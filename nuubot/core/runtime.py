from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time
import urllib.request
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import websockets

from nuubot.core.clock import Clock, ReplayClock, TimeEvent
from nuubot.core.config import load_botrun_config
from nuubot.core.dtypes import Bar, BotRunResult
from nuubot.core.logger import logger
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.core.risk import Risk
from nuubot.core.telemetry import Telemetry
from nuubot.executor.tradebot import ExecutorTrade, TradeConfig
from nuubot.signaler.emacross import SignalerEmaCross
from nuubot.signaler.startnow import SignalerStartNow

log = logger("workspace/logs/runtime.log")

RUNTIME_TIMER = "runtime"


class BacktestData:
    def __init__(self, config: BotrunConfig, telemetry: Telemetry) -> None:
        self.bars = load_binance_bars(config)
        self.start_ms = date_ms(config.backtest.start)
        self.stop_ms = date_ms(config.backtest.stop)
        self.index = next((idx for idx, bar in enumerate(self.bars) if bar.ts_ms >= self.start_ms), len(self.bars))
        self.telemetry = telemetry
        self.current_bar: Bar | None = None

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def history(self, interval: str, limit: int) -> list[Bar]:
        _ = interval
        start = max(0, self.index - limit)
        return self.bars[start : self.index]

    async def ingest(self, event: TimeEvent) -> None:
        _ = event
        if self.index >= len(self.bars) or self.bars[self.index].ts_ms > self.stop_ms:
            self.current_bar = None
            return
        self.current_bar = self.bars[self.index]
        self.index += 1

    async def snapshot(self, now_ms: int) -> dict[str, Any]:
        _ = now_ms
        if self.current_bar is None:
            return {}
        return {"bar": self.current_bar}

    def next_ts_ms(self) -> int | None:
        if self.index >= len(self.bars) or self.bars[self.index].ts_ms > self.stop_ms:
            return None
        return self.bars[self.index].ts_ms


