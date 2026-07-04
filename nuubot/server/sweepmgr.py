from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from math import sqrt
from statistics import mean, median
import threading
import tomllib
from typing import Any

from nuubot.datastore import AccountRow, BotrunRow, EventRow, FillRow, OrderRow, PositionRow, SweeprunRow, SweepRow, dbname
from nuubot.core.data_loader import binance_files, month_keys
from nuubot.core.market_data import date_ms, read_binance_file
from nuubot.nuubot import Nuubot
from nuubot.sweeps.executors import chart_display as executor_chart_display
from nuubot.sweeps.signalers.signaler import chart_display as signaler_chart_display
from nuubot.sweeps.sweep import Sweep, ensure_executor_accounts_exist
from nuubot.sweeps.template import expand_sweep_template, generate_sweepruns

SWEEP_DB_RE = re.compile(r"^sweep_(\d+)\.db$")


@dataclass
class SweepManager:
    nuubot: Nuubot
    result_threads: dict[int, threading.Thread]
    run_lock: threading.Lock

    def create(self, template: str | dict[str, Any]) -> int:
        """Create a configured sweep DB from a template."""

        # Parse template.
        template_data = self.parse_template(template)

        # Create sweep DB.
        sweep_id = self.nuubot.datastore.next_seq(self.nuubot.server_db, "sweep")
        db = dbname(sweep_id, "sweep")
        self.nuubot.datastore.dbinit(db)

        # Save sweep row.
        sweep = template_data.get("sweep", {})
        self.nuubot.datastore.insert(
            db,
            SweepRow(
                sweep_id=sweep_id,
                sweep_desc=str(sweep.get("description") or sweep.get("desc") or "sweep"),
                config_json=json.dumps(template_data, sort_keys=True, separators=(",", ":")),
                results_json="{}",
                status="configured",
                sweeprun_count=0,
            )
        )
        return sweep_id

    def list(self) -> dict[str, Any]:
        db_dir = self.nuubot.datastore.dbroot
        if db_dir is None:
            raise RuntimeError("datastore DB root missing")
        rows: list[dict[str, Any]] = []
        for path in sorted(db_dir.glob("sweep_*.db"), key=_extract_sweep_id):
            rows.append(self._list_sweep(path))
        return {"sweeps": rows}

    def list_archives(self) -> dict[str, Any]:
        if self.nuubot.datastore.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        archive_dir = self.nuubot.datastore.dbroot / "archived"
        rows = []
        if archive_dir.exists():
            for path in sorted(archive_dir.glob("sweep_*.db"), key=_extract_sweep_id):
                rows.append(self._list_sweep(path, archived=True))
        return {"sweeps": rows}

    def load(self, sweep_id: int) -> dict[str, Any]:
        db = dbname(sweep_id, "sweep")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        sweep = self.nuubot.datastore.get(db, SweepRow, sweep_id=sweep_id)
        config = json.loads(sweep.config_json)
        return config

    def update(self, sweep_id: int, template: str | dict[str, Any]) -> None:
        """Replace a configured sweep template."""

        # Validate sweep.
        db = dbname(sweep_id, "sweep")
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")

        # Parse template.
        template_data = self.parse_template(template)

        # Save sweep config.
        with self.run_lock:
            tx = self.nuubot.datastore.tx(db)
            tx.start()
            try:
                sweep = tx.get(SweepRow, sweep_id=sweep_id)
                if sweep.status in {"queued", "running", "submitted"}:
                    raise RuntimeError(f"cannot edit active sweep: {sweep_id}")
                for row_class in (FillRow, OrderRow, PositionRow, EventRow, AccountRow, BotrunRow, SweeprunRow):
                    tx.delete(row_class)
                sweep.config_json = json.dumps(template_data, sort_keys=True, separators=(",", ":"))
                sweep.results_json = "{}"
                sweep.status = "configured"
                sweep.sweeprun_count = 0
                sweep.error_code = None
                sweep.error_text = None
                tx.commit()
            except Exception:
                tx.rollback()
                raise
            finally:
                tx.close()

    def clone(self, sweep_id: int) -> int:
        source = self.load(sweep_id)
        return self.create(source)

    def delete(self, sweep_id: int) -> None:
        db = dbname(sweep_id, "sweep")
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        with self.run_lock:
            sweep = self.nuubot.datastore.get(db, SweepRow, sweep_id=sweep_id)
            if sweep.status in {"queued", "running", "submitted"}:
                raise RuntimeError(f"cannot delete active sweep: {sweep_id}")
            self.nuubot.datastore.drop(db)

    def metrics(self, sweep_id: int, archived: bool = False) -> dict[str, Any]:
        """Return sweep status, performance, and telemetry."""

        # Validate sweep.
        db = dbname(sweep_id, "sweep")
        if self.nuubot.datastore.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        path = self.nuubot.datastore.dbroot / "archived" / db if archived else self.nuubot.datastore.dbpath(db)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not path.exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        sweep = self.nuubot.datastore.get(path, SweepRow, sweep_id=sweep_id)
        rows = self.nuubot.datastore.select(path, SweeprunRow, sweep_id=sweep_id)

        # Calculate run counts.
        counts = {
            status: sum(1 for row in rows if row.status == status)
            for status in ("queued", "running", "complete", "failed")
        }
        done_count = int(counts["complete"] + counts["failed"])
        total_count = int(sum(counts.values()))
        status = "archived" if archived else sweep.status
        progress = "" if archived else f"{done_count}/{total_count}"

        # Load result metrics.
        results = json.loads(sweep.results_json or "{}")
        pnl = _pnl_metrics(rows)

        # Collect timing metrics.
        timing_values: dict[str, list[float]] = {}
        for row in rows:
            result = json.loads(row.results_json or "{}")
            for key, value in result.get("telemetry", {}).get("timing", {}).items():
                if isinstance(value, int | float):
                    timing_values.setdefault(key, []).append(value)
        telemetry = {
            "sweep": results.get("telemetry", {}),
            "sweepruns": {key: _timing_stats(items) for key, items in sorted(timing_values.items())},
        }

        config = json.loads(sweep.config_json or "{}")
        sweep_config = config.get("sweep", {})
        return {
            "sweep_id": sweep_id,
            "name": str(sweep_config.get("name") or f"sweep-{sweep.sweep_id}"),
            "sweep_desc": sweep.sweep_desc,
            "status": status,
            "queued_count": int(counts["queued"]),
            "running_count": int(counts["running"]),
            "complete_count": int(counts["complete"]),
            "failed_count": int(counts["failed"]),
            "done_count": done_count,
            "total_count": total_count,
            "progress": progress,
            "sweeprun_count": len(rows),
            "account_count": self.nuubot.datastore.count(path, AccountRow),
            "botrun_count": self.nuubot.datastore.count(path, BotrunRow),
            "event_count": self.nuubot.datastore.count(path, EventRow),
            "signal_count": self.nuubot.datastore.count(path, EventRow, event="signal"),
            "position_count": self.nuubot.datastore.count(path, PositionRow),
            "order_count": self.nuubot.datastore.count(path, OrderRow),
            "fill_count": self.nuubot.datastore.count(path, FillRow),
            "win_loss": pnl["win_loss"],
            "profit_factor": pnl["profit_factor"],
            "ev": pnl["ev"],
            "created_at": sweep.created_at.isoformat() if sweep.created_at else "",
            "updated_at": sweep.updated_at.isoformat() if sweep.updated_at else "",
            "db_path": str(path),
            "results": results,
            "telemetry": telemetry,
        }

    def detail(self, sweep_id: int, archived: bool = False) -> dict[str, Any]:
        """Return sweep metrics plus one row per sweeprun."""

        path = self._sweep_path(sweep_id, archived)
        metrics = self.metrics(sweep_id, archived)
        rows = self.nuubot.datastore.select(path, SweeprunRow, sweep_id=sweep_id)
        metrics["sweepruns"] = [self._sweeprun_summary(row) for row in sorted(rows, key=lambda item: item.sweeprun_id)]
        return metrics

    def sweeprun_chart(self, sweep_id: int, sweeprun_id: int, archived: bool = False) -> dict[str, Any]:
        """Return OHLC candles and chart display payloads for one sweeprun."""

        path = self._sweep_path(sweep_id, archived)
        row = self.nuubot.datastore.get(path, SweeprunRow, sweep_id=sweep_id, sweeprun_id=sweeprun_id)
        config = json.loads(row.config_json or "{}")
        sweep_run = config.get("sweeprun", {})
        executor = config.get("executor", {})
        symbol = str(executor.get("symbol") or "")
        interval = str(executor.get("interval") or "")
        start_ms = date_ms(str(sweep_run.get("start")))
        stop_ms = date_ms(str(sweep_run.get("end")))
        data_dir = self._workspace_path(str(sweep_run.get("data_dir") or ""))
        candles = self._chart_candles(data_dir, symbol, interval, start_ms, stop_ms)
        positions = self.nuubot.datastore.select(path, PositionRow, sweeprun_id=sweeprun_id)
        orders = self.nuubot.datastore.select(path, OrderRow, sweeprun_id=sweeprun_id)
        fills = self.nuubot.datastore.select(path, FillRow, sweeprun_id=sweeprun_id)
        botruns = self.nuubot.datastore.select(path, BotrunRow, sweeprun_id=sweeprun_id)
        timestamps = [item["ts_ms"] for item in candles]
        indicators = signaler_chart_display(
            config.get("signaler", {}),
            lambda start, stop: self._chart_candles(data_dir, symbol, interval, start, stop),
            start_ms,
            stop_ms,
        )
        indicators["markers"] = _signal_markers_from_events(self.nuubot.datastore.select(path, EventRow, event="signal"), sweeprun_id, timestamps)
        indicators["marker_source"] = "persisted_events"
        executor_display = executor_chart_display(config.get("executor", {}), positions, orders, timestamps)

        return {
            "sweep_id": sweep_id,
            "sweeprun": self._sweeprun_summary(row),
            "symbol": symbol,
            "interval": interval,
            "categories": [_chart_time(item["ts_ms"]) for item in candles],
            "candles": [[item["open"], item["close"], item["low"], item["high"]] for item in candles],
            "ohlcv": candles,
            "executor_display": executor_display,
            "indicators": indicators,
            "summary_groups": _chart_summary_groups(row, positions, indicators),
            "tables": _chart_tables(config, positions, orders, fills, botruns),
        }

    def run(self, sweep_id: int) -> dict[str, Any]:
        if self.nuubot.datastore is None:
            raise RuntimeError("nuubot datastore missing")
        db = dbname(sweep_id, "sweep")
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        account_names = {account.name for account in self.nuubot.config.credentials.hyperliquid.accounts}
        return Sweep(self.nuubot.datastore, sweep_id, self.result_threads, self.run_lock, account_names).run()

    def _sweep_path(self, sweep_id: int, archived: bool = False) -> Path:
        db = dbname(sweep_id, "sweep")
        if self.nuubot.datastore.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        path = self.nuubot.datastore.dbroot / "archived" / db if archived else self.nuubot.datastore.dbpath(db)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not path.exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        return path

    def _sweeprun_summary(self, row: SweeprunRow) -> dict[str, Any]:
        config = json.loads(row.config_json or "{}")
        result = json.loads(row.results_json or "{}")
        executor = config.get("executor", {})
        signaler = config.get("signaler", {})
        performance = result.get("performance", {})
        return {
            "sweeprun_id": row.sweeprun_id,
            "sweeprun_index": row.sweeprun_index,
            "status": row.status,
            "symbol": executor.get("symbol", ""),
            "interval": executor.get("interval", ""),
            "signaler": signaler.get("name", ""),
            "params": signaler.get("params", {}),
            "pnl_pct": _fmt_pct(performance.get("pnl_pct")),
            "trades": performance.get("trades", 0),
            "wins": performance.get("wins", 0),
            "losses": performance.get("losses", 0),
            "ticks": performance.get("ticks", 0),
            "error": row.error_text or "",
        }

    def _chart_candles(self, data_dir: Path, symbol: str, interval: str, start_ms: int, stop_ms: int) -> list[dict[str, Any]]:
        root = data_dir / symbol / interval
        if not root.exists():
            raise FileNotFoundError(f"missing Binance data folder: {root}")

        candles = []
        for path in binance_files(root, symbol, interval, month_keys(start_ms, stop_ms)):
            for bar in read_binance_file(path):
                if start_ms <= bar.ts_ms <= stop_ms:
                    candles.append({
                        "ts_ms": bar.ts_ms,
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    })
        if not candles:
            raise RuntimeError(f"no chart candles matched {symbol} {interval}")
        return sorted(candles, key=lambda item: item["ts_ms"])

    def _workspace_path(self, path: str) -> Path:
        value = Path(path)
        if value.is_absolute():
            return value
        return Path(self.nuubot.config.workspace.root) / value

    def parse_template(self, template: str | dict[str, Any]) -> dict[str, Any]:
        """Parse a JSON, TOML, or dict sweep template."""

        # Parse source.
        if isinstance(template, str):
            text = template.strip()
            if text.startswith("{"):
                data = json.loads(text)
                if not isinstance(data, dict):
                    raise TypeError("JSON template must be an object")
            else:
                data = tomllib.loads(template)
        else:
            data = template

        # Expand template.
        data_dir = f"{self.nuubot.config.paths.data_dir}/binance/raw/spot/monthly/klines"
        template_data = expand_sweep_template(data, data_dir)
        account_names = {account.name for account in self.nuubot.config.credentials.hyperliquid.accounts}
        ensure_executor_accounts_exist(generate_sweepruns(template_data), account_names)
        return template_data

    def _list_sweep(self, path: Path, archived: bool = False) -> dict[str, Any]:
        """Build one sweep list row."""

        # Load sweep rows.
        sweep_id = _extract_sweep_id(path)
        row = self.nuubot.datastore.get(path, SweepRow, sweep_id=sweep_id)
        config = json.loads(row.config_json or "{}")
        sweep = config.get("sweep", {})
        rows = self.nuubot.datastore.select(path, SweeprunRow, sweep_id=sweep_id)
        pnl = _pnl_metrics(rows)
        counts = {
            status: sum(1 for run in rows if run.status == status)
            for status in ("queued", "running", "complete", "failed")
        }
        done_count = row.sweeprun_count if archived else int(counts["complete"] + counts["failed"])
        total_count = row.sweeprun_count if archived else int(sum(counts.values()))
        return {
            "sweep_id": row.sweep_id,
            "name": str(sweep.get("name") or f"sweep-{row.sweep_id}"),
            "sweep_desc": row.sweep_desc,
            "status": "archived" if archived else row.status,
            "progress": "" if archived else f"{done_count}/{total_count}",
            "queued_count": int(counts["queued"]),
            "running_count": int(counts["running"]),
            "complete_count": int(counts["complete"]),
            "failed_count": int(counts["failed"]),
            "done_count": done_count,
            "total_count": total_count,
            "sweeprun_count": row.sweeprun_count,
            "win_loss": pnl["win_loss"],
            "profit_factor": pnl["profit_factor"],
            "ev": pnl["ev"],
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            "db_path": str(path),
        }

    def archive(self, sweep_id: int) -> None:
        """Move an inactive sweep DB to archives."""

        # Validate paths.
        db = dbname(sweep_id, "sweep")
        if self.nuubot.datastore.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        source = self.nuubot.datastore.dbpath(db)
        target = self.nuubot.datastore.dbroot / "archived" / db
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not source.exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        if target.exists():
            raise RuntimeError(f"sweep already archived: {sweep_id}")

        # Move sweep DB.
        with self.run_lock:
            sweep = self.nuubot.datastore.get(source, SweepRow, sweep_id=sweep_id)
            if sweep.status in {"queued", "running", "submitted"}:
                raise RuntimeError(f"cannot archive active sweep: {sweep_id}")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)

    def unarchive(self, sweep_id: int) -> None:
        """Move an archived sweep DB back to active sweeps."""

        # Validate paths.
        db = dbname(sweep_id, "sweep")
        if self.nuubot.datastore.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        source = self.nuubot.datastore.dbroot / "archived" / db
        target = self.nuubot.datastore.dbpath(db)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not source.exists():
            raise RuntimeError(f"archived sweep DB missing: {db}")
        if target.exists():
            raise RuntimeError(f"sweep already active: {sweep_id}")

        # Move sweep DB.
        with self.run_lock:
            source.replace(target)


