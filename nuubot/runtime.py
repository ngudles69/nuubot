from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websockets

from nuubot.logger import logger


@dataclass
class Config:
    bot_id: int
    mode: str
    symbol: str
    interval: str
    max_loop: int
    loop_seconds: float
    log_file: str
    data_dir: str
    start: str
    stop: str
    network: str


class Clock:
    def __init__(self, loop_seconds: float) -> None:
        self.loop_seconds = loop_seconds
        self._now_ms = int(time.time() * 1000)

    async def next_loop(self) -> None:
        await asyncio.sleep(self.loop_seconds)
        self._now_ms = int(time.time() * 1000)

    def now_ms(self) -> int:
        return self._now_ms


class BacktestData:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.bars = load_binance_bars(config)
        self.index = 0

    async def snapshot(self, now_ms: int) -> dict[str, Any]:
        _ = now_ms
        if self.index >= len(self.bars):
            return {}
        bar = self.bars[self.index]
        self.index += 1
        return {"bar": bar}


class PaperData:
    def __init__(self, config: Config, log_file: Any) -> None:
        self.config = config
        self.log = log_file
        self.latest_bbo: dict[str, Any] | None = None
        self.latest_bar: dict[str, Any] | None = None
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

    async def snapshot(self, now_ms: int) -> dict[str, Any]:
        _ = now_ms
        if self._task is not None and self._task.done():
            self._task.result()
        data: dict[str, Any] = {}
        if self.latest_bbo is not None:
            data["bbo"] = self.latest_bbo
        if self.latest_bar is not None:
            data["bar"] = self.latest_bar
        return data

    async def _listen(self) -> None:
        url = "wss://api.hyperliquid.xyz/ws"
        if self.config.network == "testnet":
            url = "wss://api.hyperliquid-testnet.xyz/ws"
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": self.config.symbol}}))
            await ws.send(
                json.dumps(
                    {
                        "method": "subscribe",
                        "subscription": {"type": "candle", "coin": self.config.symbol, "interval": self.config.interval},
                    }
                )
            )
            async for raw in ws:
                if self._stop.is_set():
                    return
                message = json.loads(raw)
                channel = message.get("channel")
                if channel == "bbo":
                    self.latest_bbo = websocket_data(message)
                    self.log.debug(f"papertest: bbo received: {self.latest_bbo}")
                elif channel == "candle":
                    self.latest_bar = websocket_data(message)
                    self.log.debug(f"papertest: bar received: {self.latest_bar}")


class Runtime:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.log = logger(config.log_file)
        self.clock = Clock(config.loop_seconds)
        if config.mode == "papertest":
            self.data = PaperData(config, self.log)
        elif config.mode == "backtest":
            self.data = BacktestData(config)
        else:
            raise ValueError(f"unsupported runtime mode: {config.mode}")
        self.loop_count = 0
        self.last_bbo_ms = 0
        self.last_bar_ms = 0

    async def init(self) -> None:
        self.log.debug("init runtime")

    async def start(self) -> None:
        self.log.debug("start runtime")
        if isinstance(self.data, PaperData):
            await self.data.start()

    async def loop(self) -> None:
        while self.loop_count < self.config.max_loop:
            await self.clock.next_loop()
            now_ms = self.clock.now_ms()
            self.loop_count += 1

            await self.process_command()

            market = await self.process_market(now_ms)
            new_bbo = self.new_bbo(market)
            new_bar = self.new_bar(market)

            if not new_bbo and not new_bar:
                self.log.debug(f"bot_id={self.config.bot_id} loop #{self.loop_count}: no new market data")
                continue

            await self.process_signaler(market)
            await self.process_risk(market)
            await self.process_executor(market)

        self.log.debug(f"bot_id={self.config.bot_id} exit runtime max_loop={self.config.max_loop}")

    async def stop(self) -> None:
        self.log.debug("stop runtime")
        if isinstance(self.data, PaperData):
            await self.data.stop()

    async def process_command(self) -> None:
        self.log.debug("process_command")

    async def process_market(self, now_ms: int) -> dict[str, Any]:
        market = await self.data.snapshot(now_ms)
        if self.config.mode == "backtest":
            self.log.debug(f"backtest: bot_id={self.config.bot_id} loop #{self.loop_count}: {market}")
        else:
            if "bbo" in market:
                self.log.debug(f"papertest: bot_id={self.config.bot_id} loop #{self.loop_count}: bbo: {market['bbo']}")
            if "bar" in market:
                self.log.debug(f"papertest: bot_id={self.config.bot_id} loop #{self.loop_count}: bar: {market['bar']}")
        return market

    async def process_signaler(self, market: dict[str, Any]) -> None:
        _ = market
        self.log.debug("process_signaler")

    async def process_risk(self, market: dict[str, Any]) -> None:
        _ = market
        self.log.debug("process_risk")

    async def process_executor(self, market: dict[str, Any]) -> None:
        _ = market
        self.log.debug("process_executor")

    def new_bbo(self, market: dict[str, Any]) -> bool:
        bbo = market.get("bbo")
        if not isinstance(bbo, dict):
            return False
        ts_ms = int(bbo.get("_received_ms") or bbo.get("time") or bbo.get("exchange_time_ms") or 0)
        if ts_ms <= self.last_bbo_ms:
            return False
        self.last_bbo_ms = ts_ms
        return True

    def new_bar(self, market: dict[str, Any]) -> bool:
        bar = market.get("bar")
        if not isinstance(bar, dict):
            return False
        ts_ms = int(bar.get("_received_ms") or bar.get("open_time_ms") or bar.get("t") or 0)
        if ts_ms <= self.last_bar_ms:
            return False
        self.last_bar_ms = ts_ms
        return True


