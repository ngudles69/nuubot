from __future__ import annotations

import json
import threading
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from nuubot.datastore import Datastore, EventRow, SweeprunRow, SweepRow, dbname
from nuubot.server.sweepmgr import SweepManager, _signal_markers_from_events
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
    chart_signal_markers_use_persisted_events()
    sweeprun_chart_splits_line_and_marker_sources()


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


def chart_signal_markers_use_persisted_events() -> None:
    event = EventRow(
        event_ts=2_000,
        event="signal",
        message="ema_cross_up",
        data_json=json.dumps(
            {
                "sweeprun_id": 2,
                "signal_ts_ms": 2_000,
                "reason": "ema_cross_up",
                "enter_long": True,
                "enter_short": False,
                "exit_long": False,
                "exit_short": False,
                "high": 110,
                "low": 100,
                "close": 105,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
    )

    markers = _signal_markers_from_events([event], 2, [1_000, 2_000, 3_000])

    assert markers == [
        {
            "name": "enter_long",
            "value": [1, 97.9],
            "reason": "ema_cross_up",
            "time": "1970-01-01 00:00",
            "itemStyle": {"color": "rgba(0,0,0,0)", "borderColor": "#00e676", "borderWidth": 2.4},
        }
    ]


def sweeprun_chart_splits_line_and_marker_sources() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "sweep")
        datastore.dbinit(db)
        config = {
            "sweeprun": {"start": "1970-01-01T00:00:00", "end": "1970-01-01T00:03:00", "data_dir": "data"},
            "executor": {"symbol": "BTCUSDT", "interval": "1m", "name": "tradebot"},
            "signaler": {"name": "emacross", "interval": "1m", "params": {"fast": 2, "slow": 3}},
        }
        datastore.insert(db, SweeprunRow(sweep_id=1, sweeprun_id=2, config_json=json.dumps(config), results_json="{}", status="complete"))
        datastore.insert(
            db,
            EventRow(
                event_ts=120_000,
                event="signal",
                message="persisted_reason",
                data_json=json.dumps(
                    {
                        "sweeprun_id": 2,
                        "signal_ts_ms": 120_000,
                        "reason": "persisted_reason",
                        "enter_long": True,
                        "enter_short": False,
                        "exit_long": False,
                        "exit_short": False,
                        "high": 110,
                        "low": 100,
                        "close": 105,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        )
        manager = SweepManager(SimpleNamespace(datastore=datastore, config=SimpleNamespace(workspace=SimpleNamespace(root=root))), {}, threading.Lock())
        candles = [
            {"ts_ms": index * 60_000, "open": float(index + 1), "high": float(index + 2), "low": float(index), "close": float(index + 1), "volume": 1.0}
            for index in range(20)
        ]
        manager._chart_candles = lambda data_dir, symbol, interval, start_ms, stop_ms: [row for row in candles if start_ms <= row["ts_ms"] <= stop_ms]

        result = manager.sweeprun_chart(1, 2)

        assert result["indicators"]["source"] == "regenerated"
        assert result["indicators"]["marker_source"] == "persisted_events"
        assert [marker["reason"] for marker in result["indicators"]["markers"]] == ["persisted_reason"]


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
