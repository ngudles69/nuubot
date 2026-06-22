"""Domain Types"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

class Mode(StrEnum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    SIMNET = "simnet"
    BACKTEST = "backtest"


class DataNetwork(StrEnum):
    WSDATA = "wsdata"
    FILEDATA = "filedata"


class ExecNetwork(StrEnum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    SIMULATOR = "simulator"


MODE_NETWORKS: dict[Mode, tuple[DataNetwork, ExecNetwork]] = {
    Mode.MAINNET: (DataNetwork.WSDATA, ExecNetwork.MAINNET),
    Mode.TESTNET: (DataNetwork.WSDATA, ExecNetwork.TESTNET),
    Mode.SIMNET: (DataNetwork.WSDATA, ExecNetwork.SIMULATOR),
    Mode.BACKTEST: (DataNetwork.FILEDATA, ExecNetwork.SIMULATOR),
}


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
