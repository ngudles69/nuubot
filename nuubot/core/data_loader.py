from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from nuubot.core.dtypes import Bar, SwData
from nuubot.core.market_data import interval_ms, read_binance_file


class DataLoader:
    def __init__(self, data_dir: str) -> None:
        self.data_dir = Path(data_dir)

    def load(self, data: SwData) -> pl.DataFrame:
        """Load one market dataset into a Polars dataframe."""

        interval = interval_ms(data.timeframe.value)
        active_start_ms = data.start_ms + interval * data.warmup_bars

        # Locate source files.
        root = self.data_dir / data.symbol / data.timeframe.value
        if not root.exists():
            raise FileNotFoundError(f"missing Binance data folder: {root}")

        # Load rows.
        rows = []
        for path in binance_files(root, data.symbol, data.timeframe.value, month_keys(data.start_ms, data.stop_ms)):
            for bar in read_binance_file(path):
                rows.append((bar.ts_ms, bar.open, bar.high, bar.low, bar.close, bar.volume, bar.closed))
        if not rows:
            raise RuntimeError(f"no Binance rows loaded for {data.symbol} {data.timeframe}")

        # Build frame.
        frame = pl.DataFrame(rows, schema=["ts_ms", "open", "high", "low", "close", "volume", "closed"], orient="row")
        frame = frame.sort("ts_ms")

        # Filter rows.
        frame = frame.filter((pl.col("ts_ms") >= data.start_ms) & (pl.col("ts_ms") <= data.stop_ms))
        if frame.filter((pl.col("ts_ms") >= active_start_ms) & (pl.col("ts_ms") <= data.stop_ms)).height == 0:
            raise RuntimeError(f"no Binance bars matched {data.symbol} {data.timeframe}")

        # Validate frame.
        if frame.get_column("ts_ms").n_unique() != frame.height:
            raise RuntimeError(f"duplicate bar timestamps for {data.symbol} {data.timeframe}")
        if not frame.get_column("closed").all():
            raise RuntimeError(f"open bars loaded for {data.symbol} {data.timeframe}")

        # Mark active bars and their close time.
        frame = frame.with_columns(
            (pl.col("ts_ms") + interval).alias("close_ms"),
            (pl.col("ts_ms") >= active_start_ms).alias("is_active"),
        )

        return frame


def binance_files(root: Path, symbol: str, timeframe: str, months: set[str] | None = None) -> list[Path]:
    files: dict[str, Path] = {}
    prefix = f"{symbol}-{timeframe}-"
    for path in sorted(root.glob(f"{prefix}*")):
        if path.suffix not in {".zip", ".csv"}:
            continue
        stem = path.name.removesuffix(path.suffix)
        month = stem.removeprefix(prefix)
        if months is not None and month not in months:
            continue
        if path.suffix == ".zip" or stem not in files:
            files[stem] = path
    return [files[key] for key in sorted(files)]


def month_keys(start_ms: int, stop_ms: int) -> set[str]:
    start = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    stop = datetime.fromtimestamp(stop_ms / 1000, tz=timezone.utc)
    year = start.year
    month = start.month
    keys = set()
    while (year, month) <= (stop.year, stop.month):
        keys.add(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return keys


def bars_from_frame(frame: pl.DataFrame) -> list[Bar]:
    return [
        Bar(
            ts_ms=int(row["ts_ms"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            closed=bool(row["closed"]),
        )
        for row in frame.iter_rows(named=True)
    ]
