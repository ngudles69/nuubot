from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import tomllib
from typing import Any

from sqlalchemy import delete, func, select

from nuubot.datastore import AccountRow, BotrunRow, EventRow, FillRow, OrderRow, PositionRow, SweeprunRow, SweepRow
from nuubot.nuubot import Nuubot
from nuubot.sweeps.models import SweepConfig
from nuubot.sweeps.sweep import Sweep


@dataclass
class SweepManager:
    nuubot: Nuubot
    finalizers: dict[int, threading.Thread]

    def create(self, template: str | dict[str, Any]) -> int:
        template_data = self.template(template)
        sweep_id = self.nuubot.datastore.next_seq("sweep")
        dbpath = self.dbpath(sweep_id)
        self.nuubot.datastore.init_sweep(dbpath)
        with self.nuubot.datastore.session(dbpath) as session:
            session.add(
                SweepRow(
                    sweep_id=sweep_id,
                    sweep_desc="sweep",
                    config_json=json.dumps(template_data, sort_keys=True, separators=(",", ":")),
                    results_json="{}",
                    status="configured",
                    sweeprun_count=0,
                )
            )
            session.commit()
        return sweep_id

    def load(self, sweep_id: int) -> dict[str, Any]:
        dbpath = self.dbpath(sweep_id)
        if not dbpath.exists():
            raise RuntimeError(f"sweep DB missing: {dbpath}")
        with self.nuubot.datastore.session(dbpath) as session:
            sweep = session.get(SweepRow, sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {sweep_id}")
            config = json.loads(sweep.config_json)
        SweepConfig.model_validate(config)
        return config

    def update(self, sweep_id: int, template: str | dict[str, Any]) -> None:
        dbpath = self.dbpath(sweep_id)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not dbpath.exists():
            raise RuntimeError(f"sweep DB missing: {dbpath}")
        template_data = self.template(template)
        with self.nuubot.datastore.session(dbpath) as session:
            sweep = session.get(SweepRow, sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {sweep_id}")
            if sweep.status in {"queued", "running", "submitted"}:
                raise RuntimeError(f"cannot edit active sweep: {sweep_id}")
            for row_class in (FillRow, OrderRow, PositionRow, EventRow, AccountRow, BotrunRow, SweeprunRow):
                session.execute(delete(row_class))
            sweep.config_json = json.dumps(template_data, sort_keys=True, separators=(",", ":"))
            sweep.results_json = "{}"
            sweep.status = "configured"
            sweep.sweeprun_count = 0
            sweep.error_code = None
            sweep.error_text = None
            session.commit()

    def status(self, sweep_id: int) -> dict[str, Any]:
        dbpath = self.dbpath(sweep_id)
        if sweep_id <= 0:
            raise RuntimeError(f"invalid sweep_id: {sweep_id}")
        if not dbpath.exists():
            raise RuntimeError(f"sweep DB missing: {dbpath}")
        with self.nuubot.datastore.session(dbpath) as session:
            sweep = session.get(SweepRow, sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {sweep_id}")
            counts = {
                status: session.execute(
                    select(func.count()).select_from(SweeprunRow).where(SweeprunRow.status == status)
                ).scalar_one()
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

    def dbpath(self, sweep_id: int) -> Path:
        return Path(self.nuubot.config.workspace.root) / self.nuubot.config.paths.db_dir / f"sweep_{sweep_id}.db"

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
    return SweepManager(nuubot, {})


def run_sweep(sweepmgr: SweepManager, sweep_id: int) -> dict[str, Any]:
    return Sweep(sweepmgr.nuubot, sweep_id, sweepmgr.finalizers).run()


def _parse_template(template: str) -> dict[str, Any]:
    text = template.strip()
    if text.startswith("{"):
        data = json.loads(text)
        if not isinstance(data, dict):
            raise TypeError("JSON template must be an object")
        return data
    return tomllib.loads(template)
