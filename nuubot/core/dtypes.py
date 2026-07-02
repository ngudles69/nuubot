"""Domain Types"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import polars as pl

class Mode(StrEnum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    SIMNET = "simnet"
    BACKTEST = "backtest"
    SWEEP = "sweep"


class DataNetwork(StrEnum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    FILENET = "filenet"


class ExecNetwork(StrEnum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    SIMNET = "simnet"
    SWEEP = "sweep"


class HyperliquidNetwork(StrEnum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    SIMNET = "simnet"


class Timeframe(StrEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


@dataclass
class Bar:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = True


@dataclass(frozen=True)
class DataReq:
    symbol: str
    interval: str
    warmup_bars: int = 0


@dataclass
class SwData:
    name: str
    symbol: str
    timeframe: Timeframe
    warmup_bars: int
    max_age_ms: int = 0
    frame: pl.DataFrame | None = None


@dataclass(order=True)
class ReplayEvent:
    ts_ms: int
    priority: int
    seq: int
    kind: str = field(compare=False)
    payload: Any = field(compare=False)


@dataclass
class ReplayBatch:
    ts_ms: int
    events: list[ReplayEvent]


@dataclass
class MarketSnapshot:
    bbo: dict[str, Any] | None = None
    bars: dict[str, Bar] = field(default_factory=dict)


@dataclass
class Signal:
    entry: bool = False
    exit: bool = False
    reason: str = ""


@dataclass
class BotRunResult:
    config_id: int
    pnl_pct: float
    wins: int
    losses: int
    trades: int
    max_drawdown_pct: float
    bars: int
    cycles: int
