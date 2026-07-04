from __future__ import annotations

import json
import threading
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from nuubot.datastore import Datastore, SweeprunRow, SweepRow, dbname
from nuubot.server.sweepmgr import SweepManager
from nuubot.sweeps.executors.swtradebot import _tpsl_by_position, position_window_primitives


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
    box_uses_tpsl_as_bounds()


def box_uses_tpsl_as_bounds() -> None:
    position = SimpleNamespace(
        position_id=10,
        opened_ts=1_000,
        closed_ts=3_000,
        avg_entry_px="100",
        avg_exit_px="101",
        side="long",
        exit_reason="take_profit",
    )
    orders = [
        SimpleNamespace(position_id=10, submit_tpsl="tp", submit_trigger_price="103", submit_price="103"),
        SimpleNamespace(position_id=10, submit_tpsl="sl", submit_trigger_price="98", submit_price="98"),
    ]

    primitives = position_window_primitives(position, [1_000, 2_000, 3_000], _tpsl_by_position(orders)[10])
    box = primitives[0]

    assert box["type"] == "dashbox"
    assert box["value"] == [0, 2, 103.0, 98.0]
    assert box["tp"] == 103.0
    assert box["sl"] == 98.0
    assert primitives[1]["type"] == "hline"
    assert primitives[1]["label"] == "entry"
    assert primitives[2]["label"] == "exit"


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
