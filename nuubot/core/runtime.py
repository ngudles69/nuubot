from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from nuubot.core.clock import Clock, ReplayClock, TimeEvent
from nuubot.core.config import load_botrun_config
from nuubot.core.dtypes import Bar, BotRunResult, MarketSnapshot, Mode, Signal
from nuubot.core.logger import format_bar, format_bbo, format_ms, logger
from nuubot.core.market_data import FileDataEngine, WsDataEngine
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.core.risk import Risk
from nuubot.core.telemetry import Telemetry
from nuubot.executor.tradebot import ExecutorTrade, TradeConfig
from nuubot.signaler.emacross import SignalerEmaCross
from nuubot.signaler.startnow import SignalerStartNow

log = logger("workspace/logs/runtime.log")

RUNTIME_TIMER = "runtime"


class Runtime:
    def __init__(self, config: BotrunConfig) -> None:
        self.config = config
        self.mode = runtime_mode(config)
        self.log = logger(bot_log_path(config))
        self.clock = create_clock(config)
        self.telemetry = Telemetry()
        self.data = create_data(config, self.telemetry, self.log)
        self.signalers = create_signalers(config)
        self.risk = Risk(config.risk)
        self.executor = create_executor(config, self.log)
        self.loop_count = 0
        self.bars_processed = 0
        self.last_bar_ms_by_interval: dict[str, int] = {}
        self.last_bar: Bar | None = None
        self.result: BotRunResult | None = None
        self.running = False

    async def init(self) -> None:
        self.log.debug("runtime init", now=self.clock.now_ms())
        await self.data.init()
        for signaler in self.signalers:
            await signaler.init()
        await self.risk.init()
        await self.executor.init()

    async def start(self) -> None:
        self.log.debug("runtime start", now=self.clock.now_ms())
        self.running = True
        await self.data.start()
        await self.seed_signalers()
        self.clock.set_timer(RUNTIME_TIMER, self.config.runtime.loop_seconds, self.loop_once)
        await self.risk.start()
        await self.executor.start()

    async def seed_signalers(self) -> None:
        for signaler in self.signalers:
            history = await self.data.history(signaler.interval, signaler.required_bars)
            self.log.info(f"signaler_seed name={signaler.__class__.__name__} bars={len(history)}", now=self.clock.now_ms())
            await signaler.start(history)
            closed_history = [bar for bar in history if bar.closed]
            if closed_history:
                last = closed_history[-1]
                self.last_bar_ms_by_interval[signaler.interval] = max(self.last_bar_ms_by_interval.get(signaler.interval, 0), last.ts_ms)
                if self.last_bar is None or last.ts_ms >= self.last_bar.ts_ms:
                    self.last_bar = last

    async def loop(self) -> None:
        if self.mode == Mode.BACKTEST:
            await self.loop_backtest()
        else:
            await self.clock.run()

        await self.executor.stop(self.last_bar)
        self.result = self.executor.result(self.bars_processed)
        self.log.debug("results:\n%s", json.dumps(asdict(self.result), indent=2, sort_keys=True), now=self.clock.now_ms())
        self.log.debug("telemetry:\n%s", json.dumps(self.telemetry.__dict__, indent=2, sort_keys=True), now=self.clock.now_ms())

    async def loop_backtest(self) -> None:
        if not isinstance(self.data, FileDataEngine) or not isinstance(self.clock, ReplayClock):
            raise RuntimeError("backtest requires FileDataEngine and ReplayClock")

        for batch in self.data.replay_batches():
            if not self.running:
                break
            self.clock.set_time(batch.ts_ms)
            await self.data.ingest_replay_batch(batch)
            await self.clock.dispatch_due(batch.ts_ms)

        if self.running:
            self.exit("no_market")

    async def loop_once(self, event: TimeEvent) -> None:
        _ = event
        if self.config.runtime.max_loop != 0 and self.loop_count >= self.config.runtime.max_loop:
            self.exit("max_loop")
            return

        self.loop_count += 1
        self.telemetry.loops += 1

        snapshot = await self.market_snapshot(self.clock.now_ms())
        eligible = self.eligible_signalers(snapshot)
        if not eligible:
            self.log_telemetry()
            self.exit_if_max_loop()
            return

        self.mark_bars_processed(eligible)

        risk_score = await self.risk.score()
        self.log.debug(f"risk_score={risk_score}", now=self.clock.now_ms())
        if await self.risk.exit():
            self.exit("risk")
            return

        bar, signal = await self.process_signalers(eligible)
        if await self.signaler_exit():
            self.exit("signaler")
            return

        await self.executor.loop_once(bar, signal)
        if await self.executor.exit():
            self.exit("max_cycles")
            return
        self.log_telemetry()
        self.exit_if_max_loop()

    async def market_snapshot(self, now_ms: int) -> MarketSnapshot:
        snapshot = await self.data.snapshot(now_ms)
        for interval, bar in sorted(snapshot.bars.items()):
            self.log.debug(
                f"{self.mode} bar bot_id={self.config.runtime.bot_id} loop={self.loop_count} "
                f"tf={interval} ts_bar: {format_ms(bar.ts_ms)} data={format_bar(bar)}",
                now=now_ms,
            )
        if snapshot.bbo is not None:
            bbo_ts = snapshot.bbo.get("time")
            ts_text = format_ms(int(bbo_ts)) if isinstance(bbo_ts, int) else str(bbo_ts)
            self.log.debug(
                f"{self.mode} bbo bot_id={self.config.runtime.bot_id} loop={self.loop_count} "
                f"ts_bbo: {ts_text} data={format_bbo(snapshot.bbo)}",
                now=now_ms,
            )
        return snapshot

    def eligible_signalers(self, snapshot: MarketSnapshot) -> list[tuple[Any, Bar]]:
        eligible = []
        for signaler in self.signalers:
            bar = snapshot.bars.get(signaler.interval)
            if bar is None:
                continue
            if not bar.closed and not signaler.partial:
                continue
            if bar.closed and bar.ts_ms <= self.last_bar_ms_by_interval.get(signaler.interval, 0):
                continue
            eligible.append((signaler, bar))
        return eligible

    def mark_bars_processed(self, eligible: list[tuple[Any, Bar]]) -> None:
        seen: dict[str, Bar] = {}
        for signaler, bar in eligible:
            if bar.closed:
                seen[signaler.interval] = bar
        for interval, bar in seen.items():
            self.last_bar_ms_by_interval[interval] = bar.ts_ms
            if self.last_bar is None or bar.ts_ms >= self.last_bar.ts_ms:
                self.last_bar = bar
            self.bars_processed += 1
            self.telemetry.bars_processed += 1

    async def process_signalers(self, eligible: list[tuple[Any, Bar]]) -> tuple[Bar, Signal]:
        results: list[tuple[Bar, Signal]] = []
        for signaler, bar in eligible:
            results.append((bar, await signaler.loop_once(bar)))

        exit_signal = next(((bar, signal) for bar, signal in results if signal.exit), None)
        if exit_signal is not None:
            bar, signal = exit_signal
            self.log.info(f"signal_exit reason={signal.reason}", now=bar.ts_ms)
            self.telemetry.signal_exits += 1
            return bar, signal

        entry_signal = next(((bar, signal) for bar, signal in results if signal.entry), None)
        if entry_signal is not None:
            bar, signal = entry_signal
            self.log.info(f"signal_entry reason={signal.reason}", now=bar.ts_ms)
            self.telemetry.signal_entries += 1
            return bar, signal

        return results[0]

    async def signaler_exit(self) -> bool:
        for signaler in self.signalers:
            if await signaler.exit():
                return True
        return False

    def exit(self, reason: str) -> None:
        self.log.debug(f"runtime_exit reason={reason}", now=self.clock.now_ms())
        self.running = False
        if RUNTIME_TIMER in self.clock.timers:
            self.clock.cancel_timer(RUNTIME_TIMER)

    async def stop(self) -> None:
        self.log.debug("runtime stop", now=self.clock.now_ms())
        self.exit("stop")
        for signaler in self.signalers:
            await signaler.stop()
        await self.risk.stop()
        await self.data.stop()

    def log_telemetry(self) -> None:
        if self.mode != Mode.BACKTEST:
            self.log.info(f"{self.mode} telemetry:\n%s", json.dumps(self.telemetry.__dict__, indent=2, sort_keys=True), now=self.clock.now_ms())

    def exit_if_max_loop(self) -> None:
        if self.config.runtime.max_loop != 0 and self.loop_count >= self.config.runtime.max_loop:
            self.exit("max_loop")


