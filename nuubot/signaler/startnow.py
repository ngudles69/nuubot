from __future__ import annotations

from nuubot.core.dtypes import Bar, Signal
from nuubot.core.models.mconfig import SignalerConfig


class SignalerStartNow:
    def __init__(self, config: SignalerConfig) -> None:
        self.interval = config.interval
        self.partial = config.partial
        self.required_bars = 0
        self.started = False

    async def init(self) -> None:
        pass

    async def start(self, history: list[Bar]) -> None:
        _ = history
        pass

    async def loop_once(self, bar: Bar) -> Signal:
        if not bar.closed and not self.partial:
            return Signal()
        if self.started:
            return Signal()
        self.started = True
        return Signal(entry=True, reason="start_now")

    async def exit(self) -> bool:
        return False

    async def stop(self) -> None:
        pass
