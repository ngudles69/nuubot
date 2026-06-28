from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from nuubot.config.models import AppConfig
from nuubot.datastore.schemas import BotRow, CommandRow, FillRow, OrderRow, PositionRow, SweeprunRow, SweepRow

POSTGRES_CONNECT_ARGS = {"options": "-c timezone=UTC"}


class Datastore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.engines: dict[str, Engine] = {}
        self.sessions: dict[str, sessionmaker[Session]] = {}

    def init(self) -> Datastore:
        db = self.config.databases

        # Create SERVER database and tables
        self._create_database(db.server)
        engine = self._engine(db.server)
        BotRow.__table__.create(engine, checkfirst=True)
        CommandRow.__table__.create(engine, checkfirst=True)
        self.engines[db.server] = engine
        self.sessions[db.server] = sessionmaker(engine, expire_on_commit=False)

        # Create MAINNET database and tables
        self._create_database(db.mainnet)
        engine = self._engine(db.mainnet)
        BotRow.__table__.create(engine, checkfirst=True)
        PositionRow.__table__.create(engine, checkfirst=True)
        OrderRow.__table__.create(engine, checkfirst=True)
        FillRow.__table__.create(engine, checkfirst=True)
        self.engines[db.mainnet] = engine
        self.sessions[db.mainnet] = sessionmaker(engine, expire_on_commit=False)

        # Create TESTNET database and tables
        self._create_database(db.testnet)
        engine = self._engine(db.testnet)
        BotRow.__table__.create(engine, checkfirst=True)
        PositionRow.__table__.create(engine, checkfirst=True)
        OrderRow.__table__.create(engine, checkfirst=True)
        FillRow.__table__.create(engine, checkfirst=True)
        self.engines[db.testnet] = engine
        self.sessions[db.testnet] = sessionmaker(engine, expire_on_commit=False)

        # Create SIMNET database and tables
        self._create_database(db.simnet)
        engine = self._engine(db.simnet)
        BotRow.__table__.create(engine, checkfirst=True)
        PositionRow.__table__.create(engine, checkfirst=True)
        OrderRow.__table__.create(engine, checkfirst=True)
        FillRow.__table__.create(engine, checkfirst=True)
        self.engines[db.simnet] = engine
        self.sessions[db.simnet] = sessionmaker(engine, expire_on_commit=False)

        # Create BACKTEST database and tables
        self._create_database(db.backtest)
        engine = self._engine(db.backtest)
        BotRow.__table__.create(engine, checkfirst=True)
        PositionRow.__table__.create(engine, checkfirst=True)
        OrderRow.__table__.create(engine, checkfirst=True)
        FillRow.__table__.create(engine, checkfirst=True)
        self.engines[db.backtest] = engine
        self.sessions[db.backtest] = sessionmaker(engine, expire_on_commit=False)

        # Create SWEEPS database and tables
        self._create_database(db.sweeps)
        engine = self._engine(db.sweeps)
        SweepRow.__table__.create(engine, checkfirst=True)
        SweeprunRow.__table__.create(engine, checkfirst=True)
        BotRow.__table__.create(engine, checkfirst=True)
        PositionRow.__table__.create(engine, checkfirst=True)
        OrderRow.__table__.create(engine, checkfirst=True)
        FillRow.__table__.create(engine, checkfirst=True)
        self.engines[db.sweeps] = engine
        self.sessions[db.sweeps] = sessionmaker(engine, expire_on_commit=False)

        return self

    def session(self, database: str | None = None) -> Session:
        if not self.sessions:
            raise RuntimeError("datastore not initialized")
        if database is None:
            database = self.config.databases.server
        return self.sessions[database]()

    def stop(self) -> None:
        if not self.engines:
            raise RuntimeError("datastore not initialized")
        for engine in self.engines.values():
            engine.dispose()
        self.engines.clear()
        self.sessions.clear()

    def _create_database(self, name: str) -> None:
        # CREATE DATABASE must run from the postgres maintenance database.
        engine = self._engine("postgres", isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as conn:
                exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}).first()
                if exists is None:
                    conn.execute(text(f"CREATE DATABASE {name}"))
        finally:
            engine.dispose()

    def _engine(self, database: str, isolation_level: str | None = None) -> Engine:
        # Every datastore connection runs in UTC. Display layers can localize later.
        return create_engine(
            self._database_url(database),
            connect_args=POSTGRES_CONNECT_ARGS,
            isolation_level=isolation_level,
            future=True,
        )

    def _database_url(self, database: str) -> URL:
        creds = self.config.credentials.database
        return URL.create(
            "postgresql+psycopg",
            username=creds.user,
            password=creds.password.get_secret_value(),
            host=creds.host,
            port=creds.port,
            database=database,
        )
