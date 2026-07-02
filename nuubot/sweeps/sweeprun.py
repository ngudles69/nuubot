from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
import time
from typing import Any

from nuubot.core.dtypes import Bar, Signal
from nuubot.core.format import format_ms
from nuubot.core.logger import LOG_DIR, logger
from nuubot.core.market_data import date_ms, read_binance_file
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
    started: float = 0.0
    pending_signal: Signal = field(default_factory=Signal)
    bars_processed: int = 0
    warmup_bars: int = 0
    entry_signals: int = 0
    exit_signals: int = 0
    last_bar: Bar | None = None

    async def execute(self) -> dict[str, Any]:
        """Run the full process-pool sweeprun lifecycle."""

        # Start sweeprun.
        self.start()

        # Run active events.
        await self.loop()

        # Finish sweeprun.
        return await self.stop()

    def start(self) -> None:
        """Start the sweeprun, mark its row running, and initialize runtime objects."""

        # Start timing.
        self.started = time.perf_counter()
        t0 = time.perf_counter()

        # Open sweeprun transaction.
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        config_json = ""
        try:
            # Get sweeprun record from DB.
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)

            # Validate sweep ownership.
            if sweeprun.sweep_id != self.sweep_id:
                raise RuntimeError(f"sweeprun row wrong sweep: {self.sweeprun_id}")

            # Keep config for runtime setup.
            config_json = sweeprun.config_json

            # Set status to running.
            sweeprun.status = "running"

            # Update DB.
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

        # Validate config.
        config = SweeprunConfig.model_validate(json.loads(config_json))

        # Store config.
        self.config = config

        # Build runtime.
        self._setup_runtime()

        # Save start timing.
        self.record_timing("start", time.perf_counter() - t0)

    async def loop(self) -> None:
        """Load input data, prepare warmup, and execute one pass per active event."""

        # Validate runtime is ready.
        if self.config is None or self.signaler is None or self.executor is None or self.run_log is None:
            raise RuntimeError("sweeprun setup incomplete")

        # Load bars.
        t0 = time.perf_counter()
        self.bars = load_sweeprun_bars(self.config)
        self.record_timing("load", time.perf_counter() - t0)

        # Select active window.
        start_ms = date_ms(self.config.sweeprun.start)
        stop_ms = date_ms(self.config.sweeprun.end)

        # Prepare warmup.
        warmup = [bar for bar in self.bars if bar.ts_ms < start_ms][-self.signaler.required_bars :]
        if len(warmup) < self.signaler.required_bars:
            raise RuntimeError(f"not enough warmup bars: need={self.signaler.required_bars} got={len(warmup)}")
        self.warmup_bars = len(warmup)

        self.run_log.info(
            f"sweeprun_start worker={self.worker_name} sweep_id={self.sweep_id} sweeprun_id={self.sweeprun_id} "
            f"symbol={self.config.executor.symbol} interval={self.config.executor.interval} warmup_bars={len(warmup)}"
        )

        # Start runtime components.
        start_started = time.perf_counter()
        t0 = time.perf_counter()
        await self.signaler.start(warmup)
        self.record_timing("signaler_start", time.perf_counter() - t0)
        t0 = time.perf_counter()
        await self.executor.start()
        self.record_timing("executor_start", time.perf_counter() - t0)
        self.record_timing("components_start", time.perf_counter() - start_started)

        # Run active events.
        loop_started = time.perf_counter()
        for bar in self.bars:
            if bar.ts_ms < start_ms or bar.ts_ms > stop_ms:
                continue
            await self.next(bar)

        # Save loop timing.
        self.record_timing("loop", time.perf_counter() - loop_started)

    async def stop(self) -> dict[str, Any]:
        """Stop execution, calculate results, and persist final sweeprun state."""

        # Validate runtime is ready.
        if self.executor is None:
            raise RuntimeError("sweeprun must be started before stop")

        # Stop executor.
        stop_started = time.perf_counter()
        t0 = time.perf_counter()
        await self.executor.stop(self.last_bar)

        # Save stop and total timing.
        self.record_timing("executor_stop", time.perf_counter() - t0)
        self.record_timing("stop", time.perf_counter() - stop_started)
        if self.started:
            self.record_timing("total", time.perf_counter() - self.started)

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
        t0 = time.perf_counter()
        await self.executor.loop_once(event, self.pending_signal)
        self.record_timing("executor_next", time.perf_counter() - t0)

        # Generate next signal.
        t0 = time.perf_counter()
        signal = await self.signaler.loop_once(event)
        self.record_timing("signaler_next", time.perf_counter() - t0)

        # Update counters.
        self.pending_signal = signal
        self.bars_processed += 1
        self.last_bar = event
        if signal.entry:
            self.entry_signals += 1
        if signal.exit:
            self.exit_signals += 1

    def _setup_runtime(self) -> None:
        """Build runtime objects for one sweeprun."""

        # Validate config is ready.
        if self.config is None:
            raise RuntimeError("sweeprun must be started before setup")

        # Start init timing.
        init_started = time.perf_counter()

        # Create run log.
        self.log_path = LOG_DIR / f"sweep_{self.sweep_id}_sweeprun_{self.sweeprun_id}.log"
        self.run_log = logger(self.log_path.name)

        # Validate supported runtime.
        validate_supported_sweeprun_runtime(self.config)

        # Build signaler.
        t0 = time.perf_counter()
        self.signaler = SignalerEmaCross(self.config.signaler)
        self.record_timing("signaler_init", time.perf_counter() - t0)

        # Build executor.
        t0 = time.perf_counter()
        self.executor = ExecutorTrade(
            TradeConfig(
                self.sweeprun_id,
                self.config.executor.take_profit_pct,
                self.config.executor.stop_loss_pct,
                self.config.executor.max_cycles,
                self.config.executor.symbol,
                "default",
            ),
            NOOP_LOG,
        )
        self.record_timing("executor_init", time.perf_counter() - t0)

        # Save init timing.
        self.record_timing("init", time.perf_counter() - init_started)

    def record_timing(self, key: str, seconds: float) -> None:
        key = f"timing_{key}_ms"
        self.timing[key] = self.timing.get(key, 0) + int(seconds * 1000)

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


