from __future__ import annotations

from nuubot.core.dtypes import Bar, Signal
from nuubot.core.models.mconfig import SignalerConfig


class SignalerEmaCross:
    def __init__(self, config: SignalerConfig) -> None:
        self.interval = config.interval
        fast = int(config.params["fast"])
        slow = int(config.params["slow"])
        if fast <= 0 or slow <= 0:
            raise ValueError("EMA periods must be positive")
        if fast >= slow:
            raise ValueError("fast EMA must be lower than slow EMA")
        self.fast_period = fast
        self.slow_period = slow
        self.fast_ema: float | None = None
        self.slow_ema: float | None = None
        self.previous_diff: float | None = None
        self.count = 0

    async def init(self) -> None:
        pass

    async def start(self) -> None:
        pass

    async def loop_once(self, bar: Bar) -> Signal:
        self.count += 1
        self.fast_ema = ema(self.fast_ema, bar.close, self.fast_period)
        self.slow_ema = ema(self.slow_ema, bar.close, self.slow_period)
        if self.count < self.slow_period:
            return Signal()

        diff = self.fast_ema - self.slow_ema
        if self.previous_diff is None:
            self.previous_diff = diff
            return Signal()

        signal = Signal()
        if self.previous_diff <= 0 < diff:
            signal = Signal(entry=True, reason="ema_cross_up")
        elif self.previous_diff >= 0 > diff:
            signal = Signal(exit=True, reason="ema_cross_down")
        self.previous_diff = diff
        return signal

    async def ingest_many(self, bars: list[Bar]) -> list[Signal]:
        signals = []
        for bar in bars:
            signals.append(await self.loop_once(bar))
        return signals

    async def exit(self) -> bool:
        return False

    async def stop(self) -> None:
        pass


def ema(previous: float | None, price: float, period: int) -> float:
    if previous is None:
        return price
    alpha = 2 / (period + 1)
    return price * alpha + previous * (1 - alpha)
