from __future__ import annotations

import polars as pl

from nuubot.core.dtypes import Timeframe
from nuubot.core.market_data import interval_ms
from nuubot.core.models.mconfig import SignalerConfig
from nuubot.sweeps.signalers import SwEmacross
from nuubot.sweeps.signalers.signaler import chart_display


def main() -> None:
    validates_timeframe()
    load_sets_crossover_window()
    calculates_and_checks_latest_closed_bar()
    check_picks_latest_closed_row()
    rejects_stale_check_time()
    chart_display_returns_ema_lines_and_signal_markers()


def validates_timeframe() -> None:
    try:
        signaler = SwEmacross()
        signaler.init(SignalerConfig(name="emacross", interval="3m", params={"fast": 2, "slow": 3}), "SOLUSDT")
    except ValueError as exc:
        assert "3m" in str(exc)
    else:
        raise AssertionError("SwEmacross accepted unsupported timeframe")


def calculates_and_checks_latest_closed_bar() -> None:
    signaler = initialized_signaler()
    data = signaler.crossover
    assert data.name == "emacross"
    assert data.symbol == "SOLUSDT"
    assert data.timeframe == Timeframe.H1
    assert data.warmup_bars == 0

    signaler.load(StaticLoader(signal_frame(13)), 0, 0)
    assert data.warmup_bars == 13
    signaler.calc()

    frame = data.frame
    cross = frame.filter(pl.col("sw_enter_long")).tail(1)
    assert cross.height == 1

    row = cross.row(0, named=True)
    signal = signaler.check(int(row["close_ms"]))
    assert signal.enter_long
    assert not signal.enter_short
    assert not signal.exit_long
    assert signal.exit_short
    assert signal.reason == "ema_cross_up"


def load_sets_crossover_window() -> None:
    signaler = initialized_signaler()
    start_ms = interval_ms("1h") * 13
    stop_ms = interval_ms("1h") * 19
    signaler.load(StaticLoader(signal_frame(13)), start_ms, stop_ms)

    assert signaler.crossover.warmup_bars == 13
    assert signaler.crossover.start_ms == start_ms - interval_ms("1h") * 13
    assert signaler.crossover.stop_ms == stop_ms


def check_picks_latest_closed_row() -> None:
    signaler = initialized_signaler()
    signaler.load(StaticLoader(signal_frame(13)), 0, 0)
    signaler.calc()

    frame = signaler.crossover.frame
    cross = frame.filter(pl.col("sw_enter_long")).tail(1).row(0, named=True)
    next_close_ms = int(cross["close_ms"]) + interval_ms("1h")

    signal = signaler.check(next_close_ms - 1)
    assert signal.enter_long
    assert signal.reason == "ema_cross_up"


def rejects_stale_check_time() -> None:
    signaler = initialized_signaler()
    data = signaler.crossover
    signaler.load(StaticLoader(signal_frame(13)), 0, 0)
    signaler.calc()

    frame = data.frame
    close_ms = int(frame.tail(1).row(0, named=True)["close_ms"])
    try:
        signaler.check(close_ms + data.max_age_ms + 1)
    except RuntimeError as exc:
        assert "stale SwEmacross signal" in str(exc)
    else:
        raise AssertionError("SwEmacross accepted stale check time")


def chart_display_returns_ema_lines_and_signal_markers() -> None:
    interval = interval_ms("1h")
    start_ms = interval * 13
    stop_ms = interval * 19
    rows = signal_frame(13).iter_rows(named=True)
    candles = [dict(row) for row in rows]

    def load_candles(start: int, stop: int) -> list[dict]:
        return [row for row in candles if start <= row["ts_ms"] <= stop]

    display = chart_display(
        {"name": "emacross", "interval": "1h", "params": {"fast": 2, "slow": 3}},
        load_candles,
        start_ms,
        stop_ms,
    )

    assert display["source"] == "regenerated"
    assert [line["name"] for line in display["lines"]] == ["EMA 2", "EMA 3"]
    assert len(display["lines"][0]["data"]) == 7
    assert any(marker["reason"] == "ema_cross_up" for marker in display["markers"])
    long_marker = next(marker for marker in display["markers"] if marker["reason"] == "ema_cross_up")
    marker_index = long_marker["value"][0]
    assert long_marker["value"][1] < candles[marker_index + 13]["low"]
    candle = candles[marker_index + 13]
    assert long_marker["value"][1] == round(candle["low"] - candle["close"] * 0.02, 8)


def initialized_signaler() -> SwEmacross:
    signaler = SwEmacross()
    signaler.init(SignalerConfig(name="emacross", interval="1h", params={"fast": 2, "slow": 3}), "SOLUSDT")
    return signaler


class StaticLoader:
    def __init__(self, frame: pl.DataFrame) -> None:
        self.frame = frame

    def load(self, data) -> pl.DataFrame:
        return self.frame


def signal_frame(warmup_bars: int) -> pl.DataFrame:
    interval = interval_ms("1h")
    closes = [
        20,
        19,
        18,
        17,
        16,
        15,
        14,
        13,
        12,
        11,
        10,
        9,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
    ]
    rows = []
    for index, close in enumerate(closes):
        ts_ms = index * interval
        rows.append(
            {
                "ts_ms": ts_ms,
                "open": float(close),
                "high": float(close),
                "low": float(close),
                "close": float(close),
                "volume": 1.0,
                "closed": True,
                "close_ms": ts_ms + interval,
                "is_active": index >= warmup_bars,
            }
        )
    return pl.DataFrame(rows)


if __name__ == "__main__":
    main()