class PaperData:
    def __init__(self, config: BotrunConfig, telemetry: Telemetry) -> None:
        self.config = config
        self.telemetry = telemetry
        self.latest_bbo: dict[str, Any] | None = None
        self.latest_bar: Bar | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def history(self, interval: str, limit: int) -> list[Bar]:
        return await asyncio.to_thread(self._history, interval, limit)

    async def ingest(self, event: TimeEvent) -> None:
        _ = event

    async def snapshot(self, now_ms: int) -> dict[str, Any]:
        if self._task is not None and self._task.done():
            self._task.result()
        data: dict[str, Any] = {}
        if self.latest_bbo is not None:
            data["bbo"] = {**self.latest_bbo, "_received_ms": now_ms}
        if self.latest_bar is not None:
            data["bar"] = self.latest_bar
        return data

    async def _listen(self) -> None:
        url = "wss://api.hyperliquid.xyz/ws"
        if self.config.runtime.exec_network == "testnet":
            url = "wss://api.hyperliquid-testnet.xyz/ws"
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": self.config.market.symbol}}))
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "candle", "coin": self.config.market.symbol, "interval": self.config.market.interval}}))
            async for raw in ws:
                if self._stop.is_set():
                    return
                message = json.loads(raw)
                channel = message.get("channel")
                if channel == "bbo":
                    self.latest_bbo = websocket_data(message)
                    self.telemetry.bbo_received += 1
                    log.debug(f"papertest: bbo received: bbo_ts_ms={self.latest_bbo.get('time')} bbo={self.latest_bbo.get('bbo')}")
                elif channel == "candle":
                    self.latest_bar = hyperliquid_bar(message, self.config.market.interval, wall_ms())
                    self.telemetry.candles_received += 1
                    log.debug(f"papertest: bar received: bar_ts_ms={self.latest_bar.ts_ms} bar={self.latest_bar}")

    def _history(self, interval: str, limit: int) -> list[Bar]:
        if limit <= 0:
            return []
        now_ms = wall_ms()
        interval_ms_value = interval_ms(interval)
        end_ms = now_ms - interval_ms_value
        start_ms = end_ms - interval_ms_value * (limit + 10)
        url = "https://api.hyperliquid.xyz/info"
        if self.config.runtime.exec_network == "testnet":
            url = "https://api.hyperliquid-testnet.xyz/info"
        body = json.dumps({
            "type": "candleSnapshot",
            "req": {
                "coin": self.config.market.symbol,
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms,
            },
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            rows = json.loads(response.read().decode("utf-8"))
        bars = [hyperliquid_candle(row, interval, now_ms) for row in rows]
        return [bar for bar in sorted(bars, key=lambda item: item.ts_ms) if bar.closed][-limit:]


class Runtime:
    def __init__(self, config: BotrunConfig) -> None:
        self.config = config
        self.clock = create_clock(config)
        self.telemetry = Telemetry()
        self.data = create_data(config, self.telemetry)
        self.signalers = create_signalers(config)
        self.risk = Risk(config.risk)
        self.executor = create_executor(config)
        self.loop_count = 0
        self.bars_processed = 0
        self.last_bar_ms = 0
        self.last_bar: Bar | None = None
        self.result: BotRunResult | None = None
        self.running = False

    async def init(self) -> None:
        log.debug("runtime init", now=self.clock.now_ms())
        for signaler in self.signalers:
            await signaler.init()
        await self.risk.init()
        await self.executor.init()

    async def start(self) -> None:
        log.debug("runtime start", now=self.clock.now_ms())
        self.running = True
        self.clock.set_timer(RUNTIME_TIMER, self.config.runtime.loop_seconds, self.loop_once)
        await self.data.start()
        for signaler in self.signalers:
            history = await self.data.history(signaler.interval, signaler.required_bars)
            log.info(f"signaler seed name={signaler.__class__.__name__} bars={len(history)}", now=self.clock.now_ms())
            await signaler.start(history)
            closed_history = [bar for bar in history if bar.closed]
            if closed_history:
                self.last_bar = closed_history[-1]
                self.last_bar_ms = max(self.last_bar_ms, closed_history[-1].ts_ms)
        await self.risk.start()
        await self.executor.start()

    async def loop(self) -> None:
        if self.config.runtime.exec_network == "backtest":
            await self.loop_backtest()
        else:
            await self.clock.run()

        await self.executor.stop(self.last_bar)
        self.result = self.executor.result(self.bars_processed)
        log.debug("results:\n%s", json.dumps(asdict(self.result), indent=2, sort_keys=True), now=self.clock.now_ms())
        log.debug("telemetry:\n%s", json.dumps(self.telemetry.__dict__, indent=2, sort_keys=True), now=self.clock.now_ms())

    async def loop_backtest(self) -> None:
        data = self.data
        if not isinstance(data, BacktestData) or not isinstance(self.clock, ReplayClock):
            raise RuntimeError("backtest requires BacktestData and ReplayClock")
        while self.running:
            ts_ms = data.next_ts_ms()
            if ts_ms is None:
                log.debug("runtime exit: no_market", now=self.clock.now_ms())
                self.running = False
                break
            event = TimeEvent(RUNTIME_TIMER, ts_ms, ts_ms)
            self.clock.advance(ts_ms)
            await data.ingest(event)
            await self.loop_once(event)

    async def loop_once(self, event: TimeEvent) -> None:
        _ = event
        self.loop_count += 1
        self.telemetry.loops += 1

        # exitcon - max loop
        if self.config.runtime.max_loop != 0 and self.loop_count > self.config.runtime.max_loop:
            self.exit("max_loop")
            return

        market = await self.process_market(self.clock.now_ms())
        bar = market.get("bar")
        if bar is None:
            if self.config.runtime.exec_network == "backtest":
                self.exit("no_market")
            else:
                self.log_telemetry()
            return
        if not isinstance(bar, Bar):
            self.log_telemetry()
            return
        if not bar.closed and not self.allow_partial():
            self.log_telemetry()
            return
        if bar.closed and bar.ts_ms <= self.last_bar_ms:
            self.log_telemetry()
            return

        if bar.closed:
            self.last_bar = bar
            self.last_bar_ms = bar.ts_ms
            self.bars_processed += 1
            self.telemetry.bars_processed += 1
        risk_score = await self.risk.score()
        log.debug(f"risk_score={risk_score}", now=self.clock.now_ms())
        if await self.risk.exit():
            self.exit("risk")
            return

        signal = await self.process_signalers(bar)
        if await self.signaler_exit():
            self.exit("signaler")
            return

        await self.executor.loop_once(bar, signal)
        if await self.executor.exit():
            self.exit("max_cycles")
            return
        self.log_telemetry()

    def exit(self, reason: str) -> None:
        log.debug(f"runtime exit: {reason}", now=self.clock.now_ms())
        self.running = False
        if RUNTIME_TIMER in self.clock.timers:
            self.clock.cancel_timer(RUNTIME_TIMER)

    async def stop(self) -> None:
        log.debug("runtime stop", now=self.clock.now_ms())
        self.exit("stop")
        for signaler in self.signalers:
            await signaler.stop()
        await self.risk.stop()
        await self.data.stop()

    def log_telemetry(self) -> None:
        if self.config.runtime.exec_network != "backtest":
            log.info("telemetry:\n%s", json.dumps(self.telemetry.__dict__, indent=2, sort_keys=True), now=self.clock.now_ms())

    def allow_partial(self) -> bool:
        return any(signaler.partial for signaler in self.signalers)

    async def process_market(self, now_ms: int) -> dict[str, Any]:
        if self.config.runtime.exec_network != "backtest":
            await self.data.ingest(TimeEvent(RUNTIME_TIMER, now_ms, now_ms))
        market = await self.data.snapshot(now_ms)
        if "bar" in market:
            bar = market["bar"]
            log.debug(f"{self.config.runtime.exec_network}: bot_id={self.config.runtime.bot_id} loop #{self.loop_count}: now_ms={now_ms} bar_ts_ms={bar.ts_ms} closed={bar.closed} bar={bar}")
        if "bbo" in market:
            bbo = market["bbo"]
            log.debug(f"{self.config.runtime.exec_network}: bot_id={self.config.runtime.bot_id} loop #{self.loop_count}: now_ms={now_ms} bbo_ts_ms={bbo.get('time')} bbo={bbo.get('bbo')}")
        if not market and self.config.runtime.exec_network == "backtest":
            log.debug(f"backtest: bot_id={self.config.runtime.bot_id} no more bars", now=now_ms)
        return market

    async def process_signalers(self, bar: Bar) -> Any:
        signals = [await signaler.loop_once(bar) for signaler in self.signalers]
        if any(signal.exit for signal in signals):
            signal = next(signal for signal in signals if signal.exit)
            log.info(f"signal exit reason={signal.reason}", now=bar.ts_ms)
            self.telemetry.signal_exits += 1
            return signal
        if any(signal.entry for signal in signals):
            signal = next(signal for signal in signals if signal.entry)
            log.info(f"signal entry reason={signal.reason}", now=bar.ts_ms)
            self.telemetry.signal_entries += 1
            return signal
        return signals[0]

    async def signaler_exit(self) -> bool:
        for signaler in self.signalers:
            if await signaler.exit():
                return True
        return False


def create_data(config: BotrunConfig, telemetry: Telemetry) -> BacktestData | PaperData:
    if config.runtime.exec_network == "backtest":
        return BacktestData(config, telemetry)
    if config.runtime.exec_network in {"mainnet", "testnet", "simnet"}:
        return PaperData(config, telemetry)
    raise ValueError(f"unsupported exec_network: {config.runtime.exec_network}")


def create_clock(config: BotrunConfig) -> Clock:
    if config.runtime.exec_network == "backtest":
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


def create_executor(config: BotrunConfig) -> ExecutorTrade:
    if config.executor.name != "tradebot":
        raise ValueError(f"unsupported executor: {config.executor.name}")
    trade_config = TradeConfig(config.runtime.bot_id, config.executor.take_profit_pct, config.executor.stop_loss_pct, config.executor.max_cycles)
    return ExecutorTrade(trade_config)


def required(data: dict[str, Any], key: str, section: str) -> Any:
    if key not in data:
        raise KeyError(f"missing {section}.{key}")
    return data[key]


def load_binance_bars(config: BotrunConfig) -> list[Bar]:
    root = Path(config.backtest.data_dir) / config.market.symbol / config.market.interval
    if not root.exists():
        raise FileNotFoundError(f"missing Binance data folder: {root}")
    bars: list[Bar] = []
    for path in sorted(root.glob(f"{config.market.symbol}-{config.market.interval}-*")):
        bars.extend(read_binance_file(path))
    stop_ms = date_ms(config.backtest.stop)
    bars = [bar for bar in bars if bar.ts_ms <= stop_ms]
    if not any(date_ms(config.backtest.start) <= bar.ts_ms <= stop_ms for bar in bars):
        raise RuntimeError(f"no Binance bars matched {config.market.symbol} {config.market.interval} {config.backtest.start}..{config.backtest.stop}")
    return bars


def read_binance_file(path: Path) -> list[Bar]:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            name = zf.namelist()[0]
            lines = (line.decode("utf-8") for line in zf.open(name))
            return list(parse_binance_rows(lines))
    if path.suffix == ".csv":
        return list(parse_binance_rows(path.read_text(encoding="utf-8").splitlines()))
    return []


def parse_binance_rows(lines: Any) -> Any:
    for row in csv.reader(lines):
        if not row or row[0] == "open_time":
            continue
        ts_ms = int(row[0])
        if ts_ms > 9_999_999_999_999:
            ts_ms //= 1000
        yield Bar(ts_ms, float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))


def date_ms(value: str) -> int:
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp() * 1000)


