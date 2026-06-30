from __future__ import annotations

import argparse
import asyncio
import json
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
        self.mode = runtime_mode(config)
        self.log = logger(bot_log_path(config))
        self.clock = create_clock(config)
        self.telemetry = Telemetry()
        self.data = create_data(config, self.telemetry, self.log)
        self.signaler = Signaler(config, self.log)
        self.risk = Risk(config.risk)
        self.executor = create_executor(config, self.log)
        self.loop_count = 0
        self.bars_processed = 0
        self.last_bar: Bar | None = None
        self.result: BotRunResult | None = None
        self.running = False

    async def init(self) -> None:
        self.log.debug(f"runtime init ts_now: {format_ms(self.clock.now_ms())}")
        await self.data.init()
        await self.signaler.init()
        await self.risk.init()
        await self.executor.init()

    async def start(self) -> None:
        self.log.debug(f"runtime start ts_now: {format_ms(self.clock.now_ms())}")
        self.running = True
        await self.data.start()
        await self.signaler.start(self.data, self.clock.now_ms())
        self.clock.set_timer(RUNTIME_TIMER, self.config.runtime.loop_seconds, self.loop_once)
        await self.risk.start()
        await self.executor.start()

    async def loop(self) -> None:
        if self.mode in {Mode.BACKTEST, Mode.SWEEP}:
            await self.loop_backtest()
        else:
            await self.clock.run()

        await self.executor.stop(self.last_bar)
        self.result = self.executor.result(self.bars_processed)
        self.log.debug("results ts_now: %s\n%s", format_ms(self.clock.now_ms()), json.dumps(asdict(self.result), indent=2, sort_keys=True))
        self.log.debug("telemetry ts_now: %s\n%s", format_ms(self.clock.now_ms()), json.dumps(self.telemetry.__dict__, indent=2, sort_keys=True))

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
        if not self.signaler.observe(snapshot):
            self.log_telemetry()
            self.exit_if_max_loop()
            return

        self.bars_processed += self.signaler.new_bars
        self.telemetry.bars_processed += self.signaler.new_bars
        self.last_bar = self.signaler.last_bar

        risk_score = await self.risk.score()
        self.log.debug(f"risk_score={risk_score} ts_now: {format_ms(self.clock.now_ms())}")
        if await self.risk.exit():
            self.exit("risk")
            return

        decision = await self.signaler.loop_once()
        if decision.event == "exit":
            self.telemetry.signal_exits += 1
        elif decision.event == "entry":
            self.telemetry.signal_entries += 1

        if await self.signaler.exit():
            self.exit("signaler")
            return

        await self.executor.loop_once(decision.bar, decision.signal)
        if await self.executor.exit():
            self.exit("max_cycles")
            return
        self.log_telemetry()
        self.exit_if_max_loop()

    async def loop_once_target(self, event: TimeEvent) -> None:
        _ = event

        # Target loop pseudocode for review. Do not wire into Clock yet.
        #
        # loop_count += 1
        # telemetry.loops += 1
        # now_ms = Clock.now_ms()
        #
        # command = CommandServer.next_command()
        #
        # if command is kill:
        #   exit("kill")
        #   # Runtime exits. Bot state stays recoverable.
        #   CommandServer.heartbeat()
        #   return
        #
        # if max_loop reached:
        #   exit("max_loop")
        #   CommandServer.heartbeat()
        #   return
        #
        # market = Data.snapshot(now_ms)
        # signaler = Signaler.observe(market)
        #
        # Reconcile is a must-do step before any non-kill operation.
        # Nothing trades, closes, stops, or checks terminal state before this.
        # Fresh start reconciles to flat/no-op; restart reconciles live state.
        # executor = Executor.reconcile(market)
        # if executor is terminal stopped or terminal error:
        #   exit("terminal")
        #   CommandServer.heartbeat()
        #   return
        #
        # if command is stop:
        #   Executor.request_terminal_stop()
        #
        # if Executor.is_active():
        #   risk = Risk.score()
        #   if Risk.exit():
        #     Executor.request_terminal_stop()
        #   if Signaler.exit():
        #     Executor.request_terminal_stop()
        #   if Executor.exit():
        #     Executor.request_terminal_stop()
        #   if Executor.is_closing():
        #     Executor.handle_order_exits(market)
        #     if Executor.is_closed():
        #       Executor.mark_terminal_stopped()
        #       exit("stopped")
        #     end_loop()
        #     return
        #
        # if Executor.is_flat():
        #   if signaler has no usable entry data:
        #     end_loop()
        #     return
        #   decision = Signaler.loop_once()
        #   if decision is entry:
        #     Executor.enter(decision)
        #   end_loop()
        #   return
        #
        # risk = Risk.score()
        # Executor.handle_order_exits(market)
        # if Executor.can_submit_orders():
        #   Executor.submit_orders(market, signaler, risk)
        #
        # end_loop:
        #   CommandServer.heartbeat()
        #   owning objects write SQLite status/events
        #   log telemetry
        raise NotImplementedError("target runtime loop is pseudocode only")

    async def market_snapshot(self, now_ms: int) -> MarketSnapshot:
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
        try:
            self.exit("stop")
            await self.signaler.stop()
            await self.risk.stop()
            await self.data.stop()
        finally:
            self.nuubot.stop()

    def log_telemetry(self) -> None:
        if self.mode != Mode.BACKTEST:
            self.log.info("%s telemetry ts_now: %s\n%s", self.mode, format_ms(self.clock.now_ms()), json.dumps(self.telemetry.__dict__, indent=2, sort_keys=True))

    def exit_if_max_loop(self) -> None:
        if self.config.runtime.max_loop != 0 and self.loop_count >= self.config.runtime.max_loop:
            self.exit("max_loop")


def create_data(config: BotrunConfig, telemetry: Telemetry, run_log: Any) -> FileDataEngine | WsDataEngine:
    if config.runtime.mode == Mode.BACKTEST:
        return FileDataEngine(config, telemetry, run_log)
    if config.runtime.mode == Mode.SWEEP:
        return FileDataEngine(config, telemetry, run_log)
    if config.runtime.mode in {Mode.MAINNET, Mode.TESTNET, Mode.SIMNET}:
        return WsDataEngine(config, telemetry, run_log)
    raise ValueError(f"unsupported mode: {config.runtime.mode}")


def create_clock(config: BotrunConfig) -> Clock:
    if config.runtime.mode in {Mode.BACKTEST, Mode.SWEEP}:
        return ReplayClock(config.runtime.min_timer_interval_ms)
    return Clock(config.runtime.min_timer_interval_ms)


def create_executor(config: BotrunConfig, run_log: Any) -> ExecutorTrade:
    if config.executor.name != "tradebot":
        raise ValueError(f"unsupported executor: {config.executor.name}")
    trade_config = TradeConfig(config.runtime.bot_id, config.executor.take_profit_pct, config.executor.stop_loss_pct, config.executor.max_cycles)
    return ExecutorTrade(trade_config, run_log)


def bot_log_path(config: BotrunConfig) -> str:
    return f"bot_{runtime_mode(config)}_{config.runtime.bot_id}.log"


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
