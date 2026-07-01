from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from statistics import mean, median
import threading
import tomllib
from typing import Any

from nuubot.datastore import AccountRow, BotrunRow, EventRow, FillRow, OrderRow, PositionRow, SweeprunRow, SweepRow, dbname
from nuubot.nuubot import Nuubot
from nuubot.sweeps.sweep import Sweep
from nuubot.sweeps.template import normalize_sweep_template

SWEEP_DB_RE = re.compile(r"^sweep_(\d+)\.db$")


@dataclass
class SweepManager:
    nuubot: Nuubot
    result_threads: dict[int, threading.Thread]
    run_lock: threading.Lock

    def create(self, template: str | dict[str, Any]) -> int:
        template_data = self.template(template)
        sweep_id = self.nuubot.datastore.next_seq(self.nuubot.server_db, "sweep")
        db = dbname(sweep_id, "sweep")
        self.nuubot.datastore.dbinit(db)
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
        for path in sorted(db_dir.glob("sweep_*.db"), key=_sweep_id_from_path):
            rows.append(self._list_row(path))
        return {"sweeps": rows}

    def archived(self) -> dict[str, Any]:
        archive_dir = self.archive_dir()
        rows = []
        if archive_dir.exists():
            for path in sorted(archive_dir.glob("sweep_*.db"), key=_sweep_id_from_path):
                rows.append(self._list_row(path, archived=True))
        return {"sweeps": rows}

    def load(self, sweep_id: int) -> dict[str, Any]:
        db = dbname(sweep_id, "sweep")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        sweep = self.nuubot.datastore.get(db, SweepRow, sweep_id=sweep_id)
        config = json.loads(sweep.config_json)
        return config

    def update(self, sweep_id: int, template: str | dict[str, Any]) -> None:
        db = dbname(sweep_id, "sweep")
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        template_data = self.template(template)
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

    def status(self, sweep_id: int) -> dict[str, Any]:
        db = dbname(sweep_id, "sweep")
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        sweep = self.nuubot.datastore.get(db, SweepRow, sweep_id=sweep_id)
        counts = {
            status: self.nuubot.datastore.count(db, SweeprunRow, status=status)
            for status in ("queued", "running", "complete", "failed")
        }
        done_count = int(counts["complete"] + counts["failed"])
        total_count = int(sum(counts.values()))
        return {
            "sweep_id": sweep_id,
            "status": sweep.status,
            "queued_count": int(counts["queued"]),
            "running_count": int(counts["running"]),
            "complete_count": int(counts["complete"]),
            "failed_count": int(counts["failed"]),
            "done_count": done_count,
            "total_count": total_count,
            "progress": f"{done_count}/{total_count}",
        }

    def results(self, sweep_id: int, archived: bool = False) -> dict[str, Any]:
        db = dbname(sweep_id, "sweep")
        path = self.archive_dir() / db if archived else self.nuubot.datastore.dbpath(db)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not path.exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        sweep = self.nuubot.datastore.get(path, SweepRow, sweep_id=sweep_id)
        result = json.loads(sweep.results_json or "{}")
        result["telemetry"] = self.telemetry(sweep_id, archived)
        return result

    def telemetry(self, sweep_id: int, archived: bool = False) -> dict[str, Any]:
        db = dbname(sweep_id, "sweep")
        path = self.archive_dir() / db if archived else self.nuubot.datastore.dbpath(db)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not path.exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        sweep = self.nuubot.datastore.get(path, SweepRow, sweep_id=sweep_id)
        rows = self.nuubot.datastore.select(path, SweeprunRow, sweep_id=sweep_id)
        values: dict[str, list[float]] = {}
        for row in rows:
            result = json.loads(row.results_json or "{}")
            for key, value in result.get("telemetry", {}).get("timing", {}).items():
                if isinstance(value, int | float):
                    values.setdefault(key, []).append(value)
        return {
            "sweep_id": sweep_id,
            "status": "archived" if archived else sweep.status,
            "sweeprun_count": len(rows),
            "sweep": json.loads(sweep.results_json or "{}").get("telemetry", {}),
            "sweepruns": {key: timing_stats(items) for key, items in sorted(values.items())},
        }

    def run(self, sweep_id: int) -> dict[str, Any]:
        if self.nuubot.datastore is None:
            raise RuntimeError("nuubot datastore missing")
        db = dbname(sweep_id, "sweep")
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        return Sweep(self.nuubot.datastore, sweep_id, self.result_threads, self.run_lock).run()

    def template(self, template: str | dict[str, Any]) -> dict[str, Any]:
        data = _parse_template(template) if isinstance(template, str) else template
        data_dir = f"{self.nuubot.config.paths.data_dir}/binance/raw/spot/monthly/klines"
        return normalize_sweep_template(data, data_dir)

    def archive_dir(self) -> Path:
        if self.nuubot.datastore.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        return self.nuubot.datastore.dbroot / "archived"

    def _list_row(self, path: Path, archived: bool = False) -> dict[str, Any]:
        sweep_id = _sweep_id_from_path(path)
        row = self.nuubot.datastore.get(path, SweepRow, sweep_id=sweep_id)
        config = json.loads(row.config_json or "{}")
        metrics = sweep_metrics(self.nuubot.datastore.select(path, SweeprunRow, sweep_id=sweep_id))
        status = archived_status(row) if archived else self.status(sweep_id)
        return {
            "sweep_id": row.sweep_id,
            "name": sweep_name(row, config),
            "sweep_desc": row.sweep_desc,
            "status": status["status"],
            "progress": status["progress"],
            "done_count": status["done_count"],
            "total_count": status["total_count"],
            "sweeprun_count": row.sweeprun_count,
            "win_loss": metrics["win_loss"],
            "profit_factor": metrics["profit_factor"],
            "ev": metrics["ev"],
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
            "db_path": str(path),
        }

    # Archive and unarchive sweeps.

    def archive(self, sweep_id: int) -> None:
        db = dbname(sweep_id, "sweep")
        source = self.nuubot.datastore.dbpath(db)
        target = self.archive_dir() / db
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not source.exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        if target.exists():
            raise RuntimeError(f"sweep already archived: {sweep_id}")
        with self.run_lock:
            sweep = self.nuubot.datastore.get(source, SweepRow, sweep_id=sweep_id)
            if sweep.status in {"queued", "running", "submitted"}:
                raise RuntimeError(f"cannot archive active sweep: {sweep_id}")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)

    def unarchive(self, sweep_id: int) -> None:
        db = dbname(sweep_id, "sweep")
        source = self.archive_dir() / db
        target = self.nuubot.datastore.dbpath(db)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not source.exists():
            raise RuntimeError(f"archived sweep DB missing: {db}")
        if target.exists():
            raise RuntimeError(f"sweep already active: {sweep_id}")
        with self.run_lock:
            source.replace(target)


