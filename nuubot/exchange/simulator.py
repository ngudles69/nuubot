from __future__ import annotations

from decimal import Decimal
from typing import Any

from nuubot.account.fill import Fill, dec
from nuubot.account.ledger import TradeLedger
from nuubot.account.order import CancelResult, Order, OrderResult, OrderUpdate

OPEN_EXCHANGE_STATUS = {"open", "resting", "waitingForTrigger", "waitingForFill"}


class Simulator:
    def __init__(self, slippage_pct: float | Decimal = Decimal("0.05"), commission_pct: float | Decimal = Decimal("0.05")) -> None:
        self.next_oid = 1
        self.open: list[Order] = []
        self.seen_fills: list[Fill] = []
        self.seen_updates: list[OrderUpdate] = []
        self.current_leverage = 1
        self.slippage_rate = dec(slippage_pct) / Decimal("100")
        self.commission_rate = dec(commission_pct) / Decimal("100")
        self.bid: Decimal | None = None
        self.ask: Decimal | None = None

    def init(self) -> None:
        if self.slippage_rate < 0:
            raise ValueError(f"slippage_pct must be >= 0: {self.slippage_rate * 100}")
        if self.commission_rate < 0:
            raise ValueError(f"commission_pct must be >= 0: {self.commission_rate * 100}")

    def close(self) -> None:
        pass

    def ingest_bbo(self, tick: Any) -> None:
        ts_ms = int(getattr(tick, "ts_ms"))
        price = getattr(tick, "price", None)
        if price is None:
            price = getattr(tick, "close")
        prev_bid = self.bid
        prev_ask = self.ask
        self.bid = dec(getattr(tick, "bid", price) or price)
        self.ask = dec(getattr(tick, "ask", price) or price)
        if prev_bid is None or prev_ask is None:
            return
        for order in list(self.open):
            if order.kind != "trigger" or not _trigger_crosses(order, prev_bid, prev_ask, self.bid, self.ask):
                continue
            self.open.remove(order)
            fill_price = self._fill_price(order)
            fill = Fill(
                cloid=order.cloid,
                oid=order.oid,
                side=order.side,
                price=fill_price,
                size=order.size,
                fee=self._fee(fill_price, order.size),
                ts_ms=ts_ms,
                raw={"source": "simulator", "coin": order.symbol, "symbol": order.symbol, "bid": str(self.bid), "ask": str(self.ask), "trigger_price": str(order.trigger_price), "tpsl": order.tpsl},
            )
            self.seen_fills.append(fill)
            self.seen_updates.append(OrderUpdate(order.cloid, order.oid, "filled", {"source": "simulator"}))
            self._cancel_siblings(order)

    def place_orders(self, orders: list[Order], ts_ms: int) -> list[OrderResult]:
        results: list[OrderResult] = []
        filled_parents: set[str] = set()
        for order in orders:
            oid = self.next_oid
            self.next_oid += 1
            if order.kind == "market":
                fill_price = self._fill_price(order)
                fill = Fill(
                    cloid=order.cloid,
                    oid=oid,
                    side=order.side,
                    price=fill_price,
                    size=order.size,
                    fee=self._fee(fill_price, order.size),
                    ts_ms=ts_ms,
                    raw={"source": "simulator", "coin": order.symbol, "symbol": order.symbol, "bid": str(self.bid or ""), "ask": str(self.ask or "")},
                )
                self.seen_fills.append(fill)
                self.seen_updates.append(OrderUpdate(order.cloid, oid, "filled", {"source": "simulator"}))
                filled_parents.add(order.cloid)
                results.append(OrderResult(order.cloid, oid, "filled", [fill], {"source": "simulator"}))
            else:
                order.oid = oid
                status = "waitingForTrigger" if not order.parent_cloid or order.parent_cloid in filled_parents else "waitingForFill"
                order.status = status
                order.exchange_status = status
                self.open.append(order)
                self.seen_updates.append(OrderUpdate(order.cloid, oid, status, {"source": "simulator"}))
                results.append(OrderResult(order.cloid, oid, status, [], {"source": "simulator"}))
        return results

    def cancel_orders(self, orders: list[Order]) -> list[CancelResult]:
        results: list[CancelResult] = []
        for order in orders:
            self.open = [row for row in self.open if row.cloid != order.cloid]
            self.seen_updates.append(OrderUpdate(order.cloid, order.oid, "canceled", {"source": "simulator"}))
            results.append(CancelResult(order.cloid, order.oid, "canceled", {"source": "simulator"}))
        return results

    def open_orders(self) -> list[Order]:
        return list(self.open)

    def fills(self) -> list[Fill]:
        return list(self.seen_fills)

    def order_updates(self) -> list[OrderUpdate]:
        return list(self.seen_updates)

    def get_open_orders(self) -> list[dict[str, Any]]:
        return [_open_order_row(order) for order in self.open if order.status in OPEN_EXCHANGE_STATUS]

    def get_user_fills(self, start_time: int | None = None, end_time: int | None = None) -> list[dict[str, Any]]:
        rows = [_fill_row(fill) for fill in self.seen_fills]
        if start_time is not None:
            rows = [row for row in rows if int(row["time"]) >= start_time]
        if end_time is not None:
            rows = [row for row in rows if int(row["time"]) <= end_time]
        return rows

    def set_leverage(self, leverage: int) -> int:
        if leverage <= 0:
            raise ValueError(f"leverage must be positive: {leverage}")
        self.current_leverage = leverage
        return self.current_leverage

    def leverage(self) -> int:
        return self.current_leverage

    def balance(self) -> dict[str, Decimal]:
        raise NotImplementedError("simulator balance is not implemented")

    def _fill_price(self, order: Order) -> Decimal:
        if order.kind == "trigger" and order.trigger_price is not None:
            price = order.trigger_price
            return price * (Decimal("1") + self.slippage_rate) if order.side == "buy" else price * (Decimal("1") - self.slippage_rate)
        if order.side == "buy":
            price = self.ask if self.ask is not None else order.price
            return price * (Decimal("1") + self.slippage_rate)
        price = self.bid if self.bid is not None else order.price
        return price * (Decimal("1") - self.slippage_rate)

    def _fee(self, price: Decimal, size: Decimal) -> Decimal:
        return abs(price * size * self.commission_rate)

    def _cancel_siblings(self, filled: Order) -> None:
        if not filled.parent_cloid:
            return
        for order in list(self.open):
            if order.parent_cloid != filled.parent_cloid:
                continue
            self.open.remove(order)
            self.seen_updates.append(OrderUpdate(order.cloid, order.oid, "canceled", {"source": "simulator", "reason": "sibling_filled"}))


