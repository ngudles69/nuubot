from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from nuubot.account.ledger import TradeLedger
from nuubot.account.order import CancelResult, Order, OrderResult
from nuubot.account.position import TradePosition
from nuubot.exchange.simulator import Simulator, fill_from_row, recon_order_updates


@dataclass(frozen=True)
class ReconResult:
    fills_seen: int
    fills_recorded: int
    orders_updated: int
    positions_changed: int


class TradingAccount:
    def __init__(self, ledger: TradeLedger | None = None, simulator: Simulator | None = None) -> None:
        self.ledger = ledger or TradeLedger()
        self.simulator = simulator or Simulator()

    def init(self) -> None:
        self.ledger.init()
        self.simulator.init()

    def close(self) -> None:
        self.ledger.close()
        self.simulator.close()

    def ingest_bbo(self, tick: object) -> None:
        self.simulator.ingest_bbo(tick)

    def place_position(self, position: TradePosition, ts_ms: int) -> list[OrderResult]:
        return self.place_orders(position.orders, ts_ms)

    def place_orders(self, orders: list[Order], ts_ms: int) -> list[OrderResult]:
        results = self.simulator.place_orders(orders, ts_ms)
        changed: set[int] = set()
        for result in results:
            changed |= self.ledger.record_fills(result.fills)
        changed |= self.ledger.update_orders([result.update() for result in results])
        self.ledger.recalc(changed)
        self.ledger.save_changed()
        return results

    def cancel_orders(self, orders: list[Order]) -> list[CancelResult]:
        results = self.simulator.cancel_orders(orders)
        changed = self.ledger.update_orders([result.update() for result in results])
        self.ledger.recalc(changed)
        self.ledger.save_changed()
        return results

    def close_positions(self, positions: list[TradePosition], price: Decimal, ts_ms: int, reason: str) -> None:
        # Cancel open exit orders.
        cancel_orders = [order for position in positions for order in position.open_orders()]
        if cancel_orders:
            self.cancel_orders(cancel_orders)

        # Submit cleanup closes.
        close_orders: list[Order] = []
        for position in positions:
            position.recalc()
            if position.net_size == 0:
                continue
            side = "sell" if position.net_size > 0 else "buy"
            order = Order(
                symbol=position.symbol,
                side=side,
                size=abs(position.net_size),
                price=price,
                cloid=f"{reason}-{position.position_id}-{ts_ms}",
                role="close",
                reduce_only=True,
            )
            position.add_order(order)
            close_orders.append(order)
        if close_orders:
            self.place_orders(close_orders, ts_ms)

    def recon(self, ts_ms: int, reason: str) -> ReconResult:
        _ = reason
        raw_fills = self.simulator.get_user_fills(end_time=ts_ms)
        open_orders = self.simulator.get_open_orders()
        fills = [fill_from_row(row) for row in raw_fills]
        updates = recon_order_updates(self.ledger, open_orders, fills)
        changed, fills_recorded = self.ledger.record_fills_count(fills)
        changed |= self.ledger.update_orders(updates)
        self.ledger.recalc(changed)
        self.ledger.save_changed()
        return ReconResult(len(raw_fills), fills_recorded, len(updates), len(changed))

    def set_leverage(self, leverage: int) -> int:
        return self.simulator.set_leverage(leverage)

    def leverage(self) -> int:
        return self.simulator.leverage()

    def balance(self) -> dict[str, Decimal]:
        return self.simulator.balance()