def sweepmgr_setup(nuubot: Nuubot) -> SweepManager:
    if nuubot.config is None or nuubot.datastore is None:
        raise RuntimeError("nuubot_setup() must complete before sweepmgr_setup()")
    return SweepManager(nuubot, {}, threading.Lock())


def _extract_sweep_id(path: Path) -> int:
    match = SWEEP_DB_RE.match(path.name)
    if match is None:
        raise RuntimeError(f"invalid sweep DB name: {path.name}")
    return int(match.group(1))


def _timing_stats(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(mean(values), 2),
        "median": median(values),
    }


def _pnl_metrics(rows: list[SweeprunRow]) -> dict[str, str]:
    """Calculate sweep PnL display metrics."""

    # Collect PnL.
    pnls = []
    for row in rows:
        result = json.loads(row.results_json or "{}")
        pnl = result.get("performance", {}).get("pnl_pct")
        if isinstance(pnl, int | float):
            pnls.append(float(pnl))
    if not pnls:
        return {"win_loss": "-", "profit_factor": "-", "ev": "-"}

    # Calculate summary.
    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = sum(1 for pnl in pnls if pnl < 0)
    gross_win = sum(pnl for pnl in pnls if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in pnls if pnl < 0))
    win_rate = wins / len(pnls) * 100
    profit_factor = gross_win / gross_loss if gross_loss else None
    ev = mean(pnls)
    return {
        "win_loss": f"{wins}/{len(pnls)} ({win_rate:.1f}%)",
        "profit_factor": "inf" if profit_factor is None and gross_win > 0 else ("-" if profit_factor is None else f"{profit_factor:.2f}"),
        "ev": f"{ev:+.2f}%",
    }


