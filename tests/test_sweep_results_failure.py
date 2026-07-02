from __future__ import annotations

from concurrent.futures import Future
import time
from tempfile import TemporaryDirectory

from nuubot.datastore import BotrunRow, Datastore, SweeprunRow, SweepRow, dbname
from nuubot.sweeps.sweep import finish_sweep


class Executor:
    def __init__(self) -> None:
        self.shutdown_called = False

    def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
        self.shutdown_called = wait and not cancel_futures


def main() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "sweep")
        datastore.dbinit(db)
        datastore.insert(db, SweepRow(sweep_id=1, sweep_desc="sweep", config_json="{}", results_json="{}", status="running", sweeprun_count=1))
        sweeprun = datastore.insert(db, SweeprunRow(sweeprun_id=1, sweep_id=1, config_json="{}", results_json="{}", status="running"))
        datastore.insert(db, BotrunRow(botrun_id=10, sweeprun_id=sweeprun.sweeprun_id, bot_id=10, botrun_index=0, config_json="{}", results_json="{}", status="running"))

        future: Future = Future()
        future.set_exception(RuntimeError("boom"))
        executor = Executor()
        result = finish_sweep(datastore, db, 1, [(sweeprun.sweeprun_id, future)], executor, time.perf_counter(), 1)

        assert result["status"] == "failed"
        assert result["failed"] == 1
        assert executor.shutdown_called
        assert datastore.get(db, SweeprunRow, sweeprun_id=sweeprun.sweeprun_id).error_code == "process_failed"
        assert datastore.get(db, BotrunRow, botrun_id=10).error_code == "process_failed"


if __name__ == "__main__":
    main()
