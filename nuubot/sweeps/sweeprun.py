from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from nuubot.core.data_loader import DataLoader, bars_from_frame
from nuubot.core.dtypes import Bar, SwData
from nuubot.core.logger import LOG_DIR, logger
from nuubot.core.market_data import date_ms
from nuubot.core.telemetry import pt_now_ts_ms
from nuubot.datastore import BotrunRow, Datastore, SweeprunRow
from nuubot.sweeps.executors import build_executor
from nuubot.sweeps.models import SweeprunConfig
from nuubot.sweeps.signalers import SwSignal, SwSignaler, build_signaler

NOOP_LOG = logging.getLogger("nuubot.sweeps.noop")
NOOP_LOG.addHandler(logging.NullHandler())
NOOP_LOG.propagate = False
NOOP_LOG.setLevel(logging.CRITICAL + 1)


@dataclass
class Sweeprun:
    db_path: str
    sweep_id: int
    sweeprun_id: int
    worker_name: str
    config: SweeprunConfig | None = None
    bars: list[Bar] | None = None
    signaler: SwSignaler | None = None
    executor: Any | None = None
    datastore: Datastore = field(default_factory=Datastore)
    run_log: Any | None = None
    log_path: Path | None = None
    timing: dict[str, int] = field(default_factory=dict)
    pt_total_ts_ms: int = 0
    pending_signal: SwSignal = field(default_factory=SwSignal)
    bars_processed: int = 0
    warmup_bars: int = 0
    entry_signals: int = 0
    exit_signals: int = 0
    last_bar: Bar | None = None
    start_ms: int = 0
    stop_ms: int = 0

    async def execute(self) -> dict[str, Any]:
        """Run the full process-pool sweeprun lifecycle."""

        # Start sweeprun.
        await self.start()

        # Run active events.
        await self.loop()

        # Finish sweeprun.
        return await self.stop()

    async def start(self) -> None:
        """Initialize, validate, and prepare one sweeprun for the event loop."""

        # Start timing.
        self.pt_total_ts_ms = pt_now_ts_ms()
        pt_start_ts_ms = self.pt_total_ts_ms

        # Load sweeprun row.
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)
            if sweeprun.sweep_id != self.sweep_id:
                raise RuntimeError(f"sweeprun row wrong sweep: {self.sweeprun_id}")
            config_json = sweeprun.config_json
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

        # Validate config.
        config = SweeprunConfig.model_validate(json.loads(config_json))

        # Mark row running.
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)
            sweeprun.status = "running"
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

        # Store config.
        self.config = config

        # Create run log.
        self.log_path = LOG_DIR / f"sweep_{self.sweep_id}_sweeprun_{self.sweeprun_id}.log"
        self.run_log = logger(self.log_path.name)

        # Build signaler.
        pt_signaler_init_ts_ms = pt_now_ts_ms()
        self.signaler = build_signaler(config.signaler)
        self.record_timing_ms("signaler_init", pt_now_ts_ms() - pt_signaler_init_ts_ms)

        # Build executor.
        pt_executor_init_ts_ms = pt_now_ts_ms()
        self.executor = build_executor(self.sweeprun_id, config.executor, NOOP_LOG)
        self.record_timing_ms("executor_init", pt_now_ts_ms() - pt_executor_init_ts_ms)

        # Select active window.
        self.start_ms = date_ms(config.sweeprun.start)
        self.stop_ms = date_ms(config.sweeprun.end)

        # Request required data.
        signaler_data = self.signaler.data_req(config.executor.symbol)
        executor_data = self.executor.data_req(config.executor.interval)
        data_req: list[SwData] = signaler_data + executor_data

        # Load required data.
        pt_load_ts_ms = pt_now_ts_ms()
        loader = DataLoader(config.sweeprun.data_dir)
        for item in data_req:
            item.frame = loader.load(item, self.start_ms, self.stop_ms)
        self.bars = bars_from_frame(executor_data[0].frame.filter(pl.col("is_active")))
        self.record_timing_ms("load", pt_now_ts_ms() - pt_load_ts_ms)

        self.run_log.info(
            f"sweeprun_start worker={self.worker_name} sweep_id={self.sweep_id} sweeprun_id={self.sweeprun_id} "
            f"symbol={config.executor.symbol} interval={config.executor.interval}"
        )

        # Start signaler.
        pt_signaler_start_ts_ms = pt_now_ts_ms()
        self.signaler.start()
        self.record_timing_ms("signaler_start", pt_now_ts_ms() - pt_signaler_start_ts_ms)

        # Load signaler data.
        pt_signaler_load_ts_ms = pt_now_ts_ms()
        self.signaler.load()
        self.warmup_bars = self.signaler.warmup_bars
        self.record_timing_ms("signaler_load", pt_now_ts_ms() - pt_signaler_load_ts_ms)

        # Calculate signaler data.
        pt_signaler_calc_ts_ms = pt_now_ts_ms()
        self.signaler.calc()
        self.record_timing_ms("signaler_calc", pt_now_ts_ms() - pt_signaler_calc_ts_ms)

        # Start executor.
        pt_executor_start_ts_ms = pt_now_ts_ms()
        await self.executor.start()
        self.record_timing_ms("executor_start", pt_now_ts_ms() - pt_executor_start_ts_ms)

        # Save start timing.
        self.record_timing_ms("start", pt_now_ts_ms() - pt_start_ts_ms)

    async def loop(self) -> None:
        """Prepare the active window and execute one pass per event."""

        # Validate runtime is ready.
        if self.config is None or self.bars is None or self.signaler is None or self.executor is None or self.run_log is None:
            raise RuntimeError("sweeprun setup incomplete")

        # Run active events.
        pt_loop_ts_ms = pt_now_ts_ms()
        for bar in self.bars:
            if bar.ts_ms < self.start_ms or bar.ts_ms > self.stop_ms:
                continue
            await self.next(bar)

        # Save loop timing.
        self.record_timing_ms("loop", pt_now_ts_ms() - pt_loop_ts_ms)

    async def stop(self) -> dict[str, Any]:
        """Stop execution, calculate results, and persist final sweeprun state."""

        # Validate runtime is ready.
        if self.signaler is None or self.executor is None:
            raise RuntimeError("sweeprun must be started before stop")

        # Stop signaler.
        pt_signaler_stop_ts_ms = pt_now_ts_ms()
        self.signaler.stop()
        self.record_timing_ms("signaler_stop", pt_now_ts_ms() - pt_signaler_stop_ts_ms)

        # Stop executor.
        pt_stop_ts_ms = pt_now_ts_ms()
        pt_executor_stop_ts_ms = pt_now_ts_ms()
        await self.executor.stop(self.last_bar)

        # Save stop and total timing.
        self.record_timing_ms("executor_stop", pt_now_ts_ms() - pt_executor_stop_ts_ms)
        self.record_timing_ms("stop", pt_now_ts_ms() - pt_stop_ts_ms)
        if self.pt_total_ts_ms:
            self.record_timing_ms("total", pt_now_ts_ms() - self.pt_total_ts_ms)

        # Calculate result.
        trade_result = asdict(self.executor.result(self.bars_processed))

        # Build telemetry.
        telemetry = {
            "bars": self.bars_processed,
            "warmup_bars": self.warmup_bars,
            "entry_signals": self.entry_signals,
            "exit_signals": self.exit_signals,
            "timing": self.timing,
        }

        # Build result.
        result = {
            "sweep_id": self.sweep_id,
            "sweeprun_id": self.sweeprun_id,
            "worker_name": self.worker_name,
            "status": "complete",
            "performance": trade_result,
            "telemetry": telemetry,
            "bars": self.bars_processed,
            "warmup_bars": self.warmup_bars,
            "entry_signals": self.entry_signals,
            "exit_signals": self.exit_signals,
            "log_path": str(self.log_path),
            "tradebot": trade_result,
        }

        # Log result.
        self.run_log.info("sweeprun_complete " + json.dumps(result, sort_keys=True))

        # Save result to DB.
        self._save_result(result)
        return result

    # Helpers

    async def next(self, event: Bar) -> None:
        """Process one ordered event. Today it is a bar; later it may be a tick."""

        # Validate runtime is ready.
        if self.signaler is None or self.executor is None:
            raise RuntimeError("sweeprun must be started before next")

        # Execute pending signal.
        pt_executor_next_ts_ms = pt_now_ts_ms()
        await self.executor.loop_once(event, self.pending_signal)
        self.record_timing_ms("executor_next", pt_now_ts_ms() - pt_executor_next_ts_ms)

        # Generate next signal.
        pt_signaler_check_ts_ms = pt_now_ts_ms()
        signal = self.signaler.check(event)
        self.record_timing_ms("signaler_check", pt_now_ts_ms() - pt_signaler_check_ts_ms)

        # Update counters.
        self.pending_signal = signal
        self.bars_processed += 1
        self.last_bar = event
        if signal.enter_long or signal.enter_short:
            self.entry_signals += 1
        if signal.exit_long or signal.exit_short:
            self.exit_signals += 1

    def record_timing_ms(self, key: str, ms: int) -> None:
        key = f"timing_{key}_ms"
        self.timing[key] = self.timing.get(key, 0) + ms

    def _save_result(self, result: dict[str, Any]) -> None:
        """Persist final sweeprun result."""

        # Serialize result.
        result_json = json.dumps(result, sort_keys=True, separators=(",", ":"))

        # Update sweeprun row.
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)
            sweeprun.status = "complete"
            sweeprun.results_json = result_json
            sweeprun.error_code = None
            sweeprun.error_text = None

            # Update actual botrun rows.
            for botrun in tx.select(BotrunRow, sweeprun_id=self.sweeprun_id):
                if botrun.status != "complete":
                    botrun.status = "complete"
                    botrun.results_json = result_json
                    botrun.error_code = None
                    botrun.error_text = None

            # Commit result.
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()


def run_sweeprun(db_path: str, sweep_id: int, sweeprun_id: int, worker_name: str) -> dict[str, Any]:
    """Sweeprun process-pool entry point for one sweeprun."""

    try:
        # Create sweeprun object.
        sweeprun = Sweeprun(db_path, sweep_id, sweeprun_id, worker_name)

        # Execute sweeprun lifecycle.
        return asyncio.run(sweeprun.execute())
    except Exception as exc:
        # Save worker failure.
        datastore = Datastore()
        tx = datastore.tx(Path(db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=sweeprun_id)
            sweeprun.status = "failed"
            sweeprun.error_code = "sweeprun_failed"
            sweeprun.error_text = str(exc)
            for botrun in tx.select(BotrunRow, sweeprun_id=sweeprun_id):
                if botrun.status != "complete":
                    botrun.status = "failed"
                    botrun.error_code = "sweeprun_failed"
                    botrun.error_text = str(exc)
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()
        return {"sweep_id": sweep_id, "sweeprun_id": sweeprun_id, "worker_name": worker_name, "status": "failed", "error": str(exc)}