def create_data(config: BotrunConfig, telemetry: Telemetry, run_log: Any) -> FileDataEngine | WsDataEngine:
    if config.runtime.mode == Mode.BACKTEST:
        return FileDataEngine(config, telemetry, run_log)
    if config.runtime.mode in {Mode.MAINNET, Mode.TESTNET, Mode.SIMNET}:
        return WsDataEngine(config, telemetry, run_log)
    raise ValueError(f"unsupported mode: {config.runtime.mode}")


def create_clock(config: BotrunConfig) -> Clock:
    if config.runtime.mode == Mode.BACKTEST:
        return ReplayClock(config.runtime.min_timer_interval_ms)
    return Clock(config.runtime.min_timer_interval_ms)


def create_signalers(config: BotrunConfig) -> list[Any]:
    return [create_signaler(signaler) for signaler in config.signalers]


def create_signaler(config: Any) -> Any:
    if config.name == "emacross":
        return SignalerEmaCross(config)
    if config.name == "startnow":
        return SignalerStartNow(config)
    raise ValueError(f"unsupported signaler: {config.name}")


def create_executor(config: BotrunConfig, run_log: Any) -> ExecutorTrade:
    if config.executor.name != "tradebot":
        raise ValueError(f"unsupported executor: {config.executor.name}")
    trade_config = TradeConfig(config.runtime.bot_id, config.executor.take_profit_pct, config.executor.stop_loss_pct, config.executor.max_cycles)
    return ExecutorTrade(trade_config, run_log)


def bot_log_path(config: BotrunConfig) -> str:
    return f"workspace/logs/bot_{runtime_mode(config)}_{config.runtime.bot_id}.log"


def runtime_mode(config: BotrunConfig) -> Mode:
    return config.runtime.mode


async def run(path: Path) -> Runtime:
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