def _fmt_pct(value: object) -> str:
    if not isinstance(value, int | float):
        return "-"
    return f"{float(value):+.2f}%"


def _fmt_count(value: object) -> str:
    if not isinstance(value, int | float):
        return "-"
    return f"{int(value):,}"


def _fmt_money(value: object) -> str:
    if not isinstance(value, int | float):
        return "-"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{float(value):,.2f}"


def _fmt_decimal(value: object, places: int = 2) -> str:
    if value in (None, ""):
        return ""
    return f"{float(value):,.{places}f}"


def _fmt_ratio(value: object) -> str:
    if not isinstance(value, int | float):
        return "-"
    return f"{float(value):.2f}"


def _summary_item(label: str, value: object, title: str = "", tone: str = "") -> dict[str, str]:
    return {"label": label, "value": str(value), "title": title, "tone": tone}


def _chart_summary_groups(row: SweeprunRow, positions: list[PositionRow], indicators: dict[str, Any]) -> list[dict[str, Any]]:
    config = json.loads(row.config_json or "{}")
    result = json.loads(row.results_json or "{}")
    sweep_run = config.get("sweeprun", {})
    executor = config.get("executor", {})
    signaler = config.get("signaler", {})
    performance = result.get("performance", {})
    trades = _trade_summary(positions)
    pnl_pct = performance.get("pnl_pct")
    pnl_tone = "positive" if isinstance(pnl_pct, int | float) and pnl_pct >= 0 else "negative"
    start = str(sweep_run.get("start") or "")
    end = str(sweep_run.get("end") or "")
    return [
        {
            "title": "Info",
            "items": [
                _summary_item("Market", f"{executor.get('symbol', '')} {executor.get('interval', '')}".strip()),
                _summary_item("Duration", _fmt_duration(start, end)),
                _summary_item("Start", _fmt_config_date(start)),
                _summary_item("End", _fmt_config_date(end)),
                _summary_item("Signaler", signaler.get("name", ""), json.dumps(signaler.get("params", {}), sort_keys=True)),
                _summary_item("Executor", executor.get("name", ""), json.dumps({k: v for k, v in executor.items() if k != "name"}, sort_keys=True)),
                _summary_item("Bots", _fmt_count(performance.get("cycles"))),
            ],
        },
        {
            "title": "Performance",
            "items": [
                _summary_item("PnL", f"{_fmt_money(trades['net_pnl'])} ({_fmt_pct(pnl_pct)})", tone=pnl_tone),
                _summary_item("Max DD", _fmt_pct_value(performance.get("max_drawdown_pct")), tone="negative"),
                _summary_item("Expected Value", _fmt_money(trades["ev"])),
                _summary_item("Avg Win", _fmt_money(trades["avg_win"]), tone="positive"),
                _summary_item("Avg Loss", _fmt_money(trades["avg_loss"]), tone="negative"),
            ],
        },
        {
            "title": "Ratios",
            "items": [
                _summary_item("Profit Factor", _fmt_ratio(trades["profit_factor"])),
                _summary_item("Trade Sharpe", _fmt_ratio(trades["trade_sharpe"])),
                _summary_item("Payoff Ratio", _fmt_ratio(trades["payoff_ratio"])),
            ],
        },
        {
            "title": "PnL / Win Rate",
            "items": [
                _summary_item("PnL", f"{_fmt_money(trades['net_pnl'])} ({_fmt_pct(pnl_pct)})", tone=pnl_tone),
                _summary_item("Win Rate", f"{_fmt_count(performance.get('wins'))}/{_fmt_count(performance.get('trades'))} ({_fmt_pct_value(trades['win_rate'])})"),
                _summary_item("Trades", _fmt_count(performance.get("trades"))),
                _summary_item("Signals", _fmt_count(result.get("signal_events"))),
                _summary_item("Ticks", _fmt_count(performance.get("ticks"))),
            ],
        },
        {
            "title": "Wins",
            "items": [
                _summary_item("Wins", _fmt_count(performance.get("wins")), tone="positive"),
                _summary_item("Win Streak", _fmt_count(trades["win_streak"])),
                _summary_item("Biggest Win", _fmt_money(trades["biggest_win"]), tone="positive"),
                _summary_item("Smallest Win", _fmt_money(trades["smallest_win"]), tone="positive"),
                _summary_item("Avg Win", _fmt_money(trades["avg_win"]), tone="positive"),
            ],
        },
        {
            "title": "Losses",
            "items": [
                _summary_item("Losses", _fmt_count(performance.get("losses")), tone="negative"),
                _summary_item("Loss Streak", _fmt_count(trades["loss_streak"])),
                _summary_item("Biggest Loss", _fmt_money(trades["biggest_loss"]), tone="negative"),
                _summary_item("Smallest Loss", _fmt_money(trades["smallest_loss"]), tone="negative"),
                _summary_item("Avg Loss", _fmt_money(trades["avg_loss"]), tone="negative"),
            ],
        },
    ]