def fill_from_row(row: dict[str, Any]) -> Fill:
    side = str(row.get("side") or "").lower()
    if side in {"b", "buy"}:
        order_side = "buy"
    elif side in {"a", "ask", "sell"}:
        order_side = "sell"
    else:
        raise RuntimeError(f"recon fill has unknown side: {row.get('side')}")
    return Fill(
        cloid=str(row.get("cloid") or ""),
        oid=int(row["oid"]) if row.get("oid") is not None else None,
        side=order_side,
        price=dec(row.get("px")),
        size=dec(row.get("sz")),
        fee=dec(row.get("fee") or 0),
        ts_ms=int(row.get("time") or row.get("timestamp_ms") or 0),
        raw=dict(row),
    )


def recon_order_updates(ledger: TradeLedger, open_orders: list[dict[str, Any]], fills: list[Fill]) -> list[OrderUpdate]:
    open_cloids = {str(row.get("cloid") or "") for row in open_orders}
    open_oids = {int(row["oid"]) for row in open_orders if row.get("oid") is not None}
    fills_by_cloid = {fill.cloid for fill in fills if fill.cloid}
    fills_by_oid = {fill.oid for fill in fills if fill.oid is not None}
    updates = [
        OrderUpdate(str(row.get("cloid") or ""), int(row["oid"]) if row.get("oid") is not None else None, str(row.get("status") or "open"), dict(row))
        for row in open_orders
    ]
    for _, order in ledger.open_orders():
        if order.cloid in open_cloids or (order.oid is not None and order.oid in open_oids):
            continue
        if _filled_from_evidence(order, fills, fills_by_cloid, fills_by_oid):
            updates.append(OrderUpdate(order.cloid, order.oid, "filled", {"source": "recon", "reason": "fill_absent_from_open_orders"}))
        elif order.oid is not None:
            updates.append(OrderUpdate(order.cloid, order.oid, "canceled", {"source": "recon", "reason": "missing_from_open_orders"}))
    return updates


def _filled_from_evidence(order: Order, fills: list[Fill], fills_by_cloid: set[str], fills_by_oid: set[int]) -> bool:
    if order.cloid not in fills_by_cloid and (order.oid is None or order.oid not in fills_by_oid):
        return False
    size = Decimal("0")
    for fill in fills:
        if (order.cloid and fill.cloid == order.cloid) or (order.oid is not None and fill.oid == order.oid):
            size += fill.size
    return size >= order.size


def _trigger_crosses(order: Order, prev_bid: Decimal, prev_ask: Decimal, bid: Decimal, ask: Decimal) -> bool:
    if order.kind != "trigger" or order.trigger_price is None:
        return False
    if order.side == "sell" and order.tpsl == "tp":
        return prev_bid < order.trigger_price <= bid
    if order.side == "buy" and order.tpsl == "tp":
        return prev_ask > order.trigger_price >= ask
    if order.side == "sell" and order.tpsl == "sl":
        return prev_bid > order.trigger_price >= bid
    if order.side == "buy" and order.tpsl == "sl":
        return prev_ask < order.trigger_price <= ask
    return False


def _fill_row(fill: Fill) -> dict[str, Any]:
    return {
        "coin": str(fill.raw.get("coin") or ""),
        "symbol": str(fill.raw.get("coin") or ""),
        "px": str(fill.price),
        "sz": str(fill.size),
        "avg_px": str(fill.price),
        "filled_size": str(fill.size),
        "side": "B" if fill.side == "buy" else "A",
        "time": fill.ts_ms,
        "hash": fill.key(),
        "oid": fill.oid,
        "crossed": True,
        "fee": str(fill.fee),
        "tid": fill.key(),
        "feeToken": "USDC",
        "cloid": fill.cloid,
        "fill_key": fill.key(),
        **fill.raw,
    }


def _open_order_row(order: Order) -> dict[str, Any]:
    return {
        "coin": order.symbol,
        "symbol": order.symbol,
        "cloid": order.cloid,
        "oid": order.oid,
        "side": "B" if order.side == "buy" else "A",
        "sz": str(order.size),
        "px": str(order.price),
        "status": order.status,
    }
