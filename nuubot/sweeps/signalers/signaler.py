from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from nuubot.core.data_loader import DataLoader
from nuubot.core.dtypes import Bar
from nuubot.core.models.mconfig import SignalerConfig


@dataclass
class SwSignal:
    enter_long: bool = False
    enter_short: bool = False
    exit_long: bool = False
    exit_short: bool = False
    reason: str = ""


class SwSignaler(Protocol):
    warmup_bars: int

    def init(self, config: SignalerConfig, symbol: str) -> None: ...
    def start(self) -> None: ...
    def load(self, loader: DataLoader, start_ms: int, stop_ms: int) -> None: ...
    def calc(self) -> None: ...
    def check(self, now: int | Bar) -> SwSignal: ...
    def stop(self) -> None: ...


def build_signaler(config: SignalerConfig, symbol: str) -> SwSignaler:
    if config.name == "emacross":
        from nuubot.sweeps.signalers.swemacross import SwEmacross

        signaler = SwEmacross()
        signaler.init(config, symbol)
        return signaler
    raise ValueError(f"unsupported sweep signaler: {config.name}")
