from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, delete as sa_delete, func, select as sa_select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from nuubot.datastore.schemas import (
    AccountRow,
    BotRow,
    BotStateRow,
    BotrunRow,
    CommandRow,
    EventRow,
    FillRow,
    Meta,
    OrderRow,
    PositionRow,
    ServerSeq,
    ServerState,
    SimulatorStateRow,
    SweeprunRow,
    SweepRow,
)

SERVER_TABLES = (
    ServerSeq,
    ServerState,
    Meta,
)
BOT_TABLES = (
    BotRow,
    AccountRow,
    CommandRow,
    EventRow,
    BotStateRow,
    SimulatorStateRow,
    PositionRow,
    OrderRow,
    FillRow,
)
SWEEP_TABLES = (
    SweepRow,
    SweeprunRow,
    BotrunRow,
    AccountRow,
    EventRow,
    PositionRow,
    OrderRow,
    FillRow,
)

class DatastoreTx:
    def __init__(self, datastore: Datastore, db: Path | str) -> None:
        self.datastore = datastore
        self.db = Path(db)
        self.engine: Engine | None = None
        self.session: Session | None = None

    def start(self) -> None:
        self.engine = self.datastore._engine(self.db)
        self.session = Session(self.engine, expire_on_commit=False)

    def commit(self) -> None:
        self._session().commit()

    def rollback(self) -> None:
        if self.session is not None:
            self.session.rollback()

    def close(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None

    def insert(self, row: Any) -> Any:
        session = self._session()
        session.add(row)
        session.flush()
        return row

    def update(self, table: Any, row: Any) -> Any:
        return self._session().merge(row)

    def delete(self, table: Any, **where: Any) -> int:
        statement = sa_delete(table)
        for field, value in where.items():
            statement = statement.where(getattr(table, field) == value)
        result = self._session().execute(statement)
        return int(result.rowcount or 0)

    def select(self, table: Any, **where: Any) -> list[Any]:
        return list(self._session().query(table).filter_by(**where).all())

    def get(self, table: Any, **where: Any) -> Any:
        rows = self.select(table, **where)
        if len(rows) != 1:
            raise RuntimeError(f"{table.__name__} expected 1 row, got {len(rows)}: {where}")
        return rows[0]

    def count(self, table: Any, **where: Any) -> int:
        statement = sa_select(func.count()).select_from(table)
        for field, value in where.items():
            statement = statement.where(getattr(table, field) == value)
        return int(self._session().execute(statement).scalar_one())

    def upsert(self, row: Any) -> None:
        values = {key: value for key, value in vars(row).items() if not key.startswith("_")}
        table = type(row)
        statement = sqlite_insert(table.__table__).values(**values)
        self._session().execute(statement.on_conflict_do_nothing())

    def _session(self) -> Session:
        if self.session is None:
            raise RuntimeError("transaction not started")
        return self.session


class Datastore:
    def __init__(self, dbroot: Path | str | None = None) -> None:
        self.dbroot = Path(dbroot).resolve() if dbroot is not None else None

    def create(self, db: Path | str) -> None:
        db = self.dbpath(db)
        db.parent.mkdir(parents=True, exist_ok=True)
        engine = self._engine(db)
        try:
            with engine.connect():
                pass
        finally:
            engine.dispose()

    def drop(self, db: Path | str) -> None:
        self.dbpath(db).unlink(missing_ok=True)

    def dbinit(self, db: Path | str) -> None:
        db = self.dbpath(db)
        db.parent.mkdir(parents=True, exist_ok=True)
        engine = self._engine(db)
        try:
            for table in self._tables(db):
                table.__table__.create(engine, checkfirst=True)
        finally:
            engine.dispose()

    def insert(self, db: Path | str, row: Any) -> Any:
        tx = self.tx(db)
        tx.start()
        try:
            row = tx.insert(row)
            tx.commit()
            return row
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    def update(self, db: Path | str, table: Any, row: Any) -> Any:
        tx = self.tx(db)
        tx.start()
        try:
            row = tx.update(table, row)
            tx.commit()
            return row
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    def delete(self, db: Path | str, table: Any, **where: Any) -> int:
        tx = self.tx(db)
        tx.start()
        try:
            count = tx.delete(table, **where)
            tx.commit()
            return count
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    def select(self, db: Path | str, table: Any, **where: Any) -> list[Any]:
        tx = self.tx(db)
        tx.start()
        try:
            return tx.select(table, **where)
        finally:
            tx.close()

    def get(self, db: Path | str, table: Any, **where: Any) -> Any:
        tx = self.tx(db)
        tx.start()
        try:
            return tx.get(table, **where)
        finally:
            tx.close()

    def count(self, db: Path | str, table: Any, **where: Any) -> int:
        tx = self.tx(db)
        tx.start()
        try:
            return tx.count(table, **where)
        finally:
            tx.close()

    def upsert(self, db: Path | str, row: Any) -> None:
        tx = self.tx(db)
        tx.start()
        try:
            tx.upsert(row)
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    def next_seq(self, db: Path | str, name: str) -> int:
        path = self._require_db(db)
        engine = self._engine(path)
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        text(
                            "INSERT INTO seq (name, value, notes, created_at, updated_at) "
                            "VALUES (:name, 0, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                            "ON CONFLICT(name) DO NOTHING"
                        ),
                        {"name": name},
                    )
                    value = conn.execute(
                        text(
                            "UPDATE seq "
                            "SET value = value + 1, updated_at = CURRENT_TIMESTAMP "
                            "WHERE name = :name "
                            "RETURNING value"
                        ),
                        {"name": name},
                    ).scalar_one()
                    conn.commit()
                    return int(value)
                except Exception:
                    conn.rollback()
                    raise
        finally:
            engine.dispose()

    def tx(self, db: Path | str) -> DatastoreTx:
        return DatastoreTx(self, self._require_db(db))

    def dbpath(self, db: Path | str) -> Path:
        path = Path(db)
        if path.is_absolute():
            return path
        if path.parent != Path("."):
            raise RuntimeError(f"datastore db must be a filename or absolute path: {db}")
        if self.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        return self.dbroot / path

    def _require_db(self, db: Path | str) -> Path:
        path = self.dbpath(db)
        if not path.exists():
            raise RuntimeError(f"datastore DB missing: {path}")
        return path

    def _engine(self, path: Path) -> Engine:
        return create_engine(
            f"sqlite:///{path.as_posix()}",
            future=True,
            poolclass=NullPool,
            connect_args={"timeout": 30},
        )

    def _tables(self, db: Path) -> tuple[Any, ...]:
        name = db.name
        if name == "server.db":
            return SERVER_TABLES
        if name.startswith("sweep_"):
            return SWEEP_TABLES
        if "_bot_" in db.stem:
            return BOT_TABLES
        raise RuntimeError(f"unknown DB type: {db}")
