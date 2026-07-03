from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from nuubot.account.fill import Fill
from nuubot.account.order import Order, OrderUpdate
from nuubot.account.position import TradePosition


@dataclass
class LedgerState:
    positions_count: int
    open_positions_count: int
    closed_positions_count: int
    wins: int
    losses: int
    pnl: Decimal


class TradeLedger:
    def __init__(self) -> None:
        self.positions: list[TradePosition] = []
        self.next_position_id = 1

    def init(self) -> None:
        self.load()

    def close(self) -> None:
        self.save()

    def load(self) -> None:
        for position in self.positions:
            position.load()

    def save(self) -> None:
        for position in self.positions:
            position.save()

    def create_position(self, symbol: str) -> TradePosition:
        position = TradePosition(self.next_position_id, symbol)
        position.init()
        self.next_position_id += 1
        self.positions.append(position)
        return position

    def open_positions(self) -> list[TradePosition]:
        return [position for position in self.positions if position.is_open()]

    def position(self, position_id: int) -> TradePosition:
        for position in self.positions:
            if position.position_id == position_id:
                return position
        raise RuntimeError(f"position missing from ledger: {position_id}")

    def open_orders(self) -> list[tuple[TradePosition, Order]]:
        out: list[tuple[TradePosition, Order]] = []
        for position in self.open_positions():
            for order in position.open_orders():
                out.append((position, order))
        return out

    def find_open_order(self, *, cloid: str = "", oid: int | None = None) -> tuple[TradePosition, Order] | None:
        for position, order in self.open_orders():
            if cloid and order.cloid == cloid:
                return position, order
            if oid is not None and order.oid == oid:
                return position, order
        return None

    def update_orders(self, updates: list[OrderUpdate]) -> set[int]:
        changed: set[int] = set()
        for update in updates:
            found = self.find_open_order(cloid=update.cloid, oid=update.oid)
            if found is None:
                continue
            position, order = found
            if order.update(update):
                position.recalc()
                changed.add(position.position_id)
        return changed

    def record_fills(self, fills: list[Fill]) -> tuple[set[int], int]:
        changed: set[int] = set()
        recorded = 0
        for fill in fills:
            found = self.find_open_order(cloid=fill.cloid, oid=fill.oid)
            if found is None:
                continue
            position, order = found
            if order.record_fill(fill):
                position.recalc()
                changed.add(position.position_id)
                recorded += 1
        return changed, recorded

    def recalc(self, position_ids: set[int]) -> None:
        for position in self.positions:
            if position.position_id in position_ids:
                position.recalc()

    def save_changed(self) -> None:
        for position in self.positions:
            if position.changed:
                position.save()

    def state(self) -> LedgerState:
        closed = [position for position in self.positions if position.status == "closed"]
        pnl = self.pnl()
        return LedgerState(
            positions_count=len(self.positions),
            open_positions_count=len(self.open_positions()),
            closed_positions_count=len(closed),
            wins=sum(1 for position in closed if position.pnl() >= 0),
            losses=sum(1 for position in closed if position.pnl() < 0),
            pnl=pnl,
        )

    def pnl(self) -> Decimal:
        return sum((position.pnl() for position in self.positions if position.status == "closed"), Decimal("0"))
