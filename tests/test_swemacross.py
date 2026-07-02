from __future__ import annotations

import polars as pl

from nuubot.core.dtypes import Timeframe
from nuubot.core.market_data import interval_ms
from nuubot.core.models.mconfig import SignalerConfig
from nuubot.sweeps.signalers import SwEmacross


def main() -> None:
    validates_timeframe()
    calculates_and_checks_latest_closed_bar()
    rejects_stale_check_time()


def validates_timeframe() -> None:
    try:
        signaler = SwEmacross()
        signaler.init(SignalerConfig(name="emacross", interval="3m", params={"fast": 2, "slow": 3}))
    except ValueError as exc:
        assert "3m" in str(exc)
    else:
        raise AssertionError("SwEmacross accepted unsupported timeframe")


def calculates_and_checks_latest_closed_bar() -> None:
    signaler = initialized_signaler()
    data = signaler.data_req("SOLUSDT")[0]
    assert data.name == "trade"
    assert data.symbol == "SOLUSDT"
    assert data.timeframe == Timeframe.H1
    assert data.warmup_bars == 13

    data.frame = signal_frame(signaler.warmup_bars)
    data.max_age_ms = interval_ms(data.timeframe.value) * 2
    signaler.load()
    signaler.calc()

    frame = data.frame
    assert frame is not None
    cross = frame.filter(pl.col("sw_enter_long")).tail(1)
    assert cross.height == 1

    row = cross.row(0, named=True)
    signal = signaler.check(int(row["close_ms"]))
    assert signal.enter_long
    assert not signal.enter_short
    assert not signal.exit_long
    assert signal.exit_short
    assert signal.reason == "ema_cross_up"


def rejects_stale_check_time() -> None:
    signaler = initialized_signaler()
    data = signaler.data_req("SOLUSDT")[0]
    data.frame = signal_frame(signaler.warmup_bars)
    data.max_age_ms = interval_ms(data.timeframe.value) * 2
    signaler.load()
    signaler.calc()

    frame = data.frame
    assert frame is not None
    close_ms = int(frame.tail(1).row(0, named=True)["close_ms"])
    try:
        signaler.check(close_ms + data.max_age_ms + 1)
    except RuntimeError as exc:
        assert "stale SwEmacross signal" in str(exc)
    else:
        raise AssertionError("SwEmacross accepted stale check time")


def initialized_signaler() -> SwEmacross:
    signaler = SwEmacross()
    signaler.init(SignalerConfig(name="emacross", interval="1h", params={"fast": 2, "slow": 3}))
    return signaler


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
