from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from nuubot.config.models import AppConfig
from nuubot.core.config import load_botrun_config
from nuubot.datastore.models import Base, BotRow, CommandRow


CONFIGURED = "configured"
PENDING = "pending"


class Datastore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.path = Path(config.paths.db_dir) / "nuubot.sqlite3"
        self.engine: Engine | None = None
        self.sessions: sessionmaker[Session] | None = None

    def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.path}", future=True)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def start(self) -> None:
        if self.engine is None:
            raise RuntimeError("datastore not initialized")
        Base.metadata.create_all(self.engine)

    def stop(self) -> None:
        if self.engine is None:
            raise RuntimeError("datastore not initialized")
        self.engine.dispose()

    def create_bot(self, config_path: Path) -> BotRow:
        bot_config = load_botrun_config(config_path)
        row = BotRow(
            status=CONFIGURED,
            config_json=bot_config.model_dump_json(indent=2),
            pid=None,
            run_token=None,
            started_at=None,
            last_seen_at=None,
            stopped_at=None,
        )
        with self.session() as session:
            session.add(row)
            session.commit()
            return row

    def delete_bot(self, bot_id: int) -> None:
        with self.session() as session:
            row = self.require_bot(session, bot_id)
            if row.status != CONFIGURED:
                raise RuntimeError(f"delete requires status={CONFIGURED}, got {row.status}")
            session.delete(row)
            session.commit()

    def clone_bot(self, bot_id: int) -> BotRow:
        with self.session() as session:
            source = self.require_bot(session, bot_id)
            row = BotRow(
                status=CONFIGURED,
                config_json=source.config_json,
                pid=None,
                run_token=None,
                started_at=None,
                last_seen_at=None,
                stopped_at=None,
            )
            session.add(row)
            session.commit()
            return row

    def view_bot(self, bot_id: int | None = None) -> list[dict[str, Any]]:
        with self.session() as session:
            if bot_id is None:
                rows = session.scalars(select(BotRow).order_by(BotRow.bot_id)).all()
            else:
                rows = [self.require_bot(session, bot_id)]
            return [bot_to_json(row) for row in rows]

    def command(self, bot_id: int, command: str, payload: dict[str, Any] | None = None) -> CommandRow:
        with self.session() as session:
            self.require_bot(session, bot_id)
            row = CommandRow(
                bot_id=bot_id,
                command=command,
                payload_json=json.dumps(payload or {}, sort_keys=True),
                status=PENDING,
                created_at=now_ms(),
            )
            session.add(row)
            session.commit()
            return row

    def ping(self, bot_id: int) -> dict[str, Any]:
        with self.session() as session:
            row = self.require_bot(session, bot_id)
            return {
                "bot_id": row.bot_id,
                "status": row.status,
                "pid": row.pid,
                "run_token": row.run_token,
                "last_seen_at": row.last_seen_at,
            }

    def session(self) -> Session:
        if self.sessions is None:
            raise RuntimeError("datastore not initialized")
        return self.sessions()

    def require_bot(self, session: Session, bot_id: int) -> BotRow:
        row = session.get(BotRow, bot_id)
        if row is None:
            raise RuntimeError(f"bot not found: {bot_id}")
        return row


def bot_to_json(row: BotRow) -> dict[str, Any]:
    return {
        "bot_id": row.bot_id,
        "status": row.status,
        "config": json.loads(row.config_json),
        "pid": row.pid,
        "run_token": row.run_token,
        "started_at": row.started_at,
        "last_seen_at": row.last_seen_at,
        "stopped_at": row.stopped_at,
    }


def now_ms() -> int:
    return int(time.time() * 1000)
