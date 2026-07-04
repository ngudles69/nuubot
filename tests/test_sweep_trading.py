from __future__ import annotations

from decimal import Decimal

from nuubot.account import Fill, Order, OrderUpdate, TradeLedger, TradingAccount
from nuubot.exchange import Simulator


def main() -> None:
    test_fill_requires_positive_size()
    test_order_records_fill_and_terminal_state()
    test_terminal_orders_leave_open_lookup()
    test_terminal_positions_leave_open_lookup()
    test_position_pnl_uses_entry_and_exit_fills()
    test_simulator_trigger_order_reconciles_from_fills()
    test_simulator_trigger_fills_at_submitted_price_with_slippage()
    test_simulator_balance_fails_loud()
    test_order_submit_ts_is_write_once()
    test_recon_keeps_partial_missing_order_partial()
    test_recon_does_not_double_count_cumulative_partial_fills()


def test_fill_requires_positive_size() -> None:
    fill = Fill("entry-1", 1, "buy", Decimal("100"), Decimal("0"), Decimal("0"), 1)

    try:
        fill.init()
    except ValueError as exc:
        assert "fill size must be positive" in str(exc)
    else:
        raise AssertionError("zero-size fill passed")


def test_order_records_fill_and_terminal_state() -> None:
    order = Order("BTC", "buy", Decimal("2"), Decimal("100"), "entry-1")
    order.init()

    assert order.record_fill(Fill("entry-1", 1, "buy", Decimal("100"), Decimal("1"), Decimal("0"), 1))
    assert order.record_fill(Fill("entry-1", 1, "buy", Decimal("110"), Decimal("1"), Decimal("0"), 2))
    assert order.filled_size == Decimal("2")
    assert order.avg_fill_price == Decimal("105")

    order.update(OrderUpdate("entry-1", 1, "filled"))
    assert order.terminal()
    assert order.remaining_size == Decimal("0")


def test_terminal_orders_leave_open_lookup() -> None:
    ledger = TradeLedger()
    account = TradingAccount(ledger=ledger, simulator=Simulator(0, 0))
    account.init()

    position = ledger.create_position("BTC")
    order = Order("BTC", "buy", Decimal("1"), Decimal("100"), "entry-1")
    position.add_order(order)
    account.place_position(position, 1)

    assert ledger.find_open_order(cloid="entry-1") is None
    assert position.status == "open"
    assert position.net_size == Decimal("1")


def test_terminal_positions_leave_open_lookup() -> None:
    ledger = TradeLedger()
    account = TradingAccount(ledger=ledger, simulator=Simulator(0, 0))
    account.init()

    position = ledger.create_position("BTC")
    entry = Order("BTC", "buy", Decimal("1"), Decimal("100"), "entry-1")
    close = Order("BTC", "sell", Decimal("1"), Decimal("110"), "close-1", reduce_only=True)
    position.add_order(entry)
    account.place_position(position, 1)
    position.add_order(close)
    account.place_orders([close], 2)

    assert position.status == "closed"
    assert ledger.open_positions() == []
    assert ledger.find_open_order(cloid="close-1") is None
    assert ledger.state().wins == 1


def test_position_pnl_uses_entry_and_exit_fills() -> None:
    ledger = TradeLedger()
    account = TradingAccount(ledger=ledger, simulator=Simulator(0, 0))
    account.init()

    position = ledger.create_position("BTC")
    entry = Order("BTC", "buy", Decimal("1"), Decimal("100"), "entry-1")
    exit_order = Order("BTC", "sell", Decimal("1"), Decimal("125"), "exit-1", reduce_only=True)
    position.add_order(entry)
    account.place_position(position, 1)
    position.add_order(exit_order)
    account.place_orders([exit_order], 2)

    assert position.status == "closed"
    assert position.pnl() == Decimal("25")


