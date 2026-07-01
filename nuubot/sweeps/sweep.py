from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
import json
import signal
import threading
import time
from typing import Any

from nuubot.datastore import AccountRow, BotrunRow, Datastore, EventRow, FillRow, OrderRow, PositionRow, SweeprunRow, SweepRow, dbname
from nuubot.sweeps.template import GroupSweepConfig, expand_sweep_template
from nuubot.sweeps.sweeprun import run_sweeprun

MAX_SWEEP_WORKERS = 8


@dataclass
class Sweep:
    datastore: Datastore
    sweep_id: int
    result_threads: dict[int, threading.Thread]
    run_lock: threading.Lock

    def run(self) -> dict[str, Any]:
        with self.run_lock:
            result_thread = self.result_threads.get(self.sweep_id)
            if result_thread is not None and result_thread.is_alive():
                raise RuntimeError(f"sweep already running: {self.sweep_id}")

            # Validate the config before changing existing sweep rows.
            db = dbname(self.sweep_id, "sweep")
            config = GroupSweepConfig.model_validate(self._load_config())
            workers = self._workers(config)
            generated_configs = expand_sweep_template(config.model_dump(mode="json"))
            if not generated_configs:
                raise RuntimeError("sweep produced no sweepruns")

            # Build a fresh queued run set from the sweep config.
            sweeprun_ids = self._reset(generated_configs)

            executor = None
            try:
                # Launch each sweeprun in the process pool.
                executor = ProcessPoolExecutor(max_workers=workers, initializer=ignore_sigint_in_worker)
                futures = [
                    (sweeprun_id, executor.submit(run_sweeprun, str(self.datastore.dbpath(db)), self.sweep_id, sweeprun_id, self._worker_name(sweeprun_id)))
                    for sweeprun_id in sweeprun_ids
                ]

                # Let the request return while a thread waits and writes sweep results.
                started = time.perf_counter()
                result_thread = threading.Thread(target=self._sweep_results, args=(futures, executor, started, workers), name=f"sweep_results_sw_{self.sweep_id}")
                self.result_threads[self.sweep_id] = result_thread
                result_thread.start()
            except Exception as exc:
                if executor is not None:
                    executor.shutdown(wait=False, cancel_futures=True)
                self.result_threads.pop(self.sweep_id, None)
                self._launch_failed(str(exc))
                raise
        return self.status()

    def stop(self) -> None:
        for result_thread in list(self.result_threads.values()):
            result_thread.join()

    def status(self) -> dict[str, Any]:
        db = dbname(self.sweep_id, "sweep")
        sweep = self.datastore.get(db, SweepRow, sweep_id=self.sweep_id)
        counts = {
            status: self.datastore.count(db, SweeprunRow, status=status)
            for status in ("queued", "running", "complete", "failed")
        }
        sweep_status = sweep.status
        done_count = int(counts["complete"] + counts["failed"])
        total_count = int(sum(counts.values()))
        return {
            "sweep_id": self.sweep_id,
            "status": sweep_status,
            "queued_count": int(counts["queued"]),
            "running_count": int(counts["running"]),
            "complete_count": int(counts["complete"]),
            "failed_count": int(counts["failed"]),
            "done_count": done_count,
            "total_count": total_count,
            "progress": f"{done_count}/{total_count}",
        }

    def _reset(self, generated_configs: list[dict[str, Any]]) -> list[int]:
        # Replace old child rows before workers start.
        tx = self.datastore.tx(dbname(self.sweep_id, "sweep"))
        tx.start()
        try:
            sweep = tx.get(SweepRow, sweep_id=self.sweep_id)
            for row_class in (FillRow, OrderRow, PositionRow, EventRow, AccountRow, BotrunRow, SweeprunRow):
                tx.delete(row_class)
            sweeprun_ids = self._create(tx, generated_configs)
            sweep.status = "running"
            sweep.results_json = "{}"
            sweep.sweeprun_count = len(sweeprun_ids)
            sweep.error_code = None
            sweep.error_text = None
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()
        return sweeprun_ids

    def _create(self, tx: Any, generated_configs: list[dict[str, Any]]) -> list[int]:
        # Store each generated config as one queued sweeprun.
        sweeprun_ids = []
        for index, generated_config in enumerate(generated_configs):
            botrun_config = generated_config["botrun"]
            sweeprun = tx.insert(
                SweeprunRow(
                    sweep_id=self.sweep_id,
                    sweeprun_index=index,
                    config_json=json.dumps(generated_config, sort_keys=True, separators=(",", ":")),
                    results_json="{}",
                    status="queued",
                )
            )
            tx.insert(
                BotrunRow(
                    botrun_id=int(botrun_config["runtime"]["bot_id"]),
                    sweeprun_id=sweeprun.sweeprun_id,
                    bot_id=int(botrun_config["runtime"]["bot_id"]),
                    botrun_index=0,
                    config_json=json.dumps(botrun_config, sort_keys=True, separators=(",", ":")),
                    results_json="{}",
                    status="queued",
                )
            )
            sweeprun_ids.append(int(sweeprun.sweeprun_id))
        return sweeprun_ids

    def _workers(self, config: GroupSweepConfig) -> int:
        workers = int(config.sweep.get("workers", 4))
        if workers <= 0:
            raise RuntimeError(f"sweep.workers must be positive: {workers}")
        if workers > MAX_SWEEP_WORKERS:
            raise RuntimeError(f"sweep.workers must be <= {MAX_SWEEP_WORKERS}: {workers}")
        return workers

    def _worker_name(self, sweeprun_id: int) -> str:
        return f"worker_sw_{self.sweep_id}_sr_{sweeprun_id}"

    def _load_config(self) -> dict[str, Any]:
        sweep = self.datastore.get(dbname(self.sweep_id, "sweep"), SweepRow, sweep_id=self.sweep_id)
        return json.loads(sweep.config_json)

    def _launch_failed(self, message: str) -> None:
        tx = self.datastore.tx(dbname(self.sweep_id, "sweep"))
        tx.start()
        try:
            sweep = tx.get(SweepRow, sweep_id=self.sweep_id)
            sweep.status = "failed"
            sweep.error_code = "launch_failed"
            sweep.error_text = message
            for row in tx.select(SweeprunRow):
                if row.status != "complete":
                    row.status = "failed"
                    row.error_code = "launch_failed"
                    row.error_text = message
            for row in tx.select(BotrunRow):
                if row.status != "complete":
                    row.status = "failed"
                    row.error_code = "launch_failed"
                    row.error_text = message
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    def _sweep_results(self, futures: list[tuple[int, Future]], executor: ProcessPoolExecutor, started: float, workers: int) -> None:
        try:
            sweep_results(self.datastore, dbname(self.sweep_id, "sweep"), self.sweep_id, futures, executor, started, workers)
        finally:
            self.result_threads.pop(self.sweep_id, None)