def _chart_tables(
    config: dict[str, Any],
    positions: list[PositionRow],
    orders: list[OrderRow],
    fills: list[FillRow],
    botruns: list[BotrunRow],
) -> list[dict[str, Any]]:
    position_columns = ["ID", "Side", "Status", "Entry", "Exit", "Net PnL", "Opened", "Closed", "Exit"]
    order_columns = ["ID", "Position", "Side", "Qty", "Price", "Type", "Status", "Avg Fill", "Fills", "Submit"]
    fill_columns = ["ID", "Order", "Side", "Price", "Size", "Fee", "Closed PnL", "Time"]
    orders_by_position: dict[int, list[OrderRow]] = {}
    for order in orders:
        orders_by_position.setdefault(order.position_id, []).append(order)
    fills_by_order: dict[int, list[FillRow]] = {}
    for fill in fills:
        fills_by_order.setdefault(fill.order_id, []).append(fill)
    positions_by_botrun: dict[int, list[PositionRow]] = {}
    for position in positions:
        if position.botrun_id is not None:
            positions_by_botrun.setdefault(position.botrun_id, []).append(position)
    return [
        {
            "key": "bots",
            "title": "Bots",
            "columns": position_columns,
            "rows": [
                _bot_tree_row(
                    botrun,
                    sorted(positions_by_botrun.get(botrun.botrun_id, []), key=lambda item: item.closed_ts or 0, reverse=True),
                    orders_by_position,
                    fills_by_order,
                    position_columns,
                    order_columns,
                    fill_columns,
                )
                for botrun in sorted(botruns, key=lambda item: item.botrun_index, reverse=True)
            ],
        },
        {
            "key": "orders",
            "title": "Orders",
            "columns": order_columns,
            "rows": [
                _order_cells(order)
                for order in sorted(orders, key=lambda item: item.submit_ts)
            ],
        },
        {
            "key": "fills",
            "title": "Fills",
            "columns": fill_columns,
            "rows": [
                _fill_cells(fill)
                for fill in sorted(fills, key=lambda item: item.time)
            ],
        },
        {
            "key": "config",
            "title": "Config",
            "config_json": json.dumps(config, indent=2, sort_keys=True),
        },
    ]


