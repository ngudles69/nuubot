"""Domain Types"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Bar:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


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