def validate_supported_sweeprun_runtime(config: SweeprunConfig) -> None:
    if config.signaler.name != "emacross":
        raise ValueError(f"sweep supports emacross signaler only: {config.signaler.name}")
    if config.executor.name != "tradebot":
        raise ValueError(f"sweep supports tradebot executor only: {config.executor.name}")


def load_sweeprun_bars(config: SweeprunConfig) -> list[Bar]:
    """Load market bars for one sweeprun."""

    root = Path(config.sweeprun.data_dir) / config.executor.symbol / config.executor.interval
    if not root.exists():
        raise FileNotFoundError(f"missing Binance data folder: {root}")
    bars: list[Bar] = []
    for path in sorted(root.glob(f"{config.executor.symbol}-{config.executor.interval}-*")):
        bars.extend(read_binance_file(path))
    end_ms = date_ms(config.sweeprun.end)
    bars = [bar for bar in bars if bar.ts_ms <= end_ms]
    if not any(date_ms(config.sweeprun.start) <= bar.ts_ms <= end_ms for bar in bars):
        raise RuntimeError(f"no Binance bars matched {config.executor.symbol} {config.executor.interval} {config.sweeprun.start}..{config.sweeprun.end}")
    return bars


def run_sweeprun(db_path: str, sweep_id: int, sweeprun_id: int, worker_name: str) -> dict[str, Any]:
    """Run one sweeprun inside a process-pool worker."""

    try:
        # Process-pool entry point for one generated sweeprun.
        return asyncio.run(Sweeprun(db_path, sweep_id, sweeprun_id, worker_name).execute())
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
