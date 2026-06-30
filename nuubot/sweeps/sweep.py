from __future__ import annotations

from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
import itertools
import json
import signal
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from nuubot.core.sweep import expand_values, sweep_bot_data
from nuubot.datastore import AccountRow, BotrunRow, EventRow, FillRow, OrderRow, PositionRow, SweeprunRow, SweepRow
from nuubot.nuubot import Nuubot
from nuubot.sweeps.models import SweepConfig
from nuubot.sweeps.sweeprun import run_sweeprun_task

MAX_SWEEP_WORKERS = 8


@dataclass
class Sweep:
    nuubot: Nuubot
    sweep_id: int
    finalizers: dict[int, threading.Thread]
    engine: Engine | None = None

    def run(self) -> dict[str, Any]:
        finalizer = self.finalizers.get(self.sweep_id)
        if finalizer is not None and finalizer.is_alive():
            raise RuntimeError(f"sweep already running: {self.sweep_id}")
        botrun_configs = self._botrun_configs()
        if not botrun_configs:
            raise RuntimeError("sweep produced no sweepruns")
        sweeprun_ids = self._reset(botrun_configs)
        workers = self._workers()
        executor = ProcessPoolExecutor(max_workers=workers, initializer=init_sweep_worker)
        futures = [
            (sweeprun_id, executor.submit(run_sweeprun_task, str(self.dbpath()), self.sweep_id, sweeprun_id, self._worker_name(sweeprun_id)))
            for sweeprun_id in sweeprun_ids
        ]
        finalizer = threading.Thread(target=self._finalize, args=(futures, executor), name=f"finalizer_sw_{self.sweep_id}")
        self.finalizers[self.sweep_id] = finalizer
        finalizer.start()
        return self.status()

    def stop(self) -> None:
        for finalizer in self.finalizers.values():
            finalizer.join()

    def status(self) -> dict[str, Any]:
        with Session(self._engine(), expire_on_commit=False) as session:
            sweep = session.get(SweepRow, self.sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {self.sweep_id}")
            counts = {
                status: session.execute(
                    select(func.count()).select_from(SweeprunRow).where(SweeprunRow.status == status)
                ).scalar_one()
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

    def dbpath(self) -> Path:
        return Path(self.nuubot.config.workspace.root) / self.nuubot.config.paths.db_dir / f"sweep_{self.sweep_id}.db"

    def _botrun_configs(self) -> list[dict[str, Any]]:
        config = SweepConfig.model_validate(self._load_config())
        sweep = config.sweep
        params = config.params
        mode = str(sweep.get("mode", ""))
        start_bot_id = int(sweep.get("start_bot_id", 0))
        if mode not in {"fast", "standard"}:
            raise RuntimeError(f"unsupported sweep mode: {mode}")
        grid = itertools.product(
            expand_values(params["ema_fast"]),
            expand_values(params["ema_slow"]),
        )
        rows = []
        for index, (fast, slow) in enumerate(grid):
            rows.append(sweep_bot_data(config.botrun, start_bot_id + index, int(fast), int(slow)))
        return rows

    def _reset(self, botrun_configs: list[dict[str, Any]]) -> list[int]:
        with Session(self._engine(), expire_on_commit=False) as session:
            sweep = session.get(SweepRow, self.sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {self.sweep_id}")

            for row_class in (FillRow, OrderRow, PositionRow, EventRow, AccountRow, BotrunRow, SweeprunRow):
                session.execute(delete(row_class))
            sweeprun_ids = self._create(session, botrun_configs)
            sweep.status = "running"
            sweep.results_json = "{}"
            sweep.sweeprun_count = len(sweeprun_ids)
            sweep.error_code = None
            sweep.error_text = None
            session.commit()
        return sweeprun_ids

    def _create(self, session: Any, botrun_configs: list[dict[str, Any]]) -> list[int]:
        sweeprun_ids = []
        for index, botrun_config in enumerate(botrun_configs):
            sweeprun = SweeprunRow(
                sweep_id=self.sweep_id,
                sweeprun_index=index,
                config_json=json.dumps({"botrun": botrun_config}, sort_keys=True, separators=(",", ":")),
                results_json="{}",
                status="queued",
            )
            session.add(sweeprun)
            session.flush()
            session.add(
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

    def _workers(self) -> int:
        workers = int(SweepConfig.model_validate(self._load_config()).sweep.get("workers", 4))
        if workers <= 0:
            raise RuntimeError(f"sweep.workers must be positive: {workers}")
        if workers > MAX_SWEEP_WORKERS:
            raise RuntimeError(f"sweep.workers must be <= {MAX_SWEEP_WORKERS}: {workers}")
        return workers

    def _worker_name(self, sweeprun_id: int) -> str:
        return f"worker_sw_{self.sweep_id}_sr_{sweeprun_id}"

    def _load_config(self) -> dict[str, Any]:
        with Session(self._engine(), expire_on_commit=False) as session:
            sweep = session.get(SweepRow, self.sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {self.sweep_id}")
            return json.loads(sweep.config_json)

    def _engine(self) -> Engine:
        if self.engine is None:
            self.engine = create_engine(
                f"sqlite:///{self.dbpath().as_posix()}",
                future=True,
                connect_args={"timeout": 30},
            )
        return self.engine

    def _finalize(self, futures: list[tuple[int, Future]], executor: ProcessPoolExecutor) -> None:
        try:
            finalize_sweep_task(self._engine(), self.sweep_id, futures, executor)
        finally:
            self.finalizers.pop(self.sweep_id, None)


def init_sweep_worker() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def finalize_sweep_task(engine: Engine, sweep_id: int, futures: list[tuple[int, Future]], executor: ProcessPoolExecutor) -> dict[str, Any]:
    try:
        for sweeprun_id, future in futures:
            try:
                future.result()
            except Exception as exc:
                with Session(engine, expire_on_commit=False) as session:
                    sweeprun = session.get(SweeprunRow, sweeprun_id)
                    if sweeprun is not None:
                        sweeprun.status = "failed"
                        sweeprun.error_code = "process_failed"
                        sweeprun.error_text = str(exc)
                    for botrun in session.query(BotrunRow).filter_by(sweeprun_id=sweeprun_id):
                        if botrun.status != "complete":
                            botrun.status = "failed"
                            botrun.error_code = "process_failed"
                            botrun.error_text = str(exc)
                    session.commit()
        with Session(engine, expire_on_commit=False) as session:
            counts = {
                status: session.execute(
                    select(func.count()).select_from(SweeprunRow).where(SweeprunRow.status == status)
                ).scalar_one()
                for status in ("queued", "running", "complete", "failed")
            }
            total = sum(counts.values())
            done = counts["complete"] + counts["failed"]
            status = "failed" if counts["failed"] else "complete"
            if done < total:
                status = "running"
            result = {"sweep_id": sweep_id, "status": status, "done_count": done, "total_count": total, **counts}
            sweep = session.get(SweepRow, sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {sweep_id}")
            sweep.status = status
            sweep.results_json = json.dumps(result, sort_keys=True, separators=(",", ":"))
            session.commit()
            return result
    finally:
        executor.shutdown(wait=True, cancel_futures=False)
        engine.dispose()
