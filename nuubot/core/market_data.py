from __future__ import annotations

import asyncio
import csv
import json
import time
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import websockets

from nuubot.core.dtypes import Bar, MarketSnapshot, ReplayBatch, ReplayEvent
from nuubot.core.logger import logger
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.core.telemetry import Telemetry

log = logger("workspace/logs/runtime.log")


class FileDataEngine:
    def __init__(self, config: BotrunConfig, telemetry: Telemetry) -> None:
        self.config = config
        self.telemetry = telemetry
        self.start_ms = date_ms(config.backtest.start)
        self.stop_ms = date_ms(config.backtest.stop)
        self.bars: list[Bar] = []
        self.bars_by_interval: dict[str, list[Bar]] = {}
        self.replay_events: list[ReplayEvent] = []
        self.replay_batches_list: list[ReplayBatch] = []
        self.snapshot_state = MarketSnapshot()

    async def init(self) -> None:
        self.bars = load_binance_bars(self.config)
        self.bars_by_interval = {self.config.market.interval: self.bars}
        for interval in required_intervals(self.config):
            if interval == self.config.market.interval:
                continue
            self.bars_by_interval[interval] = derive_bars(self.bars, self.config.market.interval, interval)
        self.replay_events = self._prepare_replay_events()
        self.replay_batches_list = group_replay_events(self.replay_events)

    async def start(self) -> None:
        if not self.replay_batches_list:
            raise RuntimeError("backtest replay has no batches")

    async def stop(self) -> None:
        pass

    async def history(self, interval: str, limit: int) -> list[Bar]:
        if limit <= 0:
            return []
        bars = self.bars_by_interval.get(interval)
        if bars is None:
            raise ValueError(f"missing backtest bars for interval: {interval}")
        eligible = [bar for bar in bars if bar.ts_ms + interval_ms(interval) <= self.start_ms]
        return eligible[-limit:]

    def replay_batches(self) -> Iterator[ReplayBatch]:
        yield from self.replay_batches_list

    async def ingest_replay_batch(self, batch: ReplayBatch) -> None:
        for event in sorted(batch.events):
            if event.kind == "bar":
                interval, bar = event.payload
                if not isinstance(interval, str):
                    raise TypeError(f"bad replay bar interval: {interval!r}")
                if not isinstance(bar, Bar):
                    raise TypeError(f"bad replay bar payload: {bar!r}")
                self.snapshot_state.bars[interval] = bar
            elif event.kind == "bbo":
                if not isinstance(event.payload, dict):
                    raise TypeError(f"bad replay bbo payload: {event.payload!r}")
                self.snapshot_state.bbo = event.payload
            else:
                raise ValueError(f"unsupported replay event: {event.kind}")

    async def snapshot(self, now_ms: int) -> MarketSnapshot:
        _ = now_ms
        return MarketSnapshot(
            bbo=dict(self.snapshot_state.bbo) if self.snapshot_state.bbo is not None else None,
            bars=dict(self.snapshot_state.bars),
        )

    def _prepare_replay_events(self) -> list[ReplayEvent]:
        events = []
        seq = 0
        for interval in sorted(self.bars_by_interval, key=interval_ms):
            for bar in self.bars_by_interval[interval]:
                event_ts_ms = bar.ts_ms + interval_ms(interval)
                if self.start_ms <= event_ts_ms <= self.stop_ms:
                    events.append(ReplayEvent(event_ts_ms, 20, seq, "bar", (interval, bar)))
                    seq += 1
        if not events:
            raise RuntimeError(f"no replay events matched {self.config.market.symbol} {self.config.market.interval}")
        return events


