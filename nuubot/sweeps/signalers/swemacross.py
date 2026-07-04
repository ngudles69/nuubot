from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timezone
from typing import Any, Callable

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

    @staticmethod
    def chart_display(
        config: dict[str, Any],
        load_candles: Callable[[int, int], list[dict[str, Any]]],
        start_ms: int,
        stop_ms: int,
    ) -> dict[str, Any]:
        params = config.get("params", {})
        fast = params.get("fast")
        slow = params.get("slow")
        interval = config.get("interval")
        if type(fast) is not int or type(slow) is not int or type(interval) is not str:
            return {"source": "none", "lines": [], "markers": []}
        warmup_start_ms = start_ms - interval_ms(interval) * (max(fast, slow) + 10)
        candles = load_candles(warmup_start_ms, stop_ms)
        return emacross_chart_display(candles, fast, slow, start_ms)


def emacross_chart_display(candles: list[dict[str, Any]], fast: int, slow: int, start_ms: int) -> dict[str, Any]:
    fast_values = ema([candle["close"] for candle in candles], fast)
    slow_values = ema([candle["close"] for candle in candles], slow)
    active_rows = [
        (candle, fast_value, slow_value)
        for candle, fast_value, slow_value in zip(candles, fast_values, slow_values, strict=True)
        if candle["ts_ms"] >= start_ms
    ]
    lines = [
        {"name": f"EMA {fast}", "color": "#facc15", "data": [round_value(row[1]) for row in active_rows]},
        {"name": f"EMA {slow}", "color": "#38bdf8", "data": [round_value(row[2]) for row in active_rows]},
    ]
    markers = []
    previous_diff: float | None = None
    active_index = -1
    for candle, fast_value, slow_value in zip(candles, fast_values, slow_values, strict=True):
        diff = fast_value - slow_value
        if candle["ts_ms"] >= start_ms:
            active_index += 1
            if previous_diff is not None and previous_diff <= 0 and diff > 0:
                markers.append(signal_marker(active_index, candle, "enter_long", "ema_cross_up", "#00e676"))
            elif previous_diff is not None and previous_diff >= 0 and diff < 0:
                markers.append(signal_marker(active_index, candle, "enter_short", "ema_cross_down", "#ff1744"))
        previous_diff = diff
    return {"source": "regenerated", "lines": lines, "markers": markers}


def ema(values: list[float], period: int) -> list[float]:
    alpha = 2 / (period + 1)
    current: float | None = None
    output = []
    for value in values:
        current = value if current is None else current + (value - current) * alpha
        output.append(current)
    return output


def round_value(value: float | None) -> float | None:
    return None if value is None else round(value, 8)


def signal_marker(index: int, candle: dict[str, Any], kind: str, reason: str, color: str) -> dict[str, Any]:
    high = float(candle["high"])
    low = float(candle["low"])
    pad = float(candle["close"]) * 0.02
    price = high + pad if "short" in kind else low - pad
    return {
        "name": kind,
        "value": [index, round_value(price)],
        "reason": reason,
        "time": chart_time(candle["ts_ms"]),
        "itemStyle": {"color": "rgba(0,0,0,0)", "borderColor": color, "borderWidth": 2.4},
    }


def chart_time(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