def ignore_sigint_in_worker() -> None:
    # Let the parent/server process handle Ctrl+C and worker cleanup.
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def sweep_results(datastore: Datastore, db: str, sweep_id: int, futures: list[tuple[int, Future]], executor: ProcessPoolExecutor, started: float, workers: int) -> dict[str, Any]:
    try:
        # Wait for all runs to finish and record process-level failures.
        for sweeprun_id, future in futures:
            try:
                future.result()
            except Exception as exc:
                tx = datastore.tx(db)
                tx.start()
                try:
                    sweeprun = tx.get(SweeprunRow, sweeprun_id=sweeprun_id)
                    sweeprun.status = "failed"
                    sweeprun.error_code = "process_failed"
                    sweeprun.error_text = str(exc)
                    for botrun in tx.select(BotrunRow, sweeprun_id=sweeprun_id):
                        if botrun.status != "complete":
                            botrun.status = "failed"
                            botrun.error_code = "process_failed"
                            botrun.error_text = str(exc)
                    tx.commit()
                except Exception:
                    tx.rollback()
                    raise
                finally:
                    tx.close()

        # Compute sweep status from the sweeprun rows.
        tx = datastore.tx(db)
        tx.start()
        try:
            counts = {
                status: tx.count(SweeprunRow, status=status)
                for status in ("queued", "running", "complete", "failed")
            }
            total = sum(counts.values())
            done = counts["complete"] + counts["failed"]
            status = "failed" if counts["failed"] else "complete"
            if done < total:
                status = "running"
            bars = 0
            for row in tx.select(SweeprunRow):
                row_results = json.loads(row.results_json or "{}")
                bars += int(row_results.get("telemetry", {}).get("bars") or row_results.get("bars") or 0)
            total_ms = int((time.perf_counter() - started) * 1000)
            total_seconds = total_ms / 1000
            timing = {
                "total_ms": total_ms,
                "bars": bars,
                "bars_per_second": round(bars / total_seconds, 2) if total_seconds else 0.0,
                "configs_per_second": round(total / total_seconds, 2) if total_seconds else 0.0,
                "worker_count": workers,
            }
            result = {"sweep_id": sweep_id, "status": status, "done_count": done, "total_count": total, "timing": timing, "telemetry": {"timing": timing}, **counts}

            # Save the sweep result summary to the parent sweep row.
            sweep = tx.get(SweepRow, sweep_id=sweep_id)
            sweep.status = status
            sweep.results_json = json.dumps(result, sort_keys=True, separators=(",", ":"))
            tx.commit()
            return result
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()
    finally:
        executor.shutdown(wait=True, cancel_futures=False)