def sweepmgr_setup(nuubot: Nuubot) -> SweepManager:
    if nuubot.config is None or nuubot.datastore is None:
        raise RuntimeError("nuubot_setup() must complete before sweepmgr_setup()")
    return SweepManager(nuubot, {}, threading.Lock())


def _parse_template(template: str) -> dict[str, Any]:
    text = template.strip()
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise TypeError("JSON template must be an object")
        return data
    return tomllib.loads(template)


def _sweep_id_from_path(path: Path) -> int:
    match = SWEEP_DB_RE.match(path.name)
    if match is None:
        return 0
    return int(match.group(1))


def timing_stats(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "max": max(values),
        "mean": round(mean(values), 2),
        "median": median(values),
    }


def archived_status(row: SweepRow) -> dict[str, Any]:
    return {
        "status": "archived",
        "progress": "",
        "done_count": row.sweeprun_count,
        "total_count": row.sweeprun_count,
    }


def sweep_name(row: SweepRow, config: dict[str, Any]) -> str:
    sweep = config.get("sweep", {})
    return str(sweep.get("name") or f"sweep-{row.sweep_id}")


def sweep_metrics(rows: list[SweeprunRow]) -> dict[str, str]:
    pnls = []
    for row in rows:
        result = json.loads(row.results_json or "{}")
        pnl = result.get("performance", {}).get("pnl_pct")
        if isinstance(pnl, int | float):
            pnls.append(float(pnl))
    if not pnls:
        return {"win_loss": "-", "profit_factor": "-", "ev": "-"}

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
