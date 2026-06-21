from __future__ import annotations

from nuubot.core.dtypes import Bar, Signal
from nuubot.core.models.mconfig import SignalerConfig


class SignalerStartNow:
    def __init__(self, config: SignalerConfig) -> None:
        self.interval = config.interval
        self.started = False

    async def init(self) -> None:
        pass

    async def start(self) -> None:
        pass

    async def loop_once(self, bar: Bar) -> Signal:
        _ = bar
        if self.started:
            return Signal()
        self.started = True
        return Signal(entry=True, reason="start_now")

    async def exit(self) -> bool:
        return False

    async def stop(self) -> None:
        pass
