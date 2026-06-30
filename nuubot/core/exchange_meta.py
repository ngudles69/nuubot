from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import builtins
import json
from typing import Any
import urllib.request

from nuubot.core.dtypes import DataNetwork, HyperliquidNetwork
from nuubot.datastore.schemas import Meta

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


def ensure_exchange_meta(datastore: Any, db: str, *, data_network: DataNetwork, default_network: HyperliquidNetwork) -> None:
    if not exchange_meta_stale(datastore, db):
        return
    save_exchange_meta(datastore, db, fetch_hc_meta(data_network=meta_network(data_network, default_network)))


def exchange_meta_stale(datastore: Any, db: str) -> bool:
    rows = datastore.select(db, Meta)
    if not rows:
        return True
    timestamps = [row.fetched_at for row in rows if row.fetched_at is not None]
    if not timestamps:
        return True
    newest = max(timestamps)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=UTC)
    return newest < datetime.now(UTC) - META_MAX_AGE


def save_exchange_meta(datastore: Any, db: str, rows: list[HcMetaRow]) -> None:
    fetched_at = datetime.now(UTC)
    tx = datastore.tx(db)
    tx.start()
    try:
        tx.delete(Meta)
        for row in rows:
            tx.insert(
                Meta(
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
            )
        tx.commit()
    except Exception:
        tx.rollback()
        raise
    finally:
        tx.close()


def meta_network(data_network: DataNetwork, default_network: HyperliquidNetwork) -> HyperliquidNetwork:
    if data_network == DataNetwork.TESTNET:
        return HyperliquidNetwork.TESTNET
    if data_network == DataNetwork.MAINNET:
        return HyperliquidNetwork.MAINNET
    return default_network


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
