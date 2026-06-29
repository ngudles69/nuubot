from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from nuubot.datastore import SweepRow
from nuubot.sweep import SweepManager

SWEEP_DB_RE = re.compile(r"^sweep_(\d+)\.db$")


def create_sweep(sweepmgr: SweepManager, template: str) -> dict[str, Any]:
    sweep_id = sweepmgr.create_sweep(template)
    return {"sweep_id": sweep_id}


def list_sweeps(sweepmgr: SweepManager) -> dict[str, Any]:
    db_dir = Path(sweepmgr.nuubot.config.workspace.root) / sweepmgr.nuubot.config.paths.db_dir
    rows: list[dict[str, Any]] = []
    for path in sorted(db_dir.glob("sweep_*.db"), key=sweep_id_from_path):
        sweep_id = sweep_id_from_path(path)
        with sweepmgr.nuubot.datastore.session(path) as session:
            row = session.get(SweepRow, sweep_id)
            if row is None:
                raise RuntimeError(f"sweep row missing: {path}")
            status = sweepmgr.status_sweep(sweep_id)
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


def load_sweep(sweepmgr: SweepManager, sweep_id: int) -> dict[str, Any]:
    config = sweepmgr.load_sweep(sweep_id)
    return {"sweep_id": sweep_id, "config": config}


def run_sweep(sweepmgr: SweepManager, sweep_id: int) -> dict[str, Any]:
    return sweepmgr.run_sweep(sweep_id)


def status_sweep(sweepmgr: SweepManager, sweep_id: int) -> dict[str, Any]:
    return sweepmgr.status_sweep(sweep_id)


def sweep_id_from_path(path: Path) -> int:
    match = SWEEP_DB_RE.match(path.name)
    if match is None:
        return 0
    return int(match.group(1))
