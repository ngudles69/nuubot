from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace
import threading
import time
from tempfile import TemporaryDirectory

from nuubot.datastore import BotrunRow, Datastore, SweeprunRow, SweepRow, dbname
from nuubot.server.sweepmgr import SweepManager
import nuubot.sweeps.sweep as sweep_module
from nuubot.sweeps.sweep import Sweep


def main() -> None:
    invalid_workers_do_not_reset_sweep()
    update_waits_for_run_lock_and_refuses_running_sweep()
    launch_failure_marks_rows_failed()
    partial_launch_failure_drains_started_futures()


def invalid_workers_do_not_reset_sweep() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "sweep")
        datastore.dbinit(db)
        datastore.insert(
            db,
            SweepRow(
                sweep_id=1,
                sweep_desc="sweep",
                config_json=json.dumps(sweep_config(workers=0), sort_keys=True, separators=(",", ":")),
                results_json='{"old":true}',
                status="configured",
                sweeprun_count=99,
            )
        )
        datastore.insert(db, SweeprunRow(sweeprun_id=1, sweep_id=1, config_json="{}", results_json="{}", status="complete"))

        try:
            Sweep(datastore, 1, {}, threading.Lock()).run()
        except RuntimeError as exc:
            assert "sweep.workers must be positive" in str(exc)
        else:
            raise AssertionError("invalid workers should fail before reset")

        sweep = datastore.get(db, SweepRow, sweep_id=1)
        assert sweep.status == "configured"
        assert sweep.results_json == '{"old":true}'
        assert sweep.sweeprun_count == 99
        assert datastore.count(db, SweeprunRow) == 1
        assert datastore.count(db, SweeprunRow, status="complete") == 1


def update_waits_for_run_lock_and_refuses_running_sweep() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "sweep")
        datastore.dbinit(db)
        old_config = sweep_config(workers=4, fast={"start": 6, "stop": 6, "step": 1})
        new_config = sweep_config(workers=4, fast={"start": 9, "stop": 9, "step": 1})
        datastore.insert(
            db,
            SweepRow(
                sweep_id=1,
                sweep_desc="sweep",
                config_json=json.dumps(old_config, sort_keys=True, separators=(",", ":")),
                results_json="{}",
                status="configured",
                sweeprun_count=1,
            )
        )
        datastore.insert(db, SweeprunRow(sweeprun_id=1, sweep_id=1, config_json="{}", results_json="{}", status="complete"))

        nuubot = SimpleNamespace(
            datastore=datastore,
            config=SimpleNamespace(paths=SimpleNamespace(data_dir="workspace/data")),
        )
        manager = SweepManager(nuubot, {}, threading.Lock())
        manager.run_lock.acquire()
        outcome: dict[str, str] = {}

        thread = threading.Thread(target=_update_sweep, args=(manager, new_config, outcome))
        thread.start()
        time.sleep(0.05)
        assert thread.is_alive()

        tx = datastore.tx(db)
        tx.start()
        try:
            tx.get(SweepRow, sweep_id=1).status = "running"
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

        manager.run_lock.release()
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert outcome["error"] == "cannot edit active sweep: 1"

        sweep = datastore.get(db, SweepRow, sweep_id=1)
        assert sweep.status == "running"
        assert json.loads(sweep.config_json)["signalers"]["01"][0]["items"][0]["params"]["fast"] == {"start": 6, "stop": 6, "step": 1}
        assert datastore.count(db, SweeprunRow) == 1