def load_config(path: Path) -> Config:
    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    runtime = required_section(data, "runtime")
    market = required_section(data, "market")
    mode = str(required(runtime, "mode", "runtime"))
    if mode not in {"backtest", "papertest"}:
        raise ValueError(f"unsupported runtime mode: {mode}")

    data_dir = ""
    start = ""
    stop = ""
    network = ""
    if mode == "backtest":
        data_section = required_section(data, "data")
        backtest = required_section(data, "backtest")
        data_dir = str(required(data_section, "dir", "data"))
        start = str(required(backtest, "start", "backtest"))
        stop = str(required(backtest, "stop", "backtest"))
    if mode == "papertest":
        exchange = required_section(data, "exchange")
        network = str(required(exchange, "network", "exchange"))

    return Config(
        bot_id=int(required(runtime, "bot_id", "runtime")),
        mode=mode,
        symbol=str(required(market, "symbol", "market")),
        interval=str(required(market, "interval", "market")),
        max_loop=int(required(runtime, "max_loop", "runtime")),
        loop_seconds=float(required(runtime, "loop_seconds", "runtime")),
        log_file=str(required(runtime, "log_file", "runtime")),
        data_dir=data_dir,
        start=start,
        stop=stop,
        network=network,
    )


def required_section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise KeyError(f"missing [{name}] section")
    return value


def required(data: dict[str, Any], key: str, section: str) -> Any:
    if key not in data:
        raise KeyError(f"missing {section}.{key}")
    return data[key]


def load_binance_bars(config: Config) -> list[dict[str, Any]]:
    root = Path(config.data_dir) / config.symbol / config.interval
    if not root.exists():
        raise FileNotFoundError(f"missing Binance data folder: {root}")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob(f"{config.symbol}-{config.interval}-*")):
        rows.extend(read_binance_file(path))
    start_ms = date_ms(config.start) if config.start else 0
    stop_ms = date_ms(config.stop) if config.stop else 2**63 - 1
    rows = [row for row in rows if start_ms <= int(row["open_time_ms"]) <= stop_ms]
    if not rows:
        raise RuntimeError(f"no Binance bars matched {config.symbol} {config.interval} {config.start}..{config.stop}")
    return rows


def read_binance_file(path: Path) -> list[dict[str, Any]]:
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
        yield {
            "open_time_ms": ts_ms,
            "open": row[1],
            "high": row[2],
            "low": row[3],
            "close": row[4],
            "volume": row[5],
        }


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
    return {**data, "_received_ms": int(time.time() * 1000)}


async def run(path: Path) -> None:
    config = load_config(path)
    runtime = Runtime(config)
    await runtime.init()
    await runtime.start()
    try:
        await runtime.loop()
    finally:
        await runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True)
    args = parser.parse_args()
    asyncio.run(run(Path(args.file)))


if __name__ == "__main__":
    main()
