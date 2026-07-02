from __future__ import annotations

from nuubot.core.dtypes import Bar, DataReq, Signal
from nuubot.core.models.mconfig import SignalerConfig


class SignalerEmaCross:
    def __init__(self, config: SignalerConfig) -> None:
        self.interval = config.interval
        fast = config.params["fast"]
        slow = config.params["slow"]
        if type(fast) is not int or type(slow) is not int:
            raise ValueError(f"EMA periods must be integers: fast={fast!r} slow={slow!r}")
        if fast <= 0 or slow <= 0:
            raise ValueError("EMA periods must be positive")
        if fast >= slow:
            raise ValueError("fast EMA must be lower than slow EMA")
        self.partial = config.partial
        self.required_bars = max(fast, slow) + 10
        self.fast_period = fast
        self.slow_period = slow
        self.fast_ema: float | None = None
        self.slow_ema: float | None = None
        self.previous_diff: float | None = None
        self.count = 0
        self.warmup_bars = 0

    async def init(self) -> None:
        pass

    def data_req(self, symbol: str) -> list[DataReq]:
        return [DataReq(symbol, self.interval, self.required_bars)]

    async def start(self, bars: list[Bar], start_ms: int, stop_ms: int) -> None:
        _ = stop_ms
        history = [bar for bar in bars if bar.ts_ms < start_ms]
        warmup = history[-self.required_bars :]
        if len(warmup) < self.required_bars:
            raise RuntimeError(f"not enough warmup bars: need={self.required_bars} got={len(warmup)}")
        self.warmup_bars = len(warmup)
        for bar in warmup:
            if bar.closed:
                await self._calc(bar)

    async def loop_once(self, bar: Bar) -> Signal:
        if not bar.closed and not self.partial:
            return Signal()
        return await self._calc(bar)

    async def _calc(self, bar: Bar) -> Signal:
        """Calculate the EMA cross signal for one bar."""

        # Update EMA state.
        self.count += 1
        self.fast_ema = ema(self.fast_ema, bar.close, self.fast_period)
        self.slow_ema = ema(self.slow_ema, bar.close, self.slow_period)
        if self.count < self.slow_period:
            return Signal()

        # Detect cross.
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
            signals.append(await self._calc(bar))
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
