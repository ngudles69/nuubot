from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from nuubot.core.context import IdCtx
from nuubot.core.dtypes import Bar, BotRunResult, DataReq, Signal
from nuubot.core.format import format_ms
from nuubot.core.logger import logger
from nuubot.datastore import Datastore, Fill, Order, Position
from nuubot.datastore.schemas import AccountRow, BotrunRow, PositionRow

log = logger("runtime.log")


@dataclass
class TradeConfig:
    config_id: int
    take_profit_pct: float
    stop_loss_pct: float
    max_cycles: int
    symbol: str = ""
    acct_id: str = "default"
    simulator_slippage_pct: float = 0.05
    simulator_commission_pct: float = 0.05
    simulator_recon_interval_ms: int = 60_000
    investment_usdc: float = 10000.0
    trade_use: str = "pct"
    trade_amount: float = 100.0
    trade_pct: float = 2.0
    trade_usdc: float | None = None


class TradeLedger:
    def __init__(
        self,
        datastore: Datastore,
        db: Path,
        ctx: IdCtx,
    ) -> None:
        self.datastore = datastore
        self.db = db
        self.ctx = ctx
        self.base_bot_id = ctx.bot_id
        self.current_bot_id: int | None = ctx.bot_id
        self.next_botrun_index = 1

    def start(self) -> None:
        """Start the trade ledger for the active botrun."""

        # Save account state.
        tx = self.datastore.tx(self.db)
        tx.start()
        try:
            tx.upsert(
                AccountRow(
                    acct_id=self.ctx.account_id,
                    bot_id=self.ctx.bot_id,
                    role="trade",
                    name=self.ctx.account_id,
                    exec_network="sweep",
                    status="active",
                ),
            )
            botrun = tx.get(BotrunRow, botrun_id=self.current_bot_id)
            botrun.status = "running"
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    def open_position(self, side: str, price: float, ts_ms: int) -> int:
        """Open a ledger position for a trade entry."""

        # Allocate botrun.
        bot_id = self._bot_id()
        position_id = bot_id
        order_side = "buy" if side == "long" else "sell"
        position = Position(self.ctx, side=side, price=price, ts_ms=ts_ms)

        # Save entry ledger.
        tx = self.datastore.tx(self.db)
        tx.start()
        try:
            tx.insert(position.row())
            order = self._add_order(tx, bot_id, position_id, order_side, price, ts_ms, reduceonly=False)
            self._add_fill(tx, bot_id, order.id, order_side, price, ts_ms, closed_pnl=None)
            tx.commit()
            return position_id
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    def close_position(self, position_id: int, side: str, price: float, change_pct: float, reason: str, ts_ms: int) -> None:
        """Close a ledger position for a trade exit."""

        # Validate active botrun.
        bot_id = self.current_bot_id
        if bot_id is None:
            raise RuntimeError("active trade missing bot_id")

        # Save exit ledger.
        order_side = "sell" if side == "long" else "buy"
        tx = self.datastore.tx(self.db)
        tx.start()
        try:
            position = tx.get(PositionRow, position_id=position_id)
            entry_price = float(position.avg_entry_px)
            pnl_cash = price - entry_price if side == "long" else entry_price - price
            order = self._add_order(tx, bot_id, position_id, order_side, price, ts_ms, reduceonly=True)
            self._add_fill(tx, bot_id, order.id, order_side, price, ts_ms, closed_pnl=pnl_cash)
            position.status = "closed"
            position.current_sz = "0"
            position.avg_exit_px = str(price)
            position.mark_px = str(price)
            position.exit_cash = str(price)
            position.open_entry_cash = "0"
            position.gross_pnl = str(pnl_cash)
            position.realized_pnl = str(pnl_cash)
            position.net_pnl = str(pnl_cash)
            position.closed_ts = ts_ms
            position.last_update_ts = ts_ms
            position.exit_reason = reason
            botrun = tx.get(BotrunRow, botrun_id=bot_id)
            botrun.status = "complete"
            botrun.results_json = json.dumps({"position_id": position_id, "pnl_pct": change_pct, "exit_reason": reason}, sort_keys=True, separators=(",", ":"))
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()
        self.current_bot_id = None

    def _bot_id(self) -> int:
        """Return the active botrun ID or create the next one."""

        if self.current_bot_id is not None:
            return self.current_bot_id

        # Create botrun.
        tx = self.datastore.tx(self.db)
        tx.start()
        try:
            next_bot_id = self.base_bot_id * 1_000_000 + self.next_botrun_index
            botrun = BotrunRow(
                botrun_id=next_bot_id,
                sweeprun_id=self.ctx.sweeprun_id,
                bot_id=next_bot_id,
                botrun_index=self.next_botrun_index,
                config_json=json.dumps(self.ctx.bot_config.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
                results_json="{}",
                status="running",
            )
            tx.insert(botrun)
            self.current_bot_id = next_bot_id
            self.ctx.bot_id = next_bot_id
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()
        self.next_botrun_index += 1
        return self.current_bot_id

    def _add_order(self, tx: Any, bot_id: int, position_id: int, side: str, price: float, ts_ms: int, *, reduceonly: bool) -> Order:
        self.ctx.bot_id = bot_id
        order = Order(self.ctx, position_id=position_id, side=side, price=price, ts_ms=ts_ms, reduceonly=reduceonly)
        tx.insert(order.row())
        return order

    def _add_fill(self, tx: Any, bot_id: int, order_id: int, side: str, price: float, ts_ms: int, *, closed_pnl: float | None) -> Fill:
        self.ctx.bot_id = bot_id
        fill = Fill(self.ctx, order_id=order_id, side=side, price=price, ts_ms=ts_ms, closed_pnl=closed_pnl)
        tx.insert(fill.row())
        return fill


class MemoryTradeLedger:
    def __init__(self) -> None:
        self.next_position_id = 1

    def start(self) -> None:
        pass

    def open_position(self, side: str, price: float, ts_ms: int) -> int:
        _ = side, price, ts_ms
        position_id = self.next_position_id
        self.next_position_id += 1
        return position_id

    def close_position(self, position_id: int, side: str, price: float, change_pct: float, reason: str, ts_ms: int) -> None:
        _ = position_id, side, price, change_pct, reason, ts_ms


class ExecutorTrade:
    def __init__(self, config: TradeConfig, run_log=log, ledger: Any | None = None) -> None:
        self.config = config
        self.log = run_log
        self.ledger = ledger or MemoryTradeLedger()
        self.active = False
        self.side = ""
        self.entry_price = 0.0
        self.position_id: int | None = None
        self.pnl_pct = 0.0
        self.peak_pct = 0.0
        self.max_drawdown_pct = 0.0
        self.wins = 0
        self.losses = 0
        self.trades = 0
        self.cycle_id = 0
        self.cycle_count = 0

    async def init(self) -> None:
        pass

    def data_req(self, interval: str) -> list[DataReq]:
        return [DataReq(self.config.symbol, interval, 0)]

    async def start(self) -> None:
        self.ledger.start()

    async def loop_once(self, bar: Bar, signal: Signal) -> None:
        """Process one trade event."""

        # Exit active trade.
        closed = False
        if self.active:
            self._update_drawdown(bar.close)
            signal_price = bar.open
            signal_change_pct = self._change_pct(signal_price)
            if self.side == "long" and signal.exit:
                self._close(signal_price, signal_change_pct, signal.reason, bar.ts_ms)
                closed = True
            elif self.side == "short" and signal.entry:
                self._close(signal_price, signal_change_pct, signal.reason, bar.ts_ms)
                closed = True
            elif self._take_profit_hit(bar):
                price = self._take_profit_price()
                self._close(price, self._change_pct(price), "take_profit", bar.ts_ms)
                closed = True
            elif self._stop_loss_hit(bar):
                price = self._stop_loss_price()
                self._close(price, self._change_pct(price), "stop_loss", bar.ts_ms)
                closed = True

        # Enter new trade.
        if not self.active and not closed and self._can_enter():
            if signal.entry:
                self._open(bar, "long", bar.open)
            elif signal.exit:
                self._open(bar, "short", bar.open)

    async def stop(self, bar: Bar | None = None) -> None:
        if self.active and bar is not None:
            self._close(bar.close, self._change_pct(bar.close), "stop", bar.ts_ms)

    async def exit(self) -> bool:
        return self.config.max_cycles > 0 and self.cycle_count >= self.config.max_cycles and not self.active

    def result(self, ticks: int) -> BotRunResult:
        return BotRunResult(
            config_id=self.config.config_id,
            pnl_pct=self.pnl_pct,
            wins=self.wins,
            losses=self.losses,
            trades=self.trades,
            max_drawdown_pct=self.max_drawdown_pct,
            ticks=ticks,
            cycles=self.cycle_count,
        )

    def _open(self, bar: Bar, side: str, price: float) -> None:
        self.cycle_id += 1
        self.trades += 1
        self.side = side
        self.entry_price = price
        self.active = True
        self.position_id = self.ledger.open_position(side, price, bar.ts_ms)
        self.log.info(f"trade_open cycle={self.cycle_id} side={side} price={price} ts_now: {format_ms(bar.ts_ms)}")

    def _close(self, price: float, change_pct: float, reason: str, now_ms: int) -> None:
        """Close the active in-memory trade state."""

        if self.position_id is None:
            raise RuntimeError("active trade missing position_id")
        self.ledger.close_position(self.position_id, self.side, price, change_pct, reason, now_ms)
        self.pnl_pct += change_pct
        self.wins += int(change_pct >= 0)
        self.losses += int(change_pct < 0)
        self.cycle_count += 1
        self.active = False
        self.side = ""
        self.entry_price = 0.0
        self.position_id = None
        self.log.info(f"trade_close cycle={self.cycle_id} reason={reason} pnl_pct={change_pct:.4f} total_pnl_pct={self.pnl_pct:.4f} ts_now: {format_ms(now_ms)}")

    def _can_enter(self) -> bool:
        return self.config.max_cycles == 0 or self.cycle_count < self.config.max_cycles

    def _change_pct(self, price: float) -> float:
        change = (price - self.entry_price) / self.entry_price * 100
        return change if self.side != "short" else -change

    def _take_profit_hit(self, bar: Bar) -> bool:
        if self.config.take_profit_pct <= 0:
            return False
        return bar.high >= self._take_profit_price() if self.side == "long" else bar.low <= self._take_profit_price()

    def _stop_loss_hit(self, bar: Bar) -> bool:
        if self.config.stop_loss_pct <= 0:
            return False
        return bar.low <= self._stop_loss_price() if self.side == "long" else bar.high >= self._stop_loss_price()

    def _take_profit_price(self) -> float:
        pct = self.config.take_profit_pct / 100
        return self.entry_price * (1 + pct if self.side == "long" else 1 - pct)

    def _stop_loss_price(self) -> float:
        pct = self.config.stop_loss_pct / 100
        return self.entry_price * (1 - pct if self.side == "long" else 1 + pct)

    def _update_drawdown(self, price: float) -> None:
        equity = self.pnl_pct + self._change_pct(price)
        self.peak_pct = max(self.peak_pct, equity)
        self.max_drawdown_pct = max(self.max_drawdown_pct, self.peak_pct - equity)
