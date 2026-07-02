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
from nuubot.core.market_data import date_ms, load_binance_bars
from nuubot.core.models.mconfig import BotrunConfig
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
    bot_id: int | None = None
    config: BotrunConfig | None = None
    sweeprun_config: SweeprunConfig | None = None
    bars: list[Bar] | None = None
    signaler: SignalerEmaCross | None = None
    executor: ExecutorTrade | None = None
    datastore: Datastore = field(default_factory=Datastore)
    run_log: Any | None = None
    log_path: Path | None = None
    timing: dict[str, int] = field(default_factory=dict)

    def claim(self) -> None:
        # Claim the planned sweeprun; botrun rows are actual bot start/stop rows.
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)
            if sweeprun.sweep_id != self.sweep_id:
                raise RuntimeError(f"sweeprun row wrong sweep: {self.sweeprun_id}")
            sweeprun.status = "running"
            self.sweeprun_config = SweeprunConfig.model_validate(json.loads(sweeprun.config_json))
            self.config = self.sweeprun_config
            self.bot_id = int(self.config.runtime.bot_id)
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    async def run(self) -> dict[str, Any]:
        # Workers own their datastore; they do not share Nuubot state.
        started = time.perf_counter()
        t0 = time.perf_counter()
        self.claim()
        self.record_timing("claim", time.perf_counter() - t0)

        # Run the generated config and persist the final row state.
        result = await self.run_backtest()
        self.record_timing("total", time.perf_counter() - started)
        result["telemetry"]["timing"] = self.timing
        result_json = json.dumps(result, sort_keys=True, separators=(",", ":"))
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)
            sweeprun.status = "complete"
            sweeprun.results_json = result_json
            sweeprun.error_code = None
            sweeprun.error_text = None
            # Only botruns created by actual signal/executor starts are mirrored.
            for botrun in tx.select(BotrunRow, sweeprun_id=self.sweeprun_id):
                if botrun.status != "complete":
                    botrun.status = "complete"
                    botrun.results_json = result_json
                    botrun.error_code = None
                    botrun.error_text = None
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()
        return result

    async def run_backtest(self) -> dict[str, Any]:
        # Build runtime objects and preload market data.
        t0 = time.perf_counter()
        self._setup_runtime()
        self.record_timing("init", time.perf_counter() - t0)
        if self.config is None or self.bars is None or self.signaler is None or self.executor is None or self.run_log is None:
            raise RuntimeError("sweeprun setup incomplete")

        # Warm up indicators before the tested backtest window.
        start_ms = date_ms(self.config.backtest.start)
        stop_ms = date_ms(self.config.backtest.stop)
        warmup = [bar for bar in self.bars if bar.ts_ms < start_ms][-self.signaler.required_bars :]
        if len(warmup) < self.signaler.required_bars:
            raise RuntimeError(f"not enough warmup bars: need={self.signaler.required_bars} got={len(warmup)}")

        self.run_log.info(
            f"sweeprun_start worker={self.worker_name} sweep_id={self.sweep_id} sweeprun_id={self.sweeprun_id} "
            f"symbol={self.config.market.symbol} interval={self.config.market.interval} warmup_bars={len(warmup)}"
        )
        start_started = time.perf_counter()
        t0 = time.perf_counter()
        await self.signaler.start(warmup)
        self.record_timing("start_signaler_start", time.perf_counter() - t0)
        t0 = time.perf_counter()
        await self.executor.start()
        self.record_timing("start_executor_start", time.perf_counter() - t0)
        self.record_timing("start", time.perf_counter() - start_started)

        bars_processed = 0
        entry_signals = 0
        exit_signals = 0
        first_ts = None
        last_ts = None
        last_bar = None
        pending_signal = Signal()

        # Execute each bar with the previous bar's signal, then prepare the next signal.
        loop_started = time.perf_counter()
        for bar in self.bars:
            if bar.ts_ms < start_ms or bar.ts_ms > stop_ms:
                continue
            t0 = time.perf_counter()
            await self.executor.loop_once(bar, pending_signal)
            self.record_timing("loop_executor_loop", time.perf_counter() - t0)
            t0 = time.perf_counter()
            signal = await self.signaler.loop_once(bar)
            self.record_timing("loop_signaler_loop", time.perf_counter() - t0)
            pending_signal = signal
            bars_processed += 1
            first_ts = bar.ts_ms if first_ts is None else first_ts
            last_ts = bar.ts_ms
            last_bar = bar
            if signal.entry:
                entry_signals += 1
            if signal.exit:
                exit_signals += 1
        self.record_timing("loop", time.perf_counter() - loop_started)
        # Close executor state and return the persisted result payload.
        stop_started = time.perf_counter()
        t0 = time.perf_counter()
        await self.executor.stop(last_bar)
        self.record_timing("stop_executor_stop", time.perf_counter() - t0)
        self.record_timing("stop", time.perf_counter() - stop_started)
        trade_result = asdict(self.executor.result(bars_processed))
        telemetry = {
            "bars": bars_processed,
            "warmup_bars": len(warmup),
            "entry_signals": entry_signals,
            "exit_signals": exit_signals,
            "timing": self.timing,
        }
        result = {
            "sweep_id": self.sweep_id,
            "sweeprun_id": self.sweeprun_id,
            "worker_name": self.worker_name,
            "status": "complete",
            "performance": trade_result,
            "telemetry": telemetry,
            "bars": bars_processed,
            "warmup_bars": len(warmup),
            "entry_signals": entry_signals,
            "exit_signals": exit_signals,
            "first_ts": first_ts,
            "last_ts": last_ts,
            "log_path": str(self.log_path),
            "tradebot": trade_result,
        }
        self.run_log.info("sweeprun_complete " + json.dumps(result, sort_keys=True))
        return result

    def _setup_runtime(self) -> None:
        if self.config is None or self.bot_id is None or self.sweeprun_config is None:
            raise RuntimeError("sweeprun must be claimed before setup")
        self.log_path = LOG_DIR / f"sweep_{self.sweep_id}_sweeprun_{self.sweeprun_id}.log"
        self.run_log = logger(self.log_path.name)
        validate_supported_sweeprun_runtime(self.config)
        t0 = time.perf_counter()
        self.signaler = SignalerEmaCross(self.config.signalers[0])
        self.record_timing("init_signaler_init", time.perf_counter() - t0)
        t0 = time.perf_counter()
        self.executor = ExecutorTrade(
            TradeConfig(
                self.config.runtime.bot_id,
                self.config.executor.take_profit_pct,
                self.config.executor.stop_loss_pct,
                self.config.executor.max_cycles,
                self.config.market.symbol,
                "default",
            ),
            NOOP_LOG,
        )
        self.record_timing("init_executor_init", time.perf_counter() - t0)
        t0 = time.perf_counter()
        self.bars = load_binance_bars(self.config)
        self.record_timing("init_data_load", time.perf_counter() - t0)

    def record_timing(self, key: str, seconds: float) -> None:
        self.timing[f"{key}_ms"] = self.timing.get(f"{key}_ms", 0) + int(seconds * 1000)


def validate_supported_sweeprun_runtime(config: BotrunConfig) -> None:
    if len(config.signalers) != 1:
        raise ValueError(f"sweep supports exactly one signaler: got={len(config.signalers)}")
    if config.signalers[0].name != "emacross":
        raise ValueError(f"sweep supports emacross signaler only: {config.signalers[0].name}")
    if config.executor.name != "tradebot":
        raise ValueError(f"sweep supports tradebot executor only: {config.executor.name}")


def run_sweeprun(db_path: str, sweep_id: int, sweeprun_id: int, worker_name: str) -> dict[str, Any]:
    try:
        # Process-pool entry point for one generated sweeprun.
        return asyncio.run(Sweeprun(db_path, sweep_id, sweeprun_id, worker_name).run())
    except Exception as exc:
        # Save worker failure so the sweep can count it.
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
