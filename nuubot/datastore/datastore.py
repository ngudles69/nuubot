from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from nuubot.config.models import AppConfig
from nuubot.datastore.models import Base


class Datastore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.root = Path(config.paths.db_dir)
        self.engines: dict[str, Engine] = {}
        self.sessions: dict[str, sessionmaker[Session]] = {}

    def init(self) -> Datastore:
        self.root.mkdir(parents=True, exist_ok=True)
        for name in self._database_names():
            engine = create_engine(f"sqlite:///{self.root / f'{name}.sqlite3'}", future=True)
            Base.metadata.create_all(engine)
            self.engines[name] = engine
            self.sessions[name] = sessionmaker(engine, expire_on_commit=False)
        return self

    def session(self, database: str = "server") -> Session:
        if not self.sessions:
            raise RuntimeError("datastore not initialized")
        return self.sessions[database]()

    def stop(self) -> None:
        if not self.engines:
            raise RuntimeError("datastore not initialized")
        for engine in self.engines.values():
            engine.dispose()
        self.engines.clear()
        self.sessions.clear()

    def _database_names(self) -> list[str]:
        return list(self.config.databases.model_dump().values())
