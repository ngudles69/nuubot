from __future__ import annotations

from bisect import bisect_right

import polars as pl

from nuubot.core.dtypes import Bar, SwData, Timeframe
from nuubot.core.market_data import interval_ms
from nuubot.core.models.mconfig import SignalerConfig
from nuubot.sweeps.signalers.signaler import SwSignal


class SwEmacross:
    def __init__(self) -> None:
        self.timeframe = Timeframe.H1
        self.fast_period = 0
        self.slow_period = 0
        self.warmup_bars = 0
        self.data: list[SwData] = []
        self.trade: SwData | None = None
        self._close_ms: list[int] = []
        self._signals: list[SwSignal] = []

    def init(self, config: SignalerConfig) -> None:
        """Validate config and initialize EMA cross settings."""

        # Validate config.
        if config.name != "emacross":
            raise ValueError(f"bad SwEmacross config name: {config.name}")
        if config.partial:
            raise ValueError("SwEmacross uses closed bars only")
        if "fast" not in config.params or "slow" not in config.params:
            raise ValueError("EMA params require fast and slow")

        # Validate timeframe.
        timeframe = Timeframe(config.interval)

        # Validate EMA periods.
        fast = config.params["fast"]
        slow = config.params["slow"]
        if type(fast) is not int or type(slow) is not int:
            raise ValueError(f"EMA periods must be integers: fast={fast!r} slow={slow!r}")
        if fast <= 0 or slow <= 0:
            raise ValueError("EMA periods must be positive")
        if fast >= slow:
            raise ValueError("fast EMA must be lower than slow EMA")

        # Store settings.
        self.timeframe = timeframe
        self.fast_period = fast
        self.slow_period = slow
        self.warmup_bars = max(fast, slow) + 10
        self.data = []
        self.trade = None
        self._close_ms = []
        self._signals = []

    def start(self) -> None:
        pass

    def data_req(self, symbol: str) -> list[SwData]:
        """Return data needed to calculate EMA cross signals."""

        # Validate signaler is initialized.
        if self.warmup_bars <= 0:
            raise RuntimeError("SwEmacross must be initialized before data_req")

        # Request trade data.
        self.trade = SwData("trade", symbol, self.timeframe, self.warmup_bars)
        self.data = [self.trade]
        return self.data

    def load(self) -> None:
        """Validate loaded signaler frames."""

        # Validate data request.
        if self.trade is None:
            raise RuntimeError("SwEmacross data_req must run before load")

        # Validate loaded frame.
        if self.trade.frame is None:
            raise RuntimeError("SwEmacross trade frame is not loaded")
        warmup_count = self.trade.frame.filter(~pl.col("is_active")).height
        if warmup_count < self.trade.warmup_bars:
            raise RuntimeError(f"not enough warmup bars: need={self.trade.warmup_bars} got={warmup_count}")

    def calc(self) -> None:
        """Calculate EMA cross columns on the trade frame."""

        # Validate loaded frame.
        if self.trade is None or self.trade.frame is None:
            raise RuntimeError("SwEmacross must load data before calc")

        # Calculate EMA columns.
        frame = self.trade.frame.with_columns(
            pl.col("close").ewm_mean(span=self.fast_period, adjust=False).alias("sw_ema_fast"),
            pl.col("close").ewm_mean(span=self.slow_period, adjust=False).alias("sw_ema_slow"),
        )

        # Calculate cross columns.
        frame = frame.with_columns((pl.col("sw_ema_fast") - pl.col("sw_ema_slow")).alias("sw_ema_diff"))
        frame = frame.with_columns(pl.col("sw_ema_diff").shift(1).alias("sw_prev_ema_diff"))
        cross_up = (pl.col("sw_prev_ema_diff") <= 0) & (pl.col("sw_ema_diff") > 0) & pl.col("is_active")
        cross_down = (pl.col("sw_prev_ema_diff") >= 0) & (pl.col("sw_ema_diff") < 0) & pl.col("is_active")
        frame = frame.with_columns(
            cross_up.alias("sw_enter_long"),
            cross_down.alias("sw_enter_short"),
            cross_down.alias("sw_exit_long"),
            cross_up.alias("sw_exit_short"),
            pl.when(cross_up)
            .then(pl.lit("ema_cross_up"))
            .when(cross_down)
            .then(pl.lit("ema_cross_down"))
            .otherwise(pl.lit(""))
            .alias("sw_reason"),
        )

        # Store calculated frame.
        self.trade.frame = frame

        # Cache active signal rows for fast checks.
        active = frame.filter(pl.col("is_active")).select(
            "close_ms",
            "sw_enter_long",
            "sw_enter_short",
            "sw_exit_long",
            "sw_exit_short",
            "sw_reason",
        )
        self._close_ms = [int(value) for value in active.get_column("close_ms").to_list()]
        self._signals = [
            SwSignal(
                enter_long=bool(row["sw_enter_long"]),
                enter_short=bool(row["sw_enter_short"]),
                exit_long=bool(row["sw_exit_long"]),
                exit_short=bool(row["sw_exit_short"]),
                reason=str(row["sw_reason"]),
            )
            for row in active.iter_rows(named=True)
        ]

    def check(self, now: int | Bar) -> SwSignal:
        """Check the latest complete calculated bar for a signal."""

        # Normalize check time.
        now_ms = now.ts_ms + interval_ms(self.timeframe) if isinstance(now, Bar) else now
        if not isinstance(now_ms, int):
            raise TypeError(f"bad signal check time: {now!r}")

        # Validate calculated frame.
        if self.trade is None or self.trade.frame is None:
            raise RuntimeError("SwEmacross must calculate data before check")

        # Select latest calculated signal.
        index = bisect_right(self._close_ms, now_ms) - 1
        if index < 0:
            return SwSignal()
        close_ms = self._close_ms[index]
        if now_ms - close_ms > self.trade.max_age_ms:
            raise RuntimeError(f"stale SwEmacross signal: now_ms={now_ms} close_ms={close_ms}")

        # Return signal.
        signal = self._signals[index]
        return SwSignal(
            enter_long=signal.enter_long,
            enter_short=signal.enter_short,
            exit_long=signal.exit_long,
            exit_short=signal.exit_short,
            reason=signal.reason,
        )

    def stop(self) -> None:
        pass
