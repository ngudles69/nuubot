from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import builtins
import json
from pathlib import Path
import urllib.request
from typing import Any

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from nuubot.config.models import AppConfig
from nuubot.core.dtypes import DataNetwork, HyperliquidNetwork
from nuubot.datastore.schemas import (
    AccountRow,
    BotCatalogRow,
    BotRow,
    ExchangeMetaSnapshotRow,
    ExchangeMetaRow,
    FillRow,
    OrderRow,
    PositionRow,
    ServerSequenceRow,
    ServerStateRow,
    SweeprunCatalogRow,
    SweeprunRow,
    SweepCatalogRow,
    SweepRow,
)

HYPERLIQUID_MAINNET_INFO_URL = "https://api.hyperliquid.xyz/info"
HYPERLIQUID_TESTNET_INFO_URL = "https://api.hyperliquid-testnet.xyz/info"
META_MAX_AGE = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class HcMetaRow:
    symbol: str
    kind: str
    asset_id: int | None
    exchange_index: int | None
    max_leverage: int | None
    size_decimals: int | None
    price_decimals: int | None
    is_delisted: bool
    is_canonical: bool | None
    raw_json: dict[str, Any]


class Datastore:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.server_path = self._server_path()

    def init(self) -> Datastore:
        self.init_server()
        self.ensure_exchange_meta()
        return self

    def init_server(self) -> None:
        self.server_path.parent.mkdir(parents=True, exist_ok=True)
        engine = self._engine(self.server_path)
        try:
            for table in (
                ServerSequenceRow.__table__,
                ServerStateRow.__table__,
                BotCatalogRow.__table__,
                SweepCatalogRow.__table__,
                SweeprunCatalogRow.__table__,
                ExchangeMetaRow.__table__,
            ):
                table.create(engine, checkfirst=True)
        finally:
            engine.dispose()

    def init_bot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = self._engine(path)
        try:
            for table in (
                BotRow.__table__,
                AccountRow.__table__,
                ExchangeMetaSnapshotRow.__table__,
                PositionRow.__table__,
                OrderRow.__table__,
                FillRow.__table__,
            ):
                table.create(engine, checkfirst=True)
        finally:
            engine.dispose()

    def init_sweep(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = self._engine(path)
        try:
            for table in (
                SweepRow.__table__,
                SweeprunRow.__table__,
            ):
                table.create(engine, checkfirst=True)
        finally:
            engine.dispose()

    def next_sequence(self, name: str) -> int:
        engine = self._engine(self.server_path)
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        text(
                            "INSERT INTO server_sequence (name, value, notes, created_at, updated_at) "
                            "VALUES (:name, 0, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                            "ON CONFLICT(name) DO NOTHING"
                        ),
                        {"name": name},
                    )
                    value = conn.execute(
                        text(
                            "UPDATE server_sequence "
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

    def ensure_exchange_meta(self) -> None:
        if not self._exchange_meta_stale():
            return
        self.upsert_exchange_meta(fetch_hc_meta(data_network=self._meta_network()))

    @contextmanager
    def session(self, path: Path | None = None) -> Iterator[Session]:
        engine = self._engine(path or self.server_path)
        session = Session(engine, expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()
            engine.dispose()

    def stop(self) -> None:
        pass

    def _exchange_meta_stale(self) -> bool:
        engine = self._engine(self.server_path)
        try:
            with engine.connect() as conn:
                count = conn.execute(select(func.count()).select_from(ExchangeMetaRow.__table__)).scalar_one()
                if count == 0:
                    return True
                newest = conn.execute(select(func.max(ExchangeMetaRow.fetched_at))).scalar_one()
        finally:
            engine.dispose()
        if newest is None:
            return True
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=UTC)
        return newest < datetime.now(UTC) - META_MAX_AGE

    def upsert_exchange_meta(self, rows: list[HcMetaRow]) -> None:
        fetched_at = datetime.now(UTC)
        engine = self._engine(self.server_path)
        try:
            with engine.begin() as conn:
                for row in rows:
                    statement = sqlite_insert(ExchangeMetaRow.__table__).values(
                        symbol=row.symbol,
                        kind=row.kind,
                        asset_id=row.asset_id,
                        exchange_index=row.exchange_index,
                        max_leverage=row.max_leverage,
                        size_decimals=row.size_decimals,
                        price_decimals=row.price_decimals,
                        is_delisted=row.is_delisted,
                        is_canonical=row.is_canonical,
                        raw_json=json.dumps(row.raw_json, separators=(",", ":")),
                        fetched_at=fetched_at,
                    )
                    conn.execute(
                        statement.on_conflict_do_update(
                            index_elements=[ExchangeMetaRow.__table__.c.symbol, ExchangeMetaRow.__table__.c.kind],
                            set_={
                                "asset_id": statement.excluded.asset_id,
                                "exchange_index": statement.excluded.exchange_index,
                                "max_leverage": statement.excluded.max_leverage,
                                "size_decimals": statement.excluded.size_decimals,
                                "price_decimals": statement.excluded.price_decimals,
                                "is_delisted": statement.excluded.is_delisted,
                                "is_canonical": statement.excluded.is_canonical,
                                "raw_json": statement.excluded.raw_json,
                                "fetched_at": statement.excluded.fetched_at,
                            },
                        )
                    )
        finally:
            engine.dispose()

    def _server_path(self) -> Path:
        root = Path(self.config.workspace.root)
        return root / self.config.paths.db_dir / "server.db"

    def _engine(self, path: Path) -> Engine:
        return create_engine(
            f"sqlite:///{path.as_posix()}",
            future=True,
            poolclass=NullPool,
            connect_args={"timeout": 30},
        )

    def _meta_network(self) -> HyperliquidNetwork:
        if self.config.data_network == DataNetwork.TESTNET:
            return HyperliquidNetwork.TESTNET
        if self.config.data_network == DataNetwork.MAINNET:
            return HyperliquidNetwork.MAINNET
        return self.config.hyperliquid.default_network


def fetch_hc_meta(*, data_network: HyperliquidNetwork) -> list[HcMetaRow]:
    url = HYPERLIQUID_TESTNET_INFO_URL if data_network == HyperliquidNetwork.TESTNET else HYPERLIQUID_MAINNET_INFO_URL
    perp_meta = fetch_info(url, "meta")
    spot_meta = fetch_info(url, "spotMeta")
    return normalize_perp_meta(perp_meta) + normalize_spot_meta(spot_meta)


def fetch_info(url: str, request_type: str) -> dict[str, Any]:
    body = json.dumps({"type": request_type}).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Hyperliquid {request_type} response must be an object")
    return value


def normalize_perp_meta(meta: dict[str, Any]) -> list[HcMetaRow]:
    universe = meta.get("universe")
    if not isinstance(universe, list):
        raise RuntimeError("meta.universe missing")
    rows: list[HcMetaRow] = []
    for index, market in enumerate(universe):
        if not isinstance(market, dict):
            continue
        symbol = required_string(market, "name").upper()
        size_decimals = required_int(market, "szDecimals")
        rows.append(
            HcMetaRow(
                symbol=symbol,
                kind="perp",
                asset_id=index,
                exchange_index=index,
                max_leverage=required_int(market, "maxLeverage"),
                size_decimals=size_decimals,
                price_decimals=max(6 - size_decimals, 0),
                is_delisted=bool(market.get("isDelisted") or False),
                is_canonical=None,
                raw_json=market,
            )
        )
    return rows


def normalize_spot_meta(meta: dict[str, Any]) -> list[HcMetaRow]:
    universe = meta.get("universe")
    tokens = meta.get("tokens")
    if not isinstance(universe, list) or not isinstance(tokens, list):
        raise RuntimeError("spotMeta.universe/tokens missing")
    rows: list[HcMetaRow] = []
    for market in universe:
        if not isinstance(market, dict):
            continue
        symbol = required_string(market, "name").upper()
        index = required_int(market, "index")
        token_indices = market.get("tokens")
        if not isinstance(token_indices, list) or not token_indices:
            raise RuntimeError(f"spot market tokens[0] missing: {symbol}")
        base_token = find_spot_token(tokens, builtins.int(token_indices[0]))
        size_decimals = required_int(base_token, "szDecimals")
        rows.append(
            HcMetaRow(
                symbol=symbol,
                kind="spot",
                asset_id=index,
                exchange_index=index,
                max_leverage=None,
                size_decimals=size_decimals,
                price_decimals=max(8 - size_decimals, 0),
                is_delisted=False,
                is_canonical=bool(market["isCanonical"]) if "isCanonical" in market else None,
                raw_json={"market": market, "base_token": base_token},
            )
        )
    return rows


def find_spot_token(tokens: list[Any], token_index: int) -> dict[str, Any]:
    for token in tokens:
        if isinstance(token, dict) and token.get("index") == token_index:
            return token
    raise RuntimeError(f"spot token index missing: {token_index}")


def required_string(value: dict[str, Any], field: str) -> str:
    result = value.get(field)
    if not isinstance(result, str):
        raise RuntimeError(f"{field} string missing")
    return result


def required_int(value: dict[str, Any], field: str) -> int:
    result = value.get(field)
    if result is None:
        raise RuntimeError(f"{field} integer missing")
    return builtins.int(result)
