from __future__ import annotations

from typing import Any

from nuubot.bots.executors.tradebot.tradebot import MemoryTradeLedger, TradeConfig
from nuubot.core.dtypes import Bar, BotRunResult
from nuubot.core.format import format_ms
from nuubot.sweeps.signalers import SwSignal


class SwTradeBot:
    def __init__(self, config: TradeConfig, run_log: Any, ledger: Any | None = None) -> None:
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

    async def start(self) -> None:
        self.ledger.start()

    async def loop_once(self, bar: Bar, signal: SwSignal) -> None:
        """Process one trade event."""

        # Exit active trade.
        closed = False
        if self.active:
            self._update_drawdown(bar.close)
            signal_price = bar.open
            signal_change_pct = self._change_pct(signal_price)
            if self.side == "long" and signal.exit_long:
                self._close(signal_price, signal_change_pct, signal.reason, bar.ts_ms)
                closed = True
            elif self.side == "short" and signal.exit_short:
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
            if signal.enter_long:
                self._open(bar, "long", bar.open)
            elif signal.enter_short:
                self._open(bar, "short", bar.open)

    async def stop(self, bar: Bar | None = None) -> None:
        if self.active and bar is not None:
            self._close(bar.close, self._change_pct(bar.close), "stop", bar.ts_ms)

    async def exit(self) -> bool:
        return self.config.max_cycles > 0 and self.cycle_count >= self.config.max_cycles and not self.active

    def result(self, bars: int) -> BotRunResult:
        return BotRunResult(
            config_id=self.config.config_id,
            pnl_pct=self.pnl_pct,
            wins=self.wins,
            losses=self.losses,
            trades=self.trades,
            max_drawdown_pct=self.max_drawdown_pct,
            bars=bars,
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