def _signal_markers_from_events(events: list[EventRow], sweeprun_id: int, timestamps: list[int]) -> list[dict[str, Any]]:
    if not timestamps:
        return []
    markers: list[dict[str, Any]] = []
    for event in events:
        data = json.loads(event.data_json or "{}")
        if data.get("sweeprun_id") != sweeprun_id:
            continue
        kind = "enter_long" if data.get("enter_long") else "enter_short" if data.get("enter_short") else "exit_long" if data.get("exit_long") else "exit_short" if data.get("exit_short") else ""
        if not kind:
            continue
        ts_ms = int(data.get("signal_ts_ms") or event.event_ts or 0)
        index = bisect_right(timestamps, ts_ms) - 1
        index = max(0, min(len(timestamps) - 1, index))
        close = float(data.get("close") or 0)
        high = float(data.get("high") or close)
        low = float(data.get("low") or close)
        pad = close * 0.02
        price = high + pad if "short" in kind else low - pad
        color = "#ff1744" if "short" in kind else "#00e676"
        markers.append(
            {
                "name": kind,
                "value": [index, round(price, 8)],
                "reason": str(data.get("reason") or event.message or ""),
                "time": _chart_time(ts_ms),
                "itemStyle": {"color": "rgba(0,0,0,0)", "borderColor": color, "borderWidth": 2.4},
            }
        )
    return markers