def launch_failure_marks_rows_failed() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "sweep")
        datastore.dbinit(db)
        datastore.insert(
            db,
            SweepRow(
                sweep_id=1,
                sweep_desc="sweep",
                config_json=json.dumps(sweep_config(workers=4), sort_keys=True, separators=(",", ":")),
                results_json="{}",
                status="configured",
                sweeprun_count=0,
            )
        )

        original = sweep_module.ProcessPoolExecutor
        sweep_module.ProcessPoolExecutor = FailingExecutor
        try:
            try:
                Sweep(datastore, 1, {}, threading.Lock()).run()
            except RuntimeError as exc:
                assert str(exc) == "submit boom"
            else:
                raise AssertionError("launch failure should be raised")
        finally:
            sweep_module.ProcessPoolExecutor = original

        sweep = datastore.get(db, SweepRow, sweep_id=1)
        assert sweep.status == "failed"
        assert sweep.error_code == "launch_failed"
        assert sweep.error_text == "submit boom"
        assert datastore.count(db, SweeprunRow, status="failed") == 1
        assert datastore.count(db, BotrunRow) == 0


def partial_launch_failure_drains_started_futures() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "sweep")
        datastore.dbinit(db)
        datastore.insert(
            db,
            SweepRow(
                sweep_id=1,
                sweep_desc="sweep",
                config_json=json.dumps(sweep_config(workers=4, fast={"start": 6, "stop": 7, "step": 1}), sort_keys=True, separators=(",", ":")),
                results_json="{}",
                status="configured",
                sweeprun_count=0,
            )
        )

        original = sweep_module.ProcessPoolExecutor
        PartialFailingExecutor.last = None
        sweep_module.ProcessPoolExecutor = PartialFailingExecutor
        try:
            try:
                Sweep(datastore, 1, {}, threading.Lock()).run()
            except RuntimeError as exc:
                assert str(exc) == "submit boom"
            else:
                raise AssertionError("partial launch failure should be raised")
        finally:
            sweep_module.ProcessPoolExecutor = original

        assert PartialFailingExecutor.last is not None
        assert PartialFailingExecutor.last.shutdown_calls == [(True, True)]
        sweep = datastore.get(db, SweepRow, sweep_id=1)
        assert sweep.status == "failed"
        assert datastore.count(db, SweeprunRow, status="failed") == 2
        assert datastore.count(db, BotrunRow) == 0


class FailingExecutor:
    def __init__(self, *args, **kwargs) -> None:
        self.shutdown_called = False

    def submit(self, *args, **kwargs):
        raise RuntimeError("submit boom")

    def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
        self.shutdown_called = True


class PartialFailingExecutor:
    last = None

    def __init__(self, *args, **kwargs) -> None:
        self.submit_count = 0
        self.shutdown_calls: list[tuple[bool, bool]] = []
        PartialFailingExecutor.last = self

    def submit(self, *args, **kwargs):
        self.submit_count += 1
        if self.submit_count == 2:
            raise RuntimeError("submit boom")
        return CompletedFuture()

    def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
        self.shutdown_calls.append((wait, cancel_futures))


class CompletedFuture:
    def result(self):
        return None


def _update_sweep(manager: SweepManager, config: dict, outcome: dict[str, str]) -> None:
    try:
        manager.update(1, config)
        outcome["ok"] = "updated"
    except Exception as exc:
        outcome["error"] = str(exc)


def sweep_config(*, workers: int, fast: dict[str, int] | None = None) -> dict:
    config = {
        "sweep": {
            "mode": "fast",
            "workers": workers,
            "data_dir": "workspace/data/binance/raw/spot/monthly/klines",
        },
        "data": {
            "01": [
                {
                    "sweeprun": {"start": "2025-01-01", "end": "2025-03-31T23:59:59"},
                }
            ],
        },
        "signalers": {
            "01": [{
                "items": [{
                "name": "emacross",
                "interval": "1h",
                "params": {
                    "fast": {"start": 6, "stop": 6, "step": 1},
                    "slow": 21,
                },
                }],
            }],
        },
        "executors": {
            "01": [{"executor": {"symbol": "BTCUSDT", "interval": "1h", "name": "tradebot", "take_profit_pct": 0.0, "stop_loss_pct": 0.0, "max_cycles": 0}}],
        },
        "risk": {
            "score": 1,
        },
    }
    if fast is not None:
        config = deepcopy(config)
        config["signalers"]["01"][0]["items"][0]["params"]["fast"] = fast
    return config


if __name__ == "__main__":
    main()
