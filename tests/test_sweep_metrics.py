from __future__ import annotations

import json

from nuubot.datastore import SweeprunRow
from nuubot.server.sweepmgr import sweep_metrics


def main() -> None:
    rows = [
        row(1.0),
        row(1.0),
        row(-0.5),
        row(-0.5),
    ]
    metrics = sweep_metrics(rows)

    assert metrics["win_loss"] == "2/4 (50.0%)"
    assert metrics["profit_factor"] == "2.00"
    assert metrics["ev"] == "+0.25%"


def row(pnl_pct: float) -> SweeprunRow:
    return SweeprunRow(
        sweep_id=1,
        sweeprun_index=0,
        config_json="{}",
        results_json=json.dumps({"performance": {"pnl_pct": pnl_pct}}),
        status="complete",
    )


if __name__ == "__main__":
    main()