def _bot_tree_row(
    botrun: BotrunRow,
    positions: list[PositionRow],
    orders_by_position: dict[int, list[OrderRow]],
    fills_by_order: dict[int, list[FillRow]],
    position_columns: list[str],
    order_columns: list[str],
    fill_columns: list[str],
) -> dict[str, Any]:
    result = json.loads(botrun.results_json or "{}")
    return {
        "botrun": {
            "id": botrun.botrun_id,
            "index": botrun.botrun_index,
            "bot": botrun.bot_id,
            "status": botrun.status,
            "pnl": _fmt_pct(result.get("pnl_pct")),
            "position_count": len(positions),
        },
        "positions": [
            {
                "cells": _position_cells(position),
                "sort": _sort_values(position_columns, _position_cells(position)),
                "orders": [
                    {
                        "cells": _order_cells(order),
                        "fills": [_fill_cells(fill) for fill in sorted(fills_by_order.get(order.order_id, []), key=lambda item: item.time, reverse=True)],
                    }
                    for order in sorted(orders_by_position.get(position.position_id, []), key=lambda item: item.submit_ts, reverse=True)
                ],
            }
            for position in positions
        ],
    }


def _position_cells(position: PositionRow) -> list[Any]:
    return [
        position.position_id,
        position.side or "",
        position.status,
        _fmt_decimal(position.avg_entry_px),
        _fmt_decimal(position.avg_exit_px),
        _fmt_decimal(position.net_pnl),
        _chart_time(position.opened_ts) if position.opened_ts else "",
        _chart_time(position.closed_ts) if position.closed_ts else "",
        position.exit_reason or "",
    ]


