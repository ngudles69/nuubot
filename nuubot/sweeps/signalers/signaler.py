from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from nuubot.core.dtypes import Bar, SwData
from nuubot.core.models.mconfig import SignalerConfig


@dataclass
class SwSignal:
    enter_long: bool = False
    enter_short: bool = False
    exit_long: bool = False
    exit_short: bool = False
    reason: str = ""


class SwSignaler(Protocol):
    data: list[SwData]
    warmup_bars: int

    def init(self, config: SignalerConfig) -> None: ...
    def start(self) -> None: ...
    def data_req(self, symbol: str) -> list[SwData]: ...
    def load(self) -> None: ...
    def calc(self) -> None: ...
    def check(self, now: int | Bar) -> SwSignal: ...
    def stop(self) -> None: ...


def build_signaler(config: SignalerConfig) -> SwSignaler:
    if config.name == "emacross":
        from nuubot.sweeps.signalers.swemacross import SwEmacross

        signaler = SwEmacross()
        signaler.init(config)
        return signaler
    raise ValueError(f"unsupported sweep signaler: {config.name}")
