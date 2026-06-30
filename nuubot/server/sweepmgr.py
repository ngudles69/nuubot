from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import threading
import tomllib
from typing import Any

from nuubot.datastore import AccountRow, BotrunRow, EventRow, FillRow, OrderRow, PositionRow, SweeprunRow, SweepRow, dbname
from nuubot.nuubot import Nuubot
from nuubot.sweeps.models import SweepConfig
from nuubot.sweeps.sweep import Sweep

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
        self.nuubot.datastore.insert(
            db,
            SweepRow(
                sweep_id=sweep_id,
                sweep_desc="sweep",
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
            sweep_id = _sweep_id_from_path(path)
            row = self.nuubot.datastore.get(path, SweepRow, sweep_id=sweep_id)
            status = self.status(sweep_id)
            rows.append(
                {
                    "sweep_id": row.sweep_id,
                    "sweep_desc": row.sweep_desc,
                    "status": status["status"],
                    "progress": status["progress"],
                    "done_count": status["done_count"],
                    "total_count": status["total_count"],
                    "sweeprun_count": row.sweeprun_count,
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "updated_at": row.updated_at.isoformat() if row.updated_at else "",
                    "db_path": str(path),
                }
            )
        return {"sweeps": rows}

    def load(self, sweep_id: int) -> dict[str, Any]:
        db = dbname(sweep_id, "sweep")
        if not self.nuubot.datastore.dbpath(db).exists():
            raise RuntimeError(f"sweep DB missing: {db}")
        sweep = self.nuubot.datastore.get(db, SweepRow, sweep_id=sweep_id)
        config = json.loads(sweep.config_json)
        SweepConfig.model_validate(config)
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
        config = SweepConfig.model_validate(data)
        result = config.model_dump(mode="json")
        result["botrun"]["runtime"].setdefault("loop_seconds", 1.0)
        if result["botrun"].get("backtest"):
            result["botrun"]["backtest"]["data_dir"] = (
                f"{self.nuubot.config.paths.data_dir}/binance/raw/spot/monthly/klines"
            )
        SweepConfig.model_validate(result)
        return result


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
