from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from nuubot import nuubot_setup
from nuubot.core.clock import Clock, ReplayClock, TimeEvent
from nuubot.core.config import load_botrun_config
from nuubot.core.dtypes import Bar, BotRunResult, MarketSnapshot, Mode
from nuubot.core.format import format_bar, format_bbo, format_ms
from nuubot.core.logger import logger
from nuubot.core.market_data import FileDataEngine, WsDataEngine
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.core.risk import Risk
from nuubot.core.telemetry import Telemetry
from nuubot.bots.executors.tradebot.tradebot import ExecutorTrade, TradeConfig
from nuubot.signalers import Signaler

log = logger("runtime.log")

RUNTIME_TIMER = "runtime"


class Runtime:
    def __init__(self, config: BotrunConfig) -> None:
        self.nuubot = nuubot_setup()
        self.config = config
        self.mode = config.runtime.mode
        self.log = logger(bot_log_path(config))
        self.clock = build_clock(config)
        self.timing: dict[str, int] = {}
        self.results: dict[str, Any] = {}
        self.telemetry = Telemetry()
        self.data = build_data_engine(config, self.telemetry, self.log)
        self.signaler = Signaler(config, self.log)
        self.risk = Risk(config.risk)
        self.executor = build_executor(config, self.log)
        self.loop_count = 0
        self.bars_processed = 0
        self.last_bar: Bar | None = None
        self.result: BotRunResult | None = None
        self.running = False

    async def init(self) -> None:
        """Initialize runtime components."""

        self.log.debug(f"runtime init ts_now: {format_ms(self.clock.now_ms())}")
        started = time.perf_counter()

        # Initialize data.
        t0 = time.perf_counter()
        await self.data.init()
        self.add_timing("init_data_init", time.perf_counter() - t0)

        # Initialize signaler.
        t0 = time.perf_counter()
        await self.signaler.init()
        self.add_timing("init_signaler_init", time.perf_counter() - t0)
        self.merge_timing("init_signaler_init", self.signaler.timing)
        self.signaler.timing.clear()

        # Initialize risk.
        await self.risk.init()

        # Initialize executor.
        await self.executor.init()

        # Save init timing.
        self.add_timing("init", time.perf_counter() - started)

    async def start(self) -> None:
        """Start runtime components and schedule the runtime loop."""

        self.log.debug(f"runtime start ts_now: {format_ms(self.clock.now_ms())}")
        started = time.perf_counter()

        # Mark runtime active.
        self.running = True

        # Start data.
        await self.data.start()

        # Start signaler.
        t0 = time.perf_counter()
        await self.signaler.start(self.data, self.clock.now_ms())
        self.add_timing("start_signaler_start", time.perf_counter() - t0)
        self.merge_timing("start_signaler_start", self.signaler.timing)
        self.signaler.timing.clear()

        # Schedule loop.
        self.clock.set_timer(RUNTIME_TIMER, self.config.runtime.loop_seconds, self.loop_once)

        # Start risk.
        await self.risk.start()

        # Start executor.
        await self.executor.start()

        # Save start timing.
        self.add_timing("start", time.perf_counter() - started)

    async def loop(self) -> None:
        """Run events until the runtime exits, then build results."""

        started = time.perf_counter()

        # Run event loop.
        if self.mode in {Mode.BACKTEST, Mode.SWEEP}:
            await self.loop_backtest()
        else:
            await self.clock.run()

        # Stop executor.
        await self.executor.stop(self.last_bar)

        # Build result.
        self.result = self.executor.result(self.bars_processed)
        self.add_timing("loop", time.perf_counter() - started)
        self.results = {
            "performance": asdict(self.result),
            "telemetry": {
                **self.telemetry.__dict__,
                "timing": self.timing,
            },
        }
        self.log.debug("results ts_now: %s\n%s", format_ms(self.clock.now_ms()), json.dumps(asdict(self.result), indent=2, sort_keys=True))
        self.log.debug("telemetry ts_now: %s\n%s", format_ms(self.clock.now_ms()), json.dumps(self.telemetry.__dict__, indent=2, sort_keys=True))
        self.log.info("runtime_results ts_now: %s\n%s", format_ms(self.clock.now_ms()), json.dumps(self.results, indent=2, sort_keys=True))

    async def loop_backtest(self) -> None:
        """Replay file data through the runtime clock."""

        # Validate replay runtime.
        if not isinstance(self.data, FileDataEngine) or not isinstance(self.clock, ReplayClock):
            raise RuntimeError("backtest requires FileDataEngine and ReplayClock")

        # Dispatch replay batches.
        for batch in self.data.replay_batches():
            if not self.running:
                break
            self.clock.set_time(batch.ts_ms)
            await self.data.ingest_replay_batch(batch)
            await self.clock.dispatch_due(batch.ts_ms)

        # Exit exhausted replay.
        if self.running:
            self.exit("no_market")

    async def loop_once(self, event: TimeEvent) -> None:
        """Process one runtime event."""

        _ = event

        # Enforce loop limit.
        if self.config.runtime.max_loop != 0 and self.loop_count >= self.config.runtime.max_loop:
            self.exit("max_loop")
            return

        # Count loop.
        self.loop_count += 1
        self.telemetry.loops += 1

        # Read market.
        started = time.perf_counter()
        snapshot = await self.market_snapshot(self.clock.now_ms())

        # Skip empty signaler input.
        if not self.signaler.observe(snapshot):
            self.add_timing("loop_loop_once", time.perf_counter() - started)
            self.log_telemetry()
            self.exit_if_max_loop()
            return

        # Record market progress.
        self.bars_processed += self.signaler.new_bars
        self.telemetry.bars_processed += self.signaler.new_bars
        self.last_bar = self.signaler.last_bar

        # Check risk.
        risk_score = await self.risk.score()
        self.log.debug(f"risk_score={risk_score} ts_now: {format_ms(self.clock.now_ms())}")
        if await self.risk.exit():
            self.add_timing("loop_loop_once", time.perf_counter() - started)
            self.exit("risk")
            return

        # Generate signal.
        t0 = time.perf_counter()
        decision = await self.signaler.loop_once()
        self.add_timing("loop_loop_once_signaler_loop", time.perf_counter() - t0)
        if decision.event == "exit":
            self.telemetry.signal_exits += 1
        elif decision.event == "entry":
            self.telemetry.signal_entries += 1

        if await self.signaler.exit():
            self.add_timing("loop_loop_once", time.perf_counter() - started)
            self.exit("signaler")
            return

        # Execute signal.
        t0 = time.perf_counter()
        await self.executor.loop_once(decision.bar, decision.signal)
        self.add_timing("loop_loop_once_executor_loop", time.perf_counter() - t0)
        if await self.executor.exit():
            self.add_timing("loop_loop_once", time.perf_counter() - started)
            self.exit("max_cycles")
            return

        # Finish loop.
        self.log_telemetry()
        self.exit_if_max_loop()
        self.add_timing("loop_loop_once", time.perf_counter() - started)

    async def market_snapshot(self, now_ms: int) -> MarketSnapshot:
        """Read and log the current market snapshot."""

        snapshot = await self.data.snapshot(now_ms)
        for interval, bar in sorted(snapshot.bars.items()):
            self.log.debug(
                f"{self.mode} bar bot_id={self.config.runtime.bot_id} loop={self.loop_count} "
                f"tf={interval} ts_bar: {format_ms(bar.ts_ms)} data={format_bar(bar)} ts_now: {format_ms(now_ms)}"
            )
        if snapshot.bbo is not None:
            bbo_ts = snapshot.bbo.get("time")
            ts_text = format_ms(int(bbo_ts)) if isinstance(bbo_ts, int) else str(bbo_ts)
            self.log.debug(
                f"{self.mode} bbo bot_id={self.config.runtime.bot_id} loop={self.loop_count} "
                f"ts_bbo: {ts_text} data={format_bbo(snapshot.bbo)} ts_now: {format_ms(now_ms)}"
            )
        return snapshot

    def exit(self, reason: str) -> None:
        self.log.debug(f"runtime_exit reason={reason} ts_now: {format_ms(self.clock.now_ms())}")
        self.running = False
        if RUNTIME_TIMER in self.clock.timers:
            self.clock.cancel_timer(RUNTIME_TIMER)

    async def stop(self) -> None:
        self.log.debug(f"runtime stop ts_now: {format_ms(self.clock.now_ms())}")
        started = time.perf_counter()
        try:
            self.exit("stop")
            await self.signaler.stop()
            await self.risk.stop()
            await self.data.stop()
        finally:
            self.add_timing("stop", time.perf_counter() - started)
            self.nuubot.stop()

    def log_telemetry(self) -> None:
        if self.mode != Mode.BACKTEST:
            self.log.info("%s telemetry ts_now: %s\n%s", self.mode, format_ms(self.clock.now_ms()), json.dumps(self.telemetry.__dict__, indent=2, sort_keys=True))

    def exit_if_max_loop(self) -> None:
        if self.config.runtime.max_loop != 0 and self.loop_count >= self.config.runtime.max_loop:
            self.exit("max_loop")

    def add_timing(self, key: str, seconds: float) -> None:
        key = f"{key}_ms"
        self.timing[key] = self.timing.get(key, 0) + int(seconds * 1000)

    def merge_timing(self, prefix: str, timing: dict[str, int]) -> None:
        for key, value in timing.items():
            merged_key = f"{prefix}_{key.removesuffix('_ms')}_ms"
            self.timing[merged_key] = self.timing.get(merged_key, 0) + value


