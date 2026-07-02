from __future__ import annotations

from tempfile import TemporaryDirectory
from pathlib import Path

from nuubot.core.data_loader import binance_files, month_keys
from nuubot.core.market_data import date_ms


def main() -> None:
    prefers_zip_over_csv_for_same_month()
    filters_files_by_month()
    builds_inclusive_month_keys()


def prefers_zip_over_csv_for_same_month() -> None:
    with TemporaryDirectory() as root:
        path = Path(root)
        (path / "BTCUSDT-1h-2025-01.csv").write_text("", encoding="utf-8")
        (path / "BTCUSDT-1h-2025-01.zip").write_text("", encoding="utf-8")
        (path / "BTCUSDT-1h-2025-01.zip.CHECKSUM").write_text("", encoding="utf-8")
        (path / "BTCUSDT-1h-2025-02.csv").write_text("", encoding="utf-8")

        files = binance_files(path, "BTCUSDT", "1h")
        assert [item.name for item in files] == ["BTCUSDT-1h-2025-01.zip", "BTCUSDT-1h-2025-02.csv"]


def filters_files_by_month() -> None:
    with TemporaryDirectory() as root:
        path = Path(root)
        (path / "BTCUSDT-1h-2024-12.zip").write_text("", encoding="utf-8")
        (path / "BTCUSDT-1h-2025-01.zip").write_text("", encoding="utf-8")
        (path / "BTCUSDT-1h-2025-02.zip").write_text("", encoding="utf-8")

        files = binance_files(path, "BTCUSDT", "1h", {"2024-12", "2025-01"})
        assert [item.name for item in files] == ["BTCUSDT-1h-2024-12.zip", "BTCUSDT-1h-2025-01.zip"]


def builds_inclusive_month_keys() -> None:
    keys = month_keys(date_ms("2024-12-30"), date_ms("2025-02-01"))
    assert keys == {"2024-12", "2025-01", "2025-02"}


if __name__ == "__main__":
    main()
