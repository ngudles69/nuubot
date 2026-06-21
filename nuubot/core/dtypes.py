"""Domain Types"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Bar:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = True


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
