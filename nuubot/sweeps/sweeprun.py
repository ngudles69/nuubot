from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
from typing import Any

from nuubot.core.dtypes import Bar, DataReq, Signal
from nuubot.core.format import format_ms
from nuubot.core.logger import LOG_DIR, logger
from nuubot.core.market_data import date_ms, read_binance_file
from nuubot.core.telemetry import pt_now_ts_ms
from nuubot.datastore import BotrunRow, Datastore, SweeprunRow
from nuubot.signalers.emacross import SignalerEmaCross
from nuubot.sweeps.models import SweeprunConfig
from nuubot.bots.executors.tradebot.tradebot import ExecutorTrade, TradeConfig

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
    signaler: SignalerEmaCross | None = None
    executor: ExecutorTrade | None = None
    datastore: Datastore = field(default_factory=Datastore)
    run_log: Any | None = None
    log_path: Path | None = None
    timing: dict[str, int] = field(default_factory=dict)
    pt_total_ts_ms: int = 0
    pending_signal: Signal = field(default_factory=Signal)
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
        self.signaler = SignalerEmaCross(config.signaler)
        self.record_timing_ms("signaler_init", pt_now_ts_ms() - pt_signaler_init_ts_ms)

        # Build executor.
        pt_executor_init_ts_ms = pt_now_ts_ms()
        self.executor = ExecutorTrade(
            TradeConfig(
                self.sweeprun_id,
                config.executor.take_profit_pct,
                config.executor.stop_loss_pct,
                config.executor.max_cycles,
                config.executor.symbol,
                "default",
            ),
            NOOP_LOG,
        )
        self.record_timing_ms("executor_init", pt_now_ts_ms() - pt_executor_init_ts_ms)

        # Select active window.
        self.start_ms = date_ms(config.sweeprun.start)
        self.stop_ms = date_ms(config.sweeprun.end)

        # Get required data.
        data_req = self.signaler.data_req(config.executor.symbol) + self.executor.data_req(config.executor.interval)

        # Load required data.
        pt_load_ts_ms = pt_now_ts_ms()
        self.bars = load_bars(config, data_req)
        self.record_timing_ms("load", pt_now_ts_ms() - pt_load_ts_ms)

        self.run_log.info(
            f"sweeprun_start worker={self.worker_name} sweep_id={self.sweep_id} sweeprun_id={self.sweeprun_id} "
            f"symbol={config.executor.symbol} interval={config.executor.interval}"
        )

        # Start signaler.
        pt_signaler_start_ts_ms = pt_now_ts_ms()
        await self.signaler.start(self.bars, self.start_ms, self.stop_ms)
        self.warmup_bars = self.signaler.warmup_bars
        self.record_timing_ms("signaler_start", pt_now_ts_ms() - pt_signaler_start_ts_ms)

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
        if self.executor is None:
            raise RuntimeError("sweeprun must be started before stop")

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
        pt_signaler_next_ts_ms = pt_now_ts_ms()
        signal = await self.signaler.loop_once(event)
        self.record_timing_ms("signaler_next", pt_now_ts_ms() - pt_signaler_next_ts_ms)

        # Update counters.
        self.pending_signal = signal
        self.bars_processed += 1
        self.last_bar = event
        if signal.entry:
            self.entry_signals += 1
        if signal.exit:
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


def load_bars(config: SweeprunConfig, data_req: list[DataReq]) -> list[Bar]:
    """Load market bars for one sweeprun."""

    streams = {(req.symbol, req.interval) for req in data_req}
    if len(streams) != 1:
        raise RuntimeError(f"sweep supports one data stream for now: {sorted(streams)}")
    symbol, interval = next(iter(streams))
    root = Path(config.sweeprun.data_dir) / symbol / interval
    if not root.exists():
        raise FileNotFoundError(f"missing Binance data folder: {root}")
    bars: list[Bar] = []
    for path in sorted(root.glob(f"{symbol}-{interval}-*")):
        bars.extend(read_binance_file(path))
    end_ms = date_ms(config.sweeprun.end)
    bars = [bar for bar in bars if bar.ts_ms <= end_ms]
    if not any(date_ms(config.sweeprun.start) <= bar.ts_ms <= end_ms for bar in bars):
        raise RuntimeError(f"no Binance bars matched {symbol} {interval} {config.sweeprun.start}..{config.sweeprun.end}")
    return bars


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