def _order_cells(order: OrderRow) -> list[Any]:
    return [
        order.order_id,
        order.position_id,
        order.submit_side,
        _fmt_decimal(order.submit_quantity, 6),
        _fmt_decimal(order.submit_price),
        order.submit_type,
        order.status,
        _fmt_decimal(order.avg_fill_price),
        order.fill_count,
        _chart_time(order.submit_ts),
    ]


def _fill_cells(fill: FillRow) -> list[Any]:
    return [
        fill.fill_id,
        fill.order_id,
        fill.side,
        _fmt_decimal(fill.px),
        _fmt_decimal(fill.sz, 6),
        _fmt_decimal(fill.fee, 6),
        _fmt_decimal(fill.closedPnl),
        _chart_time(fill.time),
    ]


def _sort_values(columns: list[str], cells: list[Any]) -> dict[str, str]:
    return {column: str(value) for column, value in zip(columns, cells, strict=True)}


def _trade_summary(positions: list[PositionRow]) -> dict[str, float | int | None]:
    pnls = [float(position.net_pnl) for position in sorted(positions, key=lambda item: item.opened_ts or 0)]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_loss = abs(sum(losses))
    avg_win = mean(wins) if wins else None
    avg_loss = mean(losses) if losses else None
    return {
        "net_pnl": sum(pnls) if pnls else None,
        "win_rate": len(wins) / len(pnls) * 100 if pnls else None,
        "win_streak": _streak(pnls, True),
        "loss_streak": _streak(pnls, False),
        "biggest_win": max(wins) if wins else None,
        "smallest_win": min(wins) if wins else None,
        "biggest_loss": min(losses) if losses else None,
        "smallest_loss": max(losses) if losses else None,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": sum(wins) / gross_loss if gross_loss else None,
        "payoff_ratio": avg_win / abs(avg_loss) if avg_win is not None and avg_loss not in (None, 0) else None,
        "ev": mean(pnls) if pnls else None,
        "trade_sharpe": _trade_sharpe(pnls),
    }


def _streak(values: list[float], winning: bool) -> int:
    best = current = 0
    for value in values:
        hit = value > 0 if winning else value < 0
        current = current + 1 if hit else 0
        best = max(best, current)
    return best


def _trade_sharpe(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return None if variance == 0 else avg / sqrt(variance) * sqrt(len(values))


def _fmt_pct_value(value: object) -> str:
    if not isinstance(value, int | float):
        return "-"
    return f"{float(value):.2f}%"


def _fmt_config_date(value: str) -> str:
    return value.replace("T", " ")[:16] if value else "-"


def _fmt_duration(start: str, end: str) -> str:
    if not start or not end:
        return "-"
    total_minutes = max(0, (date_ms(end) - date_ms(start)) // 60000)
    days, rem = divmod(total_minutes, 1440)
    hours, minutes = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts) or "0m"


def _chart_time(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
