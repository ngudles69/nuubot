from __future__ import annotations

import argparse
import json
from statistics import mean, median

from tabulate import tabulate

from nuubot.datastore import SweeprunRow, dbname
from nuubot.nuubot import nuubot_setup
from nuubot.server.sweepmgr import sweepmgr_setup


def main() -> None:
    args = parse_args()
    bot = nuubot_setup()
    manager = sweepmgr_setup(bot)
    metrics = manager.metrics(args.sweep_id)
    rows = bot.datastore.select(dbname(args.sweep_id, "sweep"), SweeprunRow, sweep_id=args.sweep_id)
    performance = [json.loads(row.results_json or "{}").get("performance", {}) for row in rows]
    timing = metrics["results"].get("timing") or metrics["results"].get("telemetry", {}).get("timing", {})

    print_table("sweep", [
        ("sweep_id", metrics["sweep_id"]),
        ("status", metrics["status"]),
        ("progress", metrics["progress"]),
        ("sweepruns", metrics["sweeprun_count"]),
        ("db", metrics["db_path"]),
    ])
    print_table("counts", [(key, metrics[key]) for key in ("account_count", "botrun_count", "signal_count", "position_count", "order_count", "fill_count")])
    print_table("performance", [
        ("win_loss", metrics["win_loss"]),
        ("profit_factor", metrics["profit_factor"]),
        ("ev", metrics["ev"]),
        ("pnl_pct", number_stats([row.get("pnl_pct") for row in performance])),
        ("trades", sum_int(row.get("trades") for row in performance)),
        ("cycles", sum_int(row.get("cycles") for row in performance)),
        ("wins", sum_int(row.get("wins") for row in performance)),
        ("losses", sum_int(row.get("losses") for row in performance)),
        ("bars", sum_int(row.get("bars") for row in performance)),
    ])
    print_table("timing", [(key, timing.get(key, "-")) for key in ("total_ms", "bars", "bars_per_second", "worker_count")])
    print_timing_stats(metrics["telemetry"].get("sweepruns", {}))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m nuubot.sweep")
    parser.add_argument("sweep_id", type=int)
    return parser.parse_args()


def print_table(title: str, rows: list[tuple[str, object]]) -> None:
    print(f"\n{title}")
    print(tabulate(rows, headers=("metric", "value"), tablefmt="github"))


def print_timing_stats(stats_by_key: dict[str, dict[str, float]]) -> None:
    rows = [
        (key, stats["min"], stats["mean"], stats["median"], stats["max"])
        for key, stats in stats_by_key.items()
    ]
    print("\ntiming stats")
    print(tabulate(rows, headers=("metric", "min", "mean", "median", "max"), tablefmt="github"))


def number_stats(values: list[object]) -> str:
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    if not numbers:
        return "-"
    return f"sum={sum(numbers):+.4f} min={min(numbers):+.4f} mean={mean(numbers):+.4f} median={median(numbers):+.4f} max={max(numbers):+.4f}"


def sum_int(values: object) -> int:
    return sum(int(value) for value in values if isinstance(value, int | float))


if __name__ == "__main__":
    main()
