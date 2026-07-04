from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from nuubot.core.data_loader import DataLoader
from nuubot.core.models.mconfig import SignalerConfig


@dataclass
class SwSignal:
    enter_long: bool = False
    enter_short: bool = False
    exit_long: bool = False
    exit_short: bool = False
    reason: str = ""
    signal_ts_ms: int = 0


class SwSignaler(Protocol):
    warmup_bars: int

    def init(self, config: SignalerConfig, symbol: str) -> None: ...
    def start(self) -> None: ...
    def load(self, loader: DataLoader, start_ms: int, stop_ms: int) -> None: ...
    def calc(self) -> None: ...
    def check(self, current_ts_ms: int) -> SwSignal: ...
    def stop(self) -> None: ...


def create_signaler(config: SignalerConfig, symbol: str) -> SwSignaler:
    if config.name == "emacross":
        from nuubot.sweeps.signalers.swemacross import SwEmacross

        signaler = SwEmacross()
        signaler.init(config, symbol)
        return signaler
    raise ValueError(f"unsupported sweep signaler: {config.name}")


def chart_display(
    config: dict[str, Any],
    load_candles: Callable[[int, int], list[dict[str, Any]]],
    start_ms: int,
    stop_ms: int,
) -> dict[str, Any]:
    if config.get("name") == "emacross":
        from nuubot.sweeps.signalers.swemacross import SwEmacross

        return SwEmacross.chart_display(config, load_candles, start_ms, stop_ms)
    return {"source": "none", "lines": [], "markers": []}
