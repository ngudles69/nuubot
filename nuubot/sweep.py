from __future__ import annotations

import asyncio
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
import itertools
import json
from pathlib import Path
import signal
import sqlite3
import threading
import time
import tomllib
from typing import Any

from sqlalchemy import delete, func, select

from nuubot.core.logger import format_bar, format_ms, logger
from nuubot.core.market_data import date_ms, load_binance_bars
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.core.sweep import expand_values, sweep_bot_data
from nuubot.core.models.mconfig import SweepConfig
from nuubot.datastore import AccountRow, BotrunRow, EventRow, FillRow, OrderRow, PositionRow, SweeprunRow, SweepRow
from nuubot.nuubot import Nuubot
from nuubot.signaler.emacross import SignalerEmaCross

MAX_SWEEP_WORKERS = 8


@dataclass
class SweepManager:
    nuubot: Nuubot
    executor: ProcessPoolExecutor
    finalizers: list[threading.Thread]

    def create_sweep(self, template: str | dict[str, Any]) -> int:
        template_data = self._template_data(template)
        sweep_id = self.nuubot.datastore.next_seq("sweep")
        db_path = self.sweep_db_path(sweep_id)
        self.nuubot.datastore.init_sweep(db_path)
        with self.nuubot.datastore.session(db_path) as session:
            session.add(
                SweepRow(
                    sweep_id=sweep_id,
                    sweep_desc="sweep",
                    config_json=json.dumps(template_data, sort_keys=True, separators=(",", ":")),
                    results_json="{}",
                    status="configured",
                    sweeprun_count=0,
                )
            )
            session.commit()
        return sweep_id

    def load_sweep(self, sweep_id: int) -> dict[str, Any]:
        db_path = self.sweep_db_path(sweep_id)
        if not db_path.exists():
            raise RuntimeError(f"sweep DB missing: {db_path}")
        with self.nuubot.datastore.session(db_path) as session:
            sweep = session.get(SweepRow, sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {sweep_id}")
            config = json.loads(sweep.config_json)
        SweepConfig.model_validate(config)
        return config

    def run_sweep(self, sweep_id: int) -> dict[str, Any]:
        db_path = self.sweep_db_path(sweep_id)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not db_path.exists():
            raise RuntimeError(f"sweep DB missing: {db_path}")

        botrun_configs = self._botrun_configs(self.load_sweep(sweep_id))
        if not botrun_configs:
            raise RuntimeError("sweep produced no sweepruns")

        sweeprun_ids = self._reset_and_create_sweepruns(sweep_id, botrun_configs)
        futures = [
            (sweeprun_id, self.executor.submit(run_sweeprun_task, str(db_path), sweep_id, sweeprun_id))
            for sweeprun_id in sweeprun_ids
        ]
        finalizer = threading.Thread(target=finalize_sweep_task, args=(str(db_path), sweep_id, futures))
        self.finalizers.append(finalizer)
        finalizer.start()
        return self.status_sweep(sweep_id)

    def shutdown(self) -> None:
        for finalizer in self.finalizers:
            finalizer.join()

    def status_sweep(self, sweep_id: int) -> dict[str, Any]:
        db_path = self.sweep_db_path(sweep_id)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not db_path.exists():
            raise RuntimeError(f"sweep DB missing: {db_path}")
        with self.nuubot.datastore.session(db_path) as session:
            sweep = session.get(SweepRow, sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {sweep_id}")
            counts = {
                status: session.execute(
                    select(func.count()).select_from(SweeprunRow).where(SweeprunRow.status == status)
                ).scalar_one()
                for status in ("queued", "running", "complete", "failed")
            }
        done_count = int(counts["complete"] + counts["failed"])
        total_count = int(sum(counts.values()))
        return {
            "sweep_id": sweep_id,
            "status": sweep.status,
            "queued_count": int(counts["queued"]),
            "running_count": int(counts["running"]),
            "complete_count": int(counts["complete"]),
            "failed_count": int(counts["failed"]),
            "done_count": done_count,
            "total_count": total_count,
            "progress": f"{done_count}/{total_count}",
        }

    def sweep_db_path(self, sweep_id: int) -> Path:
        return Path(self.nuubot.config.workspace.root) / self.nuubot.config.paths.db_dir / f"sweep_{sweep_id}.db"

    def _botrun_configs(self, sweep_data: dict[str, Any]) -> list[dict[str, Any]]:
        config = SweepConfig.model_validate(sweep_data)
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

    def _reset_and_create_sweepruns(self, sweep_id: int, botrun_configs: list[dict[str, Any]]) -> list[int]:
        db_path = self.sweep_db_path(sweep_id)
        with self.nuubot.datastore.session(db_path) as session:
            sweep = session.get(SweepRow, sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {sweep_id}")

            for row_class in (FillRow, OrderRow, PositionRow, EventRow, AccountRow, BotrunRow, SweeprunRow):
                session.execute(delete(row_class))

            sweeprun_ids = []
            for index, botrun_config in enumerate(botrun_configs):
                sweeprun = SweeprunRow(
                    sweep_id=sweep_id,
                    sweeprun_index=index,
                    config_json=json.dumps({"botrun": botrun_config}, sort_keys=True, separators=(",", ":")),
                    results_json="{}",
                    status="queued",
                )
                session.add(sweeprun)
                session.flush()
                botrun = BotrunRow(
                    sweeprun_id=sweeprun.sweeprun_id,
                    bot_id=int(botrun_config["runtime"]["bot_id"]),
                    botrun_index=0,
                    config_json=json.dumps(botrun_config, sort_keys=True, separators=(",", ":")),
                    results_json="{}",
                    status="queued",
                )
                session.add(botrun)
                sweeprun_ids.append(int(sweeprun.sweeprun_id))

            sweep.status = "running"
            sweep.results_json = "{}"
            sweep.sweeprun_count = len(sweeprun_ids)
            sweep.error_code = None
            sweep.error_text = None
            session.commit()
        return sweeprun_ids

    def _template_data(self, template: str | dict[str, Any]) -> dict[str, Any]:
        data = tomllib.loads(template) if isinstance(template, str) else template
        config = SweepConfig.model_validate(data)
        result = config.model_dump(mode="json")
        result["botrun"]["runtime"].setdefault("loop_seconds", 1.0)
        if result["botrun"].get("backtest"):
            result["botrun"]["backtest"]["data_dir"] = (
                f"{self.nuubot.config.paths.data_dir}/binance/raw/spot/monthly/klines"
            )
        SweepConfig.model_validate(result)
        return result


def sweepmgr_setup(nuubot: Nuubot, executor: ProcessPoolExecutor | None = None) -> SweepManager:
    if nuubot.config is None or nuubot.datastore is None:
        raise RuntimeError("nuubot_setup() must complete before sweepmgr_setup()")
    if executor is None:
        executor = ProcessPoolExecutor(max_workers=MAX_SWEEP_WORKERS, initializer=init_sweep_worker)
    return SweepManager(nuubot, executor, [])


def init_sweep_worker() -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def run_sweeprun_task(db_path: str, sweep_id: int, sweeprun_id: int) -> dict[str, Any]:
    try:
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.execute("UPDATE sweeprun SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE sweeprun_id = ?", (sweeprun_id,))
            conn.execute("UPDATE botrun SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE sweeprun_id = ?", (sweeprun_id,))
            row = conn.execute(
                "SELECT config_json FROM sweeprun WHERE sweep_id = ? AND sweeprun_id = ?",
                (sweep_id, sweeprun_id),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"sweeprun row missing: {sweeprun_id}")
            config = BotrunConfig.model_validate(json.loads(row[0])["botrun"])
            result = asyncio.run(run_sweeprun_data_loop(db_path, sweep_id, sweeprun_id, config))
            result_json = json.dumps(result, sort_keys=True, separators=(",", ":"))
            conn.execute(
                "UPDATE sweeprun SET status = 'complete', results_json = ?, error_code = NULL, error_text = NULL, updated_at = CURRENT_TIMESTAMP WHERE sweeprun_id = ?",
                (result_json, sweeprun_id),
            )
            conn.execute(
                "UPDATE botrun SET status = 'complete', results_json = ?, error_code = NULL, error_text = NULL, updated_at = CURRENT_TIMESTAMP WHERE sweeprun_id = ?",
                (result_json, sweeprun_id),
            )
            return result
    except Exception as exc:
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.execute(
                "UPDATE sweeprun SET status = 'failed', error_code = 'sweeprun_failed', error_text = ?, updated_at = CURRENT_TIMESTAMP WHERE sweeprun_id = ?",
                (str(exc), sweeprun_id),
            )
            conn.execute(
                "UPDATE botrun SET status = 'failed', error_code = 'sweeprun_failed', error_text = ?, updated_at = CURRENT_TIMESTAMP WHERE sweeprun_id = ?",
                (str(exc), sweeprun_id),
            )
        return {"sweep_id": sweep_id, "sweeprun_id": sweeprun_id, "status": "failed", "error": str(exc)}


async def run_sweeprun_data_loop(db_path: str, sweep_id: int, sweeprun_id: int, config: BotrunConfig) -> dict[str, Any]:
    log_path = Path(db_path).parent.parent / "logs" / f"sweep_{sweep_id}_sweeprun_{sweeprun_id}.log"
    run_log = logger(str(log_path))
    bars = load_binance_bars(config)
    start_ms = date_ms(config.backtest.start)
    stop_ms = date_ms(config.backtest.stop)
    signaler = SignalerEmaCross(config.signalers[0])
    warmup = [bar for bar in bars if bar.ts_ms < start_ms][-signaler.required_bars :]
    if len(warmup) < signaler.required_bars:
        raise RuntimeError(f"not enough warmup bars: need={signaler.required_bars} got={len(warmup)}")

    run_log.info(
        f"sweeprun_start sweep_id={sweep_id} sweeprun_id={sweeprun_id} "
        f"symbol={config.market.symbol} interval={config.market.interval} warmup_bars={len(warmup)}"
    )
    await signaler.start(warmup)

    bars_processed = 0
    entry_signals = 0
    exit_signals = 0
    first_ts = None
    last_ts = None
    for bar in bars:
        if bar.ts_ms < start_ms or bar.ts_ms > stop_ms:
            continue
        signal = await signaler.loop_once(bar)
        bars_processed += 1
        first_ts = bar.ts_ms if first_ts is None else first_ts
        last_ts = bar.ts_ms
        if signal.entry:
            entry_signals += 1
        if signal.exit:
            exit_signals += 1
        run_log.info(
            f"bar sweep_id={sweep_id} sweeprun_id={sweeprun_id} "
            f"ts={format_ms(bar.ts_ms)} data={format_bar(bar)} "
            f"ema_fast={signaler.fast_ema} ema_slow={signaler.slow_ema} "
            f"entry={str(signal.entry).lower()} exit={str(signal.exit).lower()} reason={signal.reason}"
        )

    result = {
        "sweep_id": sweep_id,
        "sweeprun_id": sweeprun_id,
        "status": "complete",
        "bars": bars_processed,
        "warmup_bars": len(warmup),
        "entry_signals": entry_signals,
        "exit_signals": exit_signals,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "log_path": str(log_path),
    }
    run_log.info("sweeprun_complete " + json.dumps(result, sort_keys=True))
    return result


def finalize_sweep_task(db_path: str, sweep_id: int, futures: list[tuple[int, Future]]) -> dict[str, Any]:
    for sweeprun_id, future in futures:
        try:
            future.result()
        except Exception as exc:
            with sqlite3.connect(db_path, timeout=30) as conn:
                conn.execute(
                    "UPDATE sweeprun SET status = 'failed', error_code = 'process_failed', error_text = ?, updated_at = CURRENT_TIMESTAMP WHERE sweeprun_id = ?",
                    (str(exc), sweeprun_id),
                )
                conn.execute(
                    "UPDATE botrun SET status = 'failed', error_code = 'process_failed', error_text = ?, updated_at = CURRENT_TIMESTAMP WHERE sweeprun_id = ?",
                    (str(exc), sweeprun_id),
                )
    with sqlite3.connect(db_path, timeout=30) as conn:
        counts = {
            status: conn.execute("SELECT COUNT(*) FROM sweeprun WHERE status = ?", (status,)).fetchone()[0]
            for status in ("queued", "running", "complete", "failed")
        }
        total = sum(counts.values())
        done = counts["complete"] + counts["failed"]
        status = "failed" if counts["failed"] else "complete"
        if done < total:
            status = "running"
        result = {"sweep_id": sweep_id, "status": status, "done_count": done, "total_count": total, **counts}
        conn.execute(
            "UPDATE sweep SET status = ?, results_json = ?, updated_at = CURRENT_TIMESTAMP WHERE sweep_id = ?",
            (status, json.dumps(result, sort_keys=True, separators=(",", ":")), sweep_id),
        )
        return result
