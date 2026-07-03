from __future__ import annotations

from bisect import bisect_right

import polars as pl

from nuubot.core.data_loader import DataLoader
from nuubot.core.dtypes import SwData, Timeframe
from nuubot.core.market_data import interval_ms
from nuubot.core.models.mconfig import SignalerConfig
from nuubot.sweeps.signalers.signaler import SwSignal


class SwEmacross:
    def __init__(self) -> None:
        self.timeframe = Timeframe.H1
        self.fast_period = 0
        self.slow_period = 0
        self.warmup_bars = 0
        self._close_ms: list[int] = []
        self._signals: list[SwSignal] = []

    def init(self, config: SignalerConfig, symbol: str) -> None:
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

        # Set values.
        self.timeframe = timeframe
        self.fast_period = fast
        self.slow_period = slow

        # Setup data requirements.
        self.crossover = SwData(
            "emacross",
            symbol,
            self.timeframe,
            0,
            interval_ms(self.timeframe.value) * 2,
            0,
            0,
            pl.DataFrame(),
        )

        # Setup cache.
        self._close_ms = []
        self._signals = []

    def start(self) -> None:
        pass

    def load(self, loader: DataLoader, start_ms: int, stop_ms: int) -> None:
        """Load and validate EMA crossover data."""

        # Determine warmup window.
        interval = interval_ms(self.timeframe.value)
        self.warmup_bars = max(self.fast_period, self.slow_period) + 10
        self.crossover.warmup_bars = self.warmup_bars
        self.crossover.start_ms = start_ms - interval * self.crossover.warmup_bars
        self.crossover.stop_ms = stop_ms
        required_bars = self.crossover.warmup_bars + ((stop_ms - start_ms) // interval) + 1

        # Load crossover data.
        self.crossover.frame = loader.load(self.crossover)

        # Validate crossover data.
        if self.crossover.frame.height < required_bars:
            raise RuntimeError(f"not enough crossover bars: need={required_bars} got={self.crossover.frame.height}")

    def calc(self) -> None:
        """Calculate EMA cross columns on the crossover frame."""

        # Validate loaded frame.
        if self.crossover.frame.is_empty():
            raise RuntimeError("SwEmacross must load data before calc")

        # Calculate the full crossover dataset.
        frame = self.crossover.frame.with_columns(
            pl.col("close").ewm_mean(span=self.fast_period, adjust=False).alias("sw_ema_fast"),
            pl.col("close").ewm_mean(span=self.slow_period, adjust=False).alias("sw_ema_slow"),
        )

        # Calculate cross columns.
        frame = frame.with_columns((pl.col("sw_ema_fast") - pl.col("sw_ema_slow")).alias("sw_ema_diff"))
        frame = frame.with_columns(pl.col("sw_ema_diff").shift(1).alias("sw_prev_ema_diff"))
        cross_up = (pl.col("sw_prev_ema_diff") <= 0) & (pl.col("sw_ema_diff") > 0)
        cross_down = (pl.col("sw_prev_ema_diff") >= 0) & (pl.col("sw_ema_diff") < 0)
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
        self.crossover.frame = frame

        # Cache signal rows for fast checks.
        signals = frame.select(
            "close_ms",
            "sw_enter_long",
            "sw_enter_short",
            "sw_exit_long",
            "sw_exit_short",
            "sw_reason",
        )
        self._close_ms = [int(value) for value in signals.get_column("close_ms").to_list()]
        self._signals = [
            SwSignal(
                enter_long=bool(row["sw_enter_long"]),
                enter_short=bool(row["sw_enter_short"]),
                exit_long=bool(row["sw_exit_long"]),
                exit_short=bool(row["sw_exit_short"]),
                reason=str(row["sw_reason"]),
                signal_ts_ms=int(row["close_ms"]),
            )
            for row in signals.iter_rows(named=True)
        ]

    def check(self, current_ts_ms: int) -> SwSignal:
        """Check the latest complete calculated bar for a signal."""

        # Normalize check time.
        if not isinstance(current_ts_ms, int):
            raise TypeError(f"bad signal check time: {current_ts_ms!r}")

        # Validate calculated frame.
        if self.crossover.frame.is_empty():
            raise RuntimeError("SwEmacross must calculate data before check")

        # Select latest calculated signal.
        index = bisect_right(self._close_ms, current_ts_ms) - 1
        if index < 0:
            return SwSignal()
        close_ms = self._close_ms[index]
        if current_ts_ms - close_ms > self.crossover.max_age_ms:
            raise RuntimeError(f"stale SwEmacross signal: now_ms={current_ts_ms} close_ms={close_ms}")

        # Return signal.
        signal = self._signals[index]
        return SwSignal(
            enter_long=signal.enter_long,
            enter_short=signal.enter_short,
            exit_long=signal.exit_long,
            exit_short=signal.exit_short,
            reason=signal.reason,
            signal_ts_ms=signal.signal_ts_ms,
        )

    def stop(self) -> None:
        pass
