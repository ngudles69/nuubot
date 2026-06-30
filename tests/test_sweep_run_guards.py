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
        datastore.insert(db, SweeprunRow(sweep_id=1, sweeprun_index=0, config_json="{}", results_json="{}", status="complete"))

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
        old_config = sweep_config(workers=4, ema_fast=[6])
        new_config = sweep_config(workers=4, ema_fast=[9])
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
        datastore.insert(db, SweeprunRow(sweep_id=1, sweeprun_index=0, config_json="{}", results_json="{}", status="complete"))

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
        assert json.loads(sweep.config_json)["params"]["ema_fast"] == [6]
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
        assert datastore.count(db, BotrunRow, status="failed") == 1


class FailingExecutor:
    def __init__(self, *args, **kwargs) -> None:
        self.shutdown_called = False

    def submit(self, *args, **kwargs):
        raise RuntimeError("submit boom")

    def shutdown(self, *, wait: bool, cancel_futures: bool) -> None:
        self.shutdown_called = True


def _update_sweep(manager: SweepManager, config: dict, outcome: dict[str, str]) -> None:
    try:
        manager.update(1, config)
        outcome["ok"] = "updated"
    except Exception as exc:
        outcome["error"] = str(exc)


def sweep_config(*, workers: int, ema_fast: list[int] | None = None) -> dict:
    config = {
        "sweep": {
            "mode": "fast",
            "start_bot_id": 200,
            "workers": workers,
        },
        "runtime": {
            "mode": "sweep",
            "max_loop": 0,
            "loop_seconds": 1.0,
        },
        "market": {
            "symbol": "BTCUSDT",
            "interval": "1h",
        },
        "backtest": {
            "start": "2025-01-01",
            "stop": "2025-03-31T23:59:59",
            "data_dir": "workspace/data/binance/raw/spot/monthly/klines",
        },
        "signalers": [
            {
                "name": "emacross",
                "interval": "1h",
                "params": {
                    "fast": 9,
                    "slow": 21,
                },
            }
        ],
        "executor": {
            "name": "tradebot",
            "take_profit_pct": 0.0,
            "stop_loss_pct": 0.0,
            "max_cycles": 0,
        },
        "risk": {
            "score": 1,
        },
        "params": {
            "ema_fast": [6],
            "ema_slow": [21],
        },
    }
    if ema_fast is not None:
        config = deepcopy(config)
        config["params"]["ema_fast"] = ema_fast
    return config


if __name__ == "__main__":
    main()
