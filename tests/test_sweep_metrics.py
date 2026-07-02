from __future__ import annotations

import json
import threading
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from nuubot.datastore import Datastore, SweeprunRow, SweepRow, dbname
from nuubot.server.sweepmgr import SweepManager


def main() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "sweep")
        datastore.dbinit(db)
        datastore.insert(db, SweepRow(sweep_id=1, sweep_desc="sweep", config_json="{}", results_json="{}", status="complete", sweeprun_count=4))
        datastore.insert(db, row(0, 1.0))
        datastore.insert(db, row(1, 1.0))
        datastore.insert(db, row(2, -0.5))
        datastore.insert(db, row(3, -0.5))
        manager = SweepManager(SimpleNamespace(datastore=datastore), {}, threading.Lock())
        metrics = manager.metrics(1)

        assert metrics["win_loss"] == "2/4 (50.0%)"
        assert metrics["profit_factor"] == "2.00"
        assert metrics["ev"] == "+0.25%"
        assert metrics["complete_count"] == 4


def row(index: int, pnl_pct: float) -> SweeprunRow:
    return SweeprunRow(
        sweep_id=1,
        sweeprun_id=index + 1,
        config_json="{}",
        results_json=json.dumps({"performance": {"pnl_pct": pnl_pct}}),
        status="complete",
    )


if __name__ == "__main__":
    main()