class WsDataEngine:
    def __init__(self, config: BotrunConfig, telemetry: Telemetry) -> None:
        self.config = config
        self.telemetry = telemetry
        self.intervals = required_intervals(config)
        self.latest_bbo: dict[str, Any] | None = None
        self.bars: dict[str, Bar] = {}
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._ready = asyncio.Event()
        self._valid_bbo_count = 0

    async def init(self) -> None:
        pass

    async def start(self) -> None:
        self._task = asyncio.create_task(self._listen())
        await asyncio.wait_for(self._ready.wait(), timeout=15)

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

    async def snapshot(self, now_ms: int) -> MarketSnapshot:
        if self._task is not None and self._task.done():
            self._task.result()
        bbo = None if self.latest_bbo is None else {**self.latest_bbo, "_received_ms": now_ms}
        return MarketSnapshot(bbo=bbo, bars=dict(self.bars))

    async def _listen(self) -> None:
        url = "wss://api.hyperliquid.xyz/ws"
        if self.config.runtime.exec_network == "testnet":
            url = "wss://api.hyperliquid-testnet.xyz/ws"
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "bbo", "coin": self.config.market.symbol}}))
            for interval in self.intervals:
                await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "candle", "coin": self.config.market.symbol, "interval": interval}}))
            async for raw in ws:
                if self._stop.is_set():
                    return
                message = json.loads(raw)
                channel = message.get("channel")
                if channel == "bbo":
                    self.latest_bbo = websocket_data(message)
                    self.telemetry.bbo_received += 1
                    if valid_bbo(self.latest_bbo):
                        self._valid_bbo_count += 1
                        if self._valid_bbo_count >= 2:
                            self._ready.set()
                    log.debug(f"papertest: bbo received: bbo_ts_ms={self.latest_bbo.get('time')} bbo={self.latest_bbo.get('bbo')}")
                elif channel == "candle":
                    interval = hyperliquid_interval(message, self.config.market.interval)
                    bar = hyperliquid_bar(message, interval, wall_ms())
                    self.bars[interval] = bar
                    self.telemetry.candles_received += 1
                    log.debug(f"papertest: bar received: bar_ts_ms={bar.ts_ms} bar={bar}")

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


def group_replay_events(events: list[ReplayEvent]) -> list[ReplayBatch]:
    batches: list[ReplayBatch] = []
    current_ts: int | None = None
    current_events: list[ReplayEvent] = []
    for event in sorted(events):
        if current_ts is None:
            current_ts = event.ts_ms
        if event.ts_ms != current_ts:
            batches.append(ReplayBatch(current_ts, current_events))
            current_ts = event.ts_ms
            current_events = []
        current_events.append(event)
    if current_ts is not None:
        batches.append(ReplayBatch(current_ts, current_events))
    return batches


def required_intervals(config: BotrunConfig) -> list[str]:
    return sorted({config.market.interval, *(signaler.interval for signaler in config.signalers)}, key=interval_ms)


def derive_bars(base_bars: list[Bar], base_interval: str, target_interval: str) -> list[Bar]:
    base_ms = interval_ms(base_interval)
    target_ms = interval_ms(target_interval)
    if target_ms < base_ms or target_ms % base_ms != 0:
        raise ValueError(f"cannot derive {target_interval} bars from {base_interval} bars")

    expected = target_ms // base_ms
    output: list[Bar] = []
    bucket: list[Bar] = []
    bucket_start: int | None = None

    for bar in base_bars:
        current_start = bar.ts_ms - (bar.ts_ms % target_ms)
        if bucket_start is None or current_start != bucket_start:
            if bucket_start is not None and len(bucket) == expected:
                output.append(merge_bars(bucket_start, bucket))
            bucket_start = current_start
            bucket = []
        bucket.append(bar)

    if bucket_start is not None and len(bucket) == expected:
        output.append(merge_bars(bucket_start, bucket))
    return output


def merge_bars(ts_ms: int, bars: list[Bar]) -> Bar:
    return Bar(
        ts_ms=ts_ms,
        open=bars[0].open,
        high=max(bar.high for bar in bars),
        low=min(bar.low for bar in bars),
        close=bars[-1].close,
        volume=sum(bar.volume for bar in bars),
        closed=all(bar.closed for bar in bars),
    )


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


def valid_bbo(data: dict[str, Any]) -> bool:
    bbo = data.get("bbo")
    if not isinstance(bbo, list) or len(bbo) < 2:
        return False
    try:
        bid = float(bbo[0]["px"])
        ask = float(bbo[1]["px"])
    except (KeyError, TypeError, ValueError):
        return False
    return bid > 0 and ask > 0 and bid < ask


def hyperliquid_bar(message: dict[str, Any], interval: str, now_ms: int) -> Bar:
    data = message.get("data")
    if not isinstance(data, dict):
        raise ValueError(f"bad candle payload: {message}")
    return hyperliquid_candle(data, interval, now_ms)


def hyperliquid_interval(message: dict[str, Any], default: str) -> str:
    data = message.get("data")
    if isinstance(data, dict) and isinstance(data.get("i"), str):
        return data["i"]
    return default


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
