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
    print_report(args.sweep_id)


def print_report(sweep_id: int) -> None:
    bot = nuubot_setup()
    try:
        manager = sweepmgr_setup(bot)
        metrics = manager.metrics(sweep_id)
        rows = bot.datastore.select(dbname(sweep_id, "sweep"), SweeprunRow, sweep_id=sweep_id)
        summaries = [sweeprun_summary(row) for row in rows]
        performance = [performance_metrics(row) for row in rows]
        pnls = [row.get("pnl_pct") for row in performance]
        net_pnls = [row.get("net_pnl_usdc") for row in performance]
        ending_balances = [row.get("ending_balance_usdc") for row in performance]
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
            ("pnl_pct", number_stats(pnls)),
            ("net_pnl_usdc", number_stats(net_pnls)),
            ("ending_balance_usdc", number_stats(ending_balances)),
            ("spread", spread(pnls)),
            ("read", investigation_read(pnls)),
            ("trades", sum_int(row.get("trades") for row in performance)),
            ("cycles", sum_int(row.get("cycles") for row in performance)),
            ("wins", sum_int(row.get("wins") for row in performance)),
            ("losses", sum_int(row.get("losses") for row in performance)),
            ("ticks", sum_int(row.get("ticks") for row in performance)),
        ])
        print_sweepruns("best sweepruns", sorted(summaries, key=lambda row: row["pnl_pct"], reverse=True)[:5])
        print_sweepruns("worst sweepruns", sorted(summaries, key=lambda row: row["pnl_pct"])[:5])
        print_table("timing", [(key, timing.get(key, "-")) for key in ("total_ms", "ticks", "ticks_per_second", "worker_count")])
        print_timing_stats(metrics["telemetry"].get("sweepruns", {}))
    finally:
        bot.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m nuubot.sweeps.report")
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


def print_sweepruns(title: str, rows: list[dict[str, object]]) -> None:
    print(f"\n{title}")
    print(tabulate(rows, headers="keys", tablefmt="github", floatfmt=".4f"))


def sweeprun_summary(row: SweeprunRow) -> dict[str, object]:
    config = json.loads(row.config_json or "{}")
    performance = performance_metrics(row)
    signaler = config.get("signaler", {})
    executor = config.get("executor", {})
    params = signaler.get("params", {})
    sweeprun = config.get("sweeprun", {})
    return {
        "sweeprun": row.sweeprun_id,
        "pnl_pct": float(performance.get("pnl_pct") or 0),
        "net_pnl": float(performance.get("net_pnl_usdc") or 0),
        "end_balance": float(performance.get("ending_balance_usdc") or 0),
        "trade_usdc": float(performance.get("trade_usdc") or 0),
        "trades": int(performance.get("trades") or 0),
        "wins": int(performance.get("wins") or 0),
        "losses": int(performance.get("losses") or 0),
        "symbol": executor.get("symbol", ""),
        "fast": params.get("fast", ""),
        "slow": params.get("slow", ""),
        "period": f"{sweeprun.get('start', '')}..{sweeprun.get('end', '')}",
    }


def performance_metrics(row: SweeprunRow) -> dict[str, object]:
    return json.loads(row.results_json or "{}").get("performance", {})


def number_stats(values: list[object]) -> str:
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    if not numbers:
        return "-"
    return f"min={min(numbers):+.4f} mean={mean(numbers):+.4f} median={median(numbers):+.4f} max={max(numbers):+.4f}"


def spread(values: list[object]) -> str:
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    if not numbers:
        return "-"
    return f"{max(numbers) - min(numbers):.4f}"


def investigation_read(values: list[object]) -> str:
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    if not numbers:
        return "-"
    if mean(numbers) > 0 and median(numbers) > 0:
        return "worth deeper review"
    if max(numbers) > 0:
        return "only isolated configs worked"
    return "weak sweep"


def sum_int(values: object) -> int:
    return sum(int(value) for value in values if isinstance(value, int | float))


if __name__ == "__main__":
    main()