def build_data_engine(config: BotrunConfig, telemetry: Telemetry, run_log: Any) -> FileDataEngine | WsDataEngine:
    if config.runtime.mode == Mode.BACKTEST:
        return FileDataEngine(config, telemetry, run_log)
    if config.runtime.mode == Mode.SWEEP:
        return FileDataEngine(config, telemetry, run_log)
    if config.runtime.mode in {Mode.MAINNET, Mode.TESTNET, Mode.SIMNET}:
        return WsDataEngine(config, telemetry, run_log)
    raise ValueError(f"unsupported mode: {config.runtime.mode}")


def build_clock(config: BotrunConfig) -> Clock:
    if config.runtime.mode in {Mode.BACKTEST, Mode.SWEEP}:
        return ReplayClock(config.runtime.min_timer_interval_ms)
    return Clock(config.runtime.min_timer_interval_ms)


def build_executor(config: BotrunConfig, run_log: Any) -> ExecutorTrade:
    if config.executor.name != "tradebot":
        raise ValueError(f"unsupported executor: {config.executor.name}")
    trade_config = TradeConfig(config.runtime.bot_id, config.executor.take_profit_pct, config.executor.stop_loss_pct, config.executor.max_cycles)
    return ExecutorTrade(trade_config, run_log)


def bot_log_path(config: BotrunConfig) -> str:
    return f"bot_{config.runtime.mode}_{config.runtime.bot_id}.log"


async def run(path: Path) -> Runtime:
    """Run one bot runtime config file."""

    runtime = Runtime(load_botrun_config(path))
    try:
        await runtime.init()
        await runtime.start()
        await runtime.loop()
        return runtime
    except Exception:
        runtime.log.error("runtime_aborted")
        raise
    finally:
        await runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True)
    args = parser.parse_args()
    asyncio.run(run(Path(args.file)))


if __name__ == "__main__":
    main()
