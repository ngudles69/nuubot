from __future__ import annotations

import threading
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from nuubot.datastore import BotRow, Datastore, SweepRow, dbname
from nuubot.server.botmgr import BotManager
from nuubot.server.sweepmgr import SweepManager


def main() -> None:
    sweep_archive_moves_file_out_of_active_list()
    bot_archive_moves_file_out_of_active_list()


def sweep_archive_moves_file_out_of_active_list() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "sweep")
        datastore.dbinit(db)
        datastore.insert(db, SweepRow(sweep_id=1, sweep_desc="sweep", config_json="{}", results_json="{}", status="complete", sweeprun_count=0))
        manager = SweepManager(SimpleNamespace(datastore=datastore, config=None), {}, threading.Lock())

        manager.archive(1)
        assert not datastore.dbpath(db).exists()
        assert (datastore.dbroot / "archived" / db).exists()
        assert manager.list()["sweeps"] == []
        assert manager.archived()["sweeps"][0]["status"] == "archived"

        manager.unarchive(1)
        assert datastore.dbpath(db).exists()
        assert not (datastore.dbroot / "archived" / db).exists()


def bot_archive_moves_file_out_of_active_list() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)
        db = dbname(1, "bot", "mainnet")
        datastore.dbinit(db)
        datastore.insert(db, BotRow(bot_id=1, status="configured", config_json="{}", state_json="{}"))
        manager = BotManager(SimpleNamespace(datastore=datastore))

        manager.archive(1)
        assert not datastore.dbpath(db).exists()
        assert (datastore.dbroot / "archived" / db).exists()

        manager.unarchive(1)
        assert datastore.dbpath(db).exists()
        assert not (datastore.dbroot / "archived" / db).exists()


if __name__ == "__main__":
    main()
