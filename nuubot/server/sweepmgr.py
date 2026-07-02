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
from nuubot.sweeps.template import expand_sweep_template

SWEEP_DB_RE = re.compile(r"^sweep_(\d+)\.db$")


@dataclass
class SweepManager:
    nuubot: Nuubot
    result_threads: dict[int, threading.Thread]
    run_lock: threading.Lock

    def create(self, template: str | dict[str, Any]) -> int:
        template_data = self.parse_template(template)
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
        db = dbname(sweep_id, "sweep")
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        template_data = self.parse_template(template)
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

        # Run status and progress.
        counts = {
            status: sum(1 for row in rows if row.status == status)
            for status in ("queued", "running", "complete", "failed")
        }
        done_count = int(counts["complete"] + counts["failed"])
        total_count = int(sum(counts.values()))
        status = "archived" if archived else sweep.status
        progress = "" if archived else f"{done_count}/{total_count}"

        # Stored sweep result and sweeprun performance.
        results = json.loads(sweep.results_json or "{}")
        pnl = _pnl_metrics(rows)

        # Sweep and sweeprun timing.
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
            "win_loss": pnl["win_loss"],
            "profit_factor": pnl["profit_factor"],
            "ev": pnl["ev"],
            "created_at": sweep.created_at.isoformat() if sweep.created_at else "",
            "updated_at": sweep.updated_at.isoformat() if sweep.updated_at else "",
            "db_path": str(path),
            "results": results,
            "telemetry": telemetry,
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

    def parse_template(self, template: str | dict[str, Any]) -> dict[str, Any]:
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
        data_dir = f"{self.nuubot.config.paths.data_dir}/binance/raw/spot/monthly/klines"
        return expand_sweep_template(data, data_dir)

    def _list_sweep(self, path: Path, archived: bool = False) -> dict[str, Any]:
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

    # Archive and unarchive sweeps.

    def archive(self, sweep_id: int) -> None:
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
        with self.run_lock:
            sweep = self.nuubot.datastore.get(source, SweepRow, sweep_id=sweep_id)
            if sweep.status in {"queued", "running", "submitted"}:
                raise RuntimeError(f"cannot archive active sweep: {sweep_id}")
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)

    def unarchive(self, sweep_id: int) -> None:
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