def websocket_data(message: dict[str, Any]) -> dict[str, Any]:
    data = message.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"bad websocket payload: {message}")
    return data


def hyperliquid_bar(message: dict[str, Any], interval: str, now_ms: int) -> Bar:
    data = message.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"bad candle payload: {message}")
    return hyperliquid_candle(data, interval, now_ms)


def hyperliquid_candle(data: dict[str, Any], interval: str, now_ms: int) -> Bar:
    ts_ms = int(required(data, "t", "candle"))
    return Bar(
        ts_ms=ts_ms,
        open=float(required(data, "o", "candle")),
        high=float(required(data, "h", "candle")),
        low=float(required(data, "l", "candle")),
        close=float(required(data, "c", "candle")),
        volume=float(required(data, "v", "candle")),
        closed=is_closed_bar(ts_ms, interval, now_ms),
    )


def is_closed_bar(ts_ms: int, interval: str, now_ms: int) -> bool:
    return now_ms >= ts_ms + interval_ms(interval)


def interval_ms(interval: str) -> int:
    unit = interval[-1]
    value = int(interval[:-1])
    if unit == "m":
        return value * 60_000
    if unit == "h":
        return value * 3_600_000
    if unit == "d":
        return value * 86_400_000
    raise ValueError(f"unsupported interval: {interval}")


def wall_ms() -> int:
    return int(time.time() * 1000)


async def run(path: Path) -> Runtime:
    try:
        runtime = Runtime(load_botrun_config(path))
        await runtime.init()
        await runtime.start()
        try:
            await runtime.loop()
        finally:
            await runtime.stop()
        return runtime
    except Exception:
        log.error("runtime aborted.")
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True)
    args = parser.parse_args()
    asyncio.run(run(Path(args.file)))


if __name__ == "__main__":
    main()
