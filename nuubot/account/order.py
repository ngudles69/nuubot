from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from nuubot.account.fill import Fill

TERMINAL_ORDER_STATUS = {"filled", "canceled", "rejected", "error", "closed"}


@dataclass(frozen=True)
class OrderUpdate:
    cloid: str
    oid: int | None
    status: str
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OrderResult:
    cloid: str
    oid: int | None
    status: str
    fills: list[Fill] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def update(self) -> OrderUpdate:
        return OrderUpdate(self.cloid, self.oid, self.status, self.raw)


@dataclass(frozen=True)
class CancelResult:
    cloid: str
    oid: int | None
    status: str
    raw: dict = field(default_factory=dict)

    def update(self) -> OrderUpdate:
        return OrderUpdate(self.cloid, self.oid, self.status, self.raw)


@dataclass
class Order:
    symbol: str
    side: str
    size: Decimal
    price: Decimal
    cloid: str
    role: str = "entry"
    reduce_only: bool = False
    kind: str = "market"
    trigger_price: Decimal | None = None
    tpsl: str = ""
    parent_cloid: str = ""
    position_id: int = 0
    oid: int | None = None
    status: str = "planned"
    exchange_status: str = ""
    filled_size: Decimal = Decimal("0")
    avg_fill_price: Decimal = Decimal("0")
    fee: Decimal = Decimal("0")
    remaining_size: Decimal | None = None
    terminal_reason: str = ""
    fills: list[Fill] = field(default_factory=list)

    def init(self) -> None:
        if not self.symbol:
            raise ValueError("order requires symbol")
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"order side must be buy or sell: {self.side}")
        if self.size <= 0:
            raise ValueError(f"order size must be positive: {self.size}")
        if not self.cloid:
            raise ValueError("order requires cloid")
        if self.kind == "trigger":
            if self.trigger_price is None:
                raise ValueError("trigger order requires trigger_price")
            if self.tpsl not in {"tp", "sl"}:
                raise ValueError(f"trigger order tpsl must be tp or sl: {self.tpsl}")
        self.remaining_size = self.size

    def close(self) -> None:
        self.status = "closed"
        self.terminal_reason = "closed"

    def update(self, update: OrderUpdate) -> bool:
        if self.terminal():
            return False
        if update.oid is not None:
            self.oid = update.oid
        self.exchange_status = update.status
        self.status = update.status
        self.recalc()
        return True

    def record_fill(self, fill: Fill) -> bool:
        if fill.key() in {row.key() for row in self.fills}:
            return False

        # Record exchange fill.
        fill.init()
        old_size = self.filled_size
        self.fills.append(fill)
        self.filled_size += fill.size
        self.fee += fill.fee
        if self.filled_size:
            self.avg_fill_price = ((self.avg_fill_price * old_size) + (fill.price * fill.size)) / self.filled_size
        self.recalc()
        return True

    def recalc(self) -> None:
        self.remaining_size = max(self.size - self.filled_size, Decimal("0"))
        if self.exchange_status in TERMINAL_ORDER_STATUS:
            self.terminal_reason = self.exchange_status
        if self.filled_size > 0 and self.exchange_status == "filled":
            self.status = "filled"
            self.terminal_reason = "filled"
        elif self.filled_size > 0 and self.exchange_status in {"canceled", "rejected"}:
            self.status = "partial"
            self.terminal_reason = self.exchange_status

    def signed_size(self) -> Decimal:
        return self.filled_size if self.side == "buy" else -self.filled_size

    def signed_cash(self) -> Decimal:
        cash = self.avg_fill_price * self.filled_size
        return -cash if self.side == "buy" else cash

    def is_open(self) -> bool:
        return not self.terminal()

    def terminal(self) -> bool:
        return bool(self.terminal_reason)
