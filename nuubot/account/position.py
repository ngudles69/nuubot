from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from nuubot.account.fill import Fill
from nuubot.account.order import Order, OrderUpdate

TERMINAL_POSITION_STATUS = {"closed", "canceled", "error"}


@dataclass
class PositionState:
    status: str
    terminal: bool
    net_size: Decimal
    pnl: Decimal


@dataclass
class TradePosition:
    position_id: int
    symbol: str
    orders: list[Order] = field(default_factory=list)
    status: str = "pending"
    net_size: Decimal = Decimal("0")
    pnl_value: Decimal = Decimal("0")
    changed: bool = False

    def init(self) -> None:
        if self.position_id <= 0:
            raise ValueError(f"position_id must be positive: {self.position_id}")
        if not self.symbol:
            raise ValueError("position requires symbol")

    def close(self) -> None:
        self.recalc()
        if self.net_size != 0:
            raise RuntimeError(f"position {self.position_id} cannot close with net_size={self.net_size}")
        self.status = "closed"
        self.changed = True

    def load(self) -> None:
        self.init()
        self.recalc()

    def save(self) -> None:
        self.changed = False

    def add_order(self, order: Order) -> None:
        order.position_id = self.position_id
        order.init()
        self.orders.append(order)
        self.changed = True

    def open_orders(self) -> list[Order]:
        if self.terminal():
            return []
        return [order for order in self.orders if order.is_open()]

    def find_open_order(self, *, cloid: str = "", oid: int | None = None) -> Order | None:
        for order in self.open_orders():
            if cloid and order.cloid == cloid:
                return order
            if oid is not None and order.oid == oid:
                return order
        return None

    def update_order(self, update: OrderUpdate) -> bool:
        order = self.find_open_order(cloid=update.cloid, oid=update.oid)
        if order is None:
            return False
        changed = order.update(update)
        if changed:
            self.recalc()
        return changed

    def record_fill(self, fill: Fill) -> bool:
        order = self.find_open_order(cloid=fill.cloid, oid=fill.oid)
        if order is None:
            return False
        changed = order.record_fill(fill)
        if changed:
            self.recalc()
        return changed

    def recalc(self) -> None:
        self.net_size = sum((order.signed_size() for order in self.orders), Decimal("0"))
        fees = sum((order.fee for order in self.orders), Decimal("0"))
        cash = sum((order.signed_cash() for order in self.orders), Decimal("0"))
        self.pnl_value = cash - fees
        all_terminal = bool(self.orders) and all(order.terminal() for order in self.orders)
        any_fill = any(order.filled_size > 0 for order in self.orders)
        if all_terminal and not any_fill:
            self.status = "canceled"
        elif all_terminal and self.net_size == 0:
            self.status = "closed"
        elif self.net_size == 0:
            self.status = "flat"
        else:
            self.status = "open"
        self.changed = True

    def state(self) -> PositionState:
        return PositionState(self.status, self.terminal(), self.net_size, self.pnl_value)

    def pnl(self) -> Decimal:
        return self.pnl_value

    def is_open(self) -> bool:
        return not self.terminal()

    def terminal(self) -> bool:
        return self.status in TERMINAL_POSITION_STATUS