def test_simulator_trigger_order_reconciles_from_fills() -> None:
    ledger = TradeLedger()
    account = TradingAccount(ledger=ledger, simulator=Simulator(0, 0))
    account.init()

    position = ledger.create_position("BTC")
    entry = Order("BTC", "buy", Decimal("1"), Decimal("100"), "entry-1")
    tp = Order("BTC", "sell", Decimal("1"), Decimal("103"), "tp-1", "take_profit", True, "trigger", Decimal("103"), "tp", "entry-1")
    sl = Order("BTC", "sell", Decimal("1"), Decimal("99"), "sl-1", "stop_loss", True, "trigger", Decimal("99"), "sl", "entry-1")
    position.add_order(entry)
    position.add_order(tp)
    position.add_order(sl)
    account.ingest_bbo(type("Tick", (), {"ts_ms": 0, "close": 100})())
    account.place_position(position, 1)
    open_rows = account.simulator.get_open_orders()

    assert len(open_rows) == 2
    assert {row["status"] for row in open_rows} == {"waitingForTrigger"}
    assert {row["coin"] for row in open_rows} == {"BTC"}

    account.ingest_bbo(type("Tick", (), {"ts_ms": 2, "close": 103})())
    assert account.simulator.fills()
    fill_rows = account.simulator.get_user_fills(end_time=2)
    result = account.recon(2, "tick")

    assert fill_rows[-1]["coin"] == "BTC"
    assert fill_rows[-1]["side"] == "A"
    assert fill_rows[-1]["px"] == "103"
    assert fill_rows[-1]["sz"] == "1"
    assert fill_rows[-1]["time"] == 2
    assert fill_rows[-1]["cloid"] == "tp-1"
    assert result.fills_recorded == 1
    assert position.status == "closed"
    assert tp.status == "filled"
    assert sl.status == "canceled"
    assert position.pnl() == Decimal("3")


def test_simulator_trigger_fills_at_submitted_price_with_slippage() -> None:
    ledger = TradeLedger()
    account = TradingAccount(ledger=ledger, simulator=Simulator(Decimal("0.05"), 0))
    account.init()

    position = ledger.create_position("BTC")
    entry = Order("BTC", "buy", Decimal("1"), Decimal("100"), "entry-1")
    tp = Order("BTC", "sell", Decimal("1"), Decimal("103"), "tp-1", "take_profit", True, "trigger", Decimal("103"), "tp", "entry-1")
    position.add_order(entry)
    position.add_order(tp)
    account.ingest_bbo(type("Tick", (), {"ts_ms": 0, "bid": 100, "ask": 100, "close": 100})())
    account.place_position(position, 1)

    account.ingest_bbo(type("Tick", (), {"ts_ms": 2, "bid": 110, "ask": 110, "close": 110})())
    assert len(account.simulator.fills()) == 2
    assert tp.filled_size == Decimal("0")
    account.recon(2, "tick")

    assert tp.avg_fill_price == Decimal("102.9485")


def test_simulator_balance_fails_loud() -> None:
    account = TradingAccount(simulator=Simulator(0, 0))
    account.init()

    try:
        account.balance()
    except NotImplementedError as exc:
        assert "simulator balance" in str(exc)
    else:
        raise AssertionError("simulator returned fake balance")


def test_order_submit_ts_is_write_once() -> None:
    account = TradingAccount(simulator=Simulator(0, 0))
    account.init()
    position = account.create_position("BTC")
    order = Order("BTC", "buy", Decimal("1"), Decimal("100"), "entry-1")
    position.add_order(order)
    account.place_position(position, 1)

    try:
        account.place_orders([order], 2)
    except RuntimeError as exc:
        assert "order already submitted" in str(exc)
        assert "entry-1" in str(exc)
    else:
        raise AssertionError("duplicate order submit overwrote submit_ts")

    assert order.submit_ts == 1


def test_recon_keeps_partial_missing_order_partial() -> None:
    ledger = TradeLedger()
    account = TradingAccount(ledger=ledger)
    account.init()

    position = ledger.create_position("BTC")
    order = Order("BTC", "buy", Decimal("1"), Decimal("100"), "entry-1", kind="limit")
    position.add_order(order)
    account.place_position(position, 1)
    account.simulator.open = []
    account.simulator.seen_fills.append(Fill("entry-1", order.oid, "buy", Decimal("100"), Decimal("0.7"), Decimal("0"), 2))

    result = account.recon(2, "partial")

    assert result.fills_recorded == 1
    assert order.status == "partial"
    assert order.terminal_reason == "canceled"
    assert order.filled_size == Decimal("0.7")
    assert order.remaining_size == Decimal("0.3")
    assert position.status == "open"


def test_recon_does_not_double_count_cumulative_partial_fills() -> None:
    ledger = TradeLedger()
    account = TradingAccount(ledger=ledger)
    account.init()

    position = ledger.create_position("BTC")
    order = Order("BTC", "buy", Decimal("1"), Decimal("100"), "entry-1", kind="limit")
    position.add_order(order)
    account.place_position(position, 1)
    account.simulator.seen_fills.append(Fill("entry-1", order.oid, "buy", Decimal("100"), Decimal("0.7"), Decimal("0"), 2))

    first = account.recon(2, "partial_open")
    account.simulator.open = []
    second = account.recon(3, "partial_gone")

    assert first.fills_recorded == 1
    assert second.fills_recorded == 0
    assert order.status == "partial"
    assert order.terminal_reason == "canceled"
    assert order.filled_size == Decimal("0.7")
    assert order.remaining_size == Decimal("0.3")
    assert position.status == "open"

if __name__ == "__main__":
    main()
