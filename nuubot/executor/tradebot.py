from __future__ import annotations

from dataclasses import dataclass

from nuubot.core.dtypes import Bar, BotRunResult, Signal


@dataclass
class TradeConfig:
    config_id: int
    take_profit_pct: float
    stop_loss_pct: float
    max_cycles: int


class ExecutorTrade:
    def __init__(self, config: TradeConfig) -> None:
        self.config = config
        self.active = False
        self.entry_price = 0.0
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
        pass

    async def loop_once(self, bar: Bar, signal: Signal) -> None:
        if self.active:
            self._update_drawdown(bar.close)
            change_pct = self._change_pct(bar.close)
            if signal.exit:
                self._close(change_pct)
            elif self.config.take_profit_pct > 0 and change_pct >= self.config.take_profit_pct:
                self._close(change_pct)
            elif self.config.stop_loss_pct > 0 and change_pct <= -self.config.stop_loss_pct:
                self._close(change_pct)

        if not self.active and signal.entry and self._can_enter():
            self._open(bar.close)

    async def stop(self, bar: Bar | None = None) -> None:
        if self.active and bar is not None:
            self._close(self._change_pct(bar.close))

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

    def _open(self, price: float) -> None:
        self.cycle_id += 1
        self.trades += 1
        self.entry_price = price
        self.active = True

    def _close(self, change_pct: float) -> None:
        self.pnl_pct += change_pct
        self.wins += int(change_pct >= 0)
        self.losses += int(change_pct < 0)
        self.cycle_count += 1
        self.active = False
        self.entry_price = 0.0

    def _can_enter(self) -> bool:
        return self.config.max_cycles == 0 or self.cycle_count < self.config.max_cycles

    def _change_pct(self, price: float) -> float:
        return (price - self.entry_price) / self.entry_price * 100

    def _update_drawdown(self, price: float) -> None:
        equity = self.pnl_pct + self._change_pct(price)
        self.peak_pct = max(self.peak_pct, equity)
        self.max_drawdown_pct = max(self.max_drawdown_pct, self.peak_pct - equity)
