from __future__ import annotations

from tempfile import TemporaryDirectory

from nuubot.datastore import Datastore, SweepRow


def main() -> None:
    with TemporaryDirectory() as root:
        datastore = Datastore(root)

        for db in ("subdir/sweep_1.db", "../sweep_1.db"):
            try:
                datastore.dbpath(db)
            except RuntimeError as exc:
                assert "filename or absolute path" in str(exc)
            else:
                raise AssertionError(f"relative DB path should fail: {db}")

        try:
            datastore.get("sweep_999.db", SweepRow, sweep_id=999)
        except RuntimeError as exc:
            assert "datastore DB missing" in str(exc)
        else:
            raise AssertionError("missing DB should fail before SQLite creates a file")


if __name__ == "__main__":
    main()
