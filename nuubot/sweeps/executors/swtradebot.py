from __future__ import annotations

from bisect import bisect_right
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

from nuubot.account import Order, TradingAccount
from nuubot.bots.executors.tradebot.tradebot import TradeConfig
from nuubot.core.dtypes import Bar, BotRunResult
from nuubot.core.format import format_ms
from nuubot.exchange import Simulator
from nuubot.sweeps.signalers import SwSignal


class SwTradeBot:
    def __init__(self, config: TradeConfig, run_log: Any, account: TradingAccount | None = None) -> None:
        self.config = config
        self.log = run_log
        self.account = account
        self.status = "configured"
        self.active = False
        self.side = ""
        self.entry_price = 0.0
        self.position_id: int | None = None
        self.entry_order_cloid = ""
        self.pnl_pct = 0.0
        self.peak_pct = 0.0
        self.max_drawdown_pct = 0.0
        self.wins = 0
        self.losses = 0
        self.trades = 0
        self.cycle_id = 0
        self.cycle_count = 0
        self.last_risk_score = 1
        self.last_recon_ts_ms: int | None = None

    async def init(self) -> None:
        # Validate config.
        if self.config.config_id <= 0:
            raise ValueError(f"config_id must be positive: {self.config.config_id}")
        if self.config.take_profit_pct < 0:
            raise ValueError(f"take_profit_pct must be >= 0: {self.config.take_profit_pct}")
        if self.config.stop_loss_pct < 0:
            raise ValueError(f"stop_loss_pct must be >= 0: {self.config.stop_loss_pct}")
        if self.config.max_cycles < 0:
            raise ValueError(f"max_cycles must be >= 0: {self.config.max_cycles}")
        if self.config.simulator_recon_interval_ms < 0:
            raise ValueError(f"simulator_recon_interval_ms must be >= 0: {self.config.simulator_recon_interval_ms}")

        # Init account.
        if self.account is None:
            self.account = TradingAccount(
                simulator=Simulator(
                    self.config.simulator_slippage_pct,
                    self.config.simulator_commission_pct,
                )
            )
        self.account.init()

    async def start(self) -> None:
        # Start bot.
        self.status = "running"

    async def next(self, bar: Bar, signal: SwSignal, risk_score: int) -> None:
        """Process one trade event."""

        if risk_score < 1 or risk_score > 100:
            raise ValueError(f"risk_score must be 1..100: {risk_score}")
        self.last_risk_score = risk_score

        # Reconcile account.
        self.account.ingest_bbo(bar)
        if self.last_recon_ts_ms is None:
            self.last_recon_ts_ms = bar.ts_ms
        elif self.config.simulator_recon_interval_ms == 0 or bar.ts_ms - self.last_recon_ts_ms >= self.config.simulator_recon_interval_ms:
            self.account.recon(bar.ts_ms, "sweeprun_tick")
            self.last_recon_ts_ms = bar.ts_ms
            self._sync_position()

        # Exit active trade without trigger orders.
        if self.active:
            self._update_drawdown(bar.close)
            if not self._uses_trigger_exits():
                signal_price = bar.open
                if self.side == "long" and signal.exit_long:
                    await self._close(signal_price, signal.reason, bar.ts_ms)
                elif self.side == "short" and signal.exit_short:
                    await self._close(signal_price, signal.reason, bar.ts_ms)

        # Enter new trade.
        if not self.active and self.status == "running" and self._can_enter():
            if signal.enter_long:
                await self._open(bar, "long", bar.open, signal.reason)
            elif signal.enter_short:
                await self._open(bar, "short", bar.open, signal.reason)

    async def stop(self, bar: Bar | None, ticks: int) -> BotRunResult:
        if self.active and bar is not None:
            await self._close(bar.close, "stop", bar.ts_ms)
        self.account.close()
        self.status = "stopped"
        return self._result(ticks)

    def telemetry(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "active": self.active,
            "side": self.side,
            "entry_price": self.entry_price,
            "position_id": self.position_id,
            "pnl_pct": self.pnl_pct,
            "peak_pct": self.peak_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "wins": self.wins,
            "losses": self.losses,
            "trades": self.trades,
            "cycle_id": self.cycle_id,
            "cycle_count": self.cycle_count,
            "last_risk_score": self.last_risk_score,
        }

    @staticmethod
    def chart_display(positions: list[Any], orders: list[Any], timestamps: list[int]) -> dict[str, Any]:
        return {
            "markers": position_markers(positions, timestamps),
            "primitives": position_primitives(positions, orders, timestamps),
        }

    def _result(self, ticks: int) -> BotRunResult:
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

    async def _open(self, bar: Bar, side: str, price: float, reason: str) -> None:
        self.cycle_id += 1
        self.trades += 1
        self.side = side
        self.entry_price = price
        self.active = True
        position = self.account.create_position(self.config.symbol or "UNKNOWN")
        entry_cloid = f"tradebot-{self.config.config_id}-{self.cycle_id}-entry-{bar.ts_ms}"
        order = Order(
            symbol=self.config.symbol or "UNKNOWN",
            side="buy" if side == "long" else "sell",
            size=Decimal("1"),
            price=Decimal(str(price)),
            cloid=entry_cloid,
            role="entry",
        )
        position.add_order(order)
        self.entry_order_cloid = entry_cloid
        for exit_order in self._trigger_exit_orders(side, Decimal(str(price)), entry_cloid, bar.ts_ms):
            position.add_order(exit_order)
        self.account.place_position(position, bar.ts_ms)
        self.account.recon(bar.ts_ms, "post_submit")
        self.last_recon_ts_ms = bar.ts_ms
        self.position_id = position.position_id
        self.entry_price = self._entry_fill_price(position)
        self.log.info(f"trade_open cycle={self.cycle_id} side={side} reason={reason} price={price} ts_now: {format_ms(bar.ts_ms)}")

    async def _close(self, price: float, reason: str, now_ms: int) -> None:
        """Close the active in-memory trade state."""

        if self.position_id is None:
            raise RuntimeError("active trade missing position_id")

        # Pull exchange truth before submitting a manual close.
        self.account.recon(now_ms, "pre_close")
        self.last_recon_ts_ms = now_ms
        self._sync_position()
        if not self.active or self.position_id is None:
            return

        position = self.account.position(self.position_id)
        self.account.close_positions([position], Decimal(str(price)), now_ms, reason)
        self.account.recon(now_ms, reason)
        self.last_recon_ts_ms = now_ms
        position.recalc()
        exit_orders = [order for order in position.orders if order.reduce_only and order.filled_size > 0]
        exit_order = exit_orders[-1] if exit_orders else None
        if exit_order is None:
            raise RuntimeError(f"manual close did not produce an exit fill: position_id={position.position_id}")
        change_pct = self._position_change_pct(position)
        self.pnl_pct += change_pct
        self.wins += int(change_pct >= 0)
        self.losses += int(change_pct < 0)
        self.cycle_count += 1
        self.active = False
        self.side = ""
        self.entry_price = 0.0
        self.position_id = None
        self.entry_order_cloid = ""
        self.log.info(f"trade_close cycle={self.cycle_id} reason={reason} pnl_pct={change_pct:.4f} total_pnl_pct={self.pnl_pct:.4f} ts_now: {format_ms(now_ms)}")
        self.status = "stopped"

    def _can_enter(self) -> bool:
        return self.config.max_cycles == 0 or self.cycle_count < self.config.max_cycles

    def _change_pct(self, price: float) -> float:
        change = (price - self.entry_price) / self.entry_price * 100
        return change if self.side != "short" else -change

    def _update_drawdown(self, price: float) -> None:
        equity = self.pnl_pct + self._change_pct(price)
        self.peak_pct = max(self.peak_pct, equity)
        self.max_drawdown_pct = max(self.max_drawdown_pct, self.peak_pct - equity)

    def _uses_trigger_exits(self) -> bool:
        return self.config.take_profit_pct > 0 or self.config.stop_loss_pct > 0

    def _trigger_exit_orders(self, side: str, entry_price: Decimal, parent_cloid: str, ts_ms: int) -> list[Order]:
        if not self._uses_trigger_exits():
            return []
        symbol = self.config.symbol or "UNKNOWN"
        exit_side = "sell" if side == "long" else "buy"
        rows = []
        if self.config.take_profit_pct > 0:
            rows.append(
                Order(
                    symbol=symbol,
                    side=exit_side,
                    size=Decimal("1"),
                    price=self._trigger_price(side, entry_price, self.config.take_profit_pct, "tp"),
                    cloid=f"tradebot-{self.config.config_id}-{self.cycle_id}-take_profit-{ts_ms}",
                    role="take_profit",
                    reduce_only=True,
                    kind="trigger",
                    trigger_price=self._trigger_price(side, entry_price, self.config.take_profit_pct, "tp"),
                    tpsl="tp",
                    parent_cloid=parent_cloid,
                )
            )
        if self.config.stop_loss_pct > 0:
            rows.append(
                Order(
                    symbol=symbol,
                    side=exit_side,
                    size=Decimal("1"),
                    price=self._trigger_price(side, entry_price, self.config.stop_loss_pct, "sl"),
                    cloid=f"tradebot-{self.config.config_id}-{self.cycle_id}-stop_loss-{ts_ms}",
                    role="stop_loss",
                    reduce_only=True,
                    kind="trigger",
                    trigger_price=self._trigger_price(side, entry_price, self.config.stop_loss_pct, "sl"),
                    tpsl="sl",
                    parent_cloid=parent_cloid,
                )
            )
        return rows

    def _trigger_price(self, side: str, entry_price: Decimal, pct: float, tpsl: str) -> Decimal:
        offset = entry_price * Decimal(str(pct)) / Decimal("100")
        if (side == "long" and tpsl == "tp") or (side == "short" and tpsl == "sl"):
            return entry_price + offset
        return entry_price - offset

    def _sync_position(self) -> None:
        if not self.active or self.position_id is None:
            return
        position = self.account.position(self.position_id)
        position.recalc()
        if position.status != "closed":
            return
        exit_orders = [order for order in position.orders if order.reduce_only and order.filled_size > 0]
        exit_order = exit_orders[-1] if exit_orders else None
        if exit_order is None:
            return
        change_pct = self._position_change_pct(position)
        self.pnl_pct += change_pct
        self.wins += int(change_pct >= 0)
        self.losses += int(change_pct < 0)
        self.cycle_count += 1
        self.active = False
        self.side = ""
        self.entry_price = 0.0
        self.position_id = None
        self.entry_order_cloid = ""
        self.status = "stopped"
        self.log.info(f"trade_close cycle={self.cycle_id} reason={exit_order.role} pnl_pct={change_pct:.4f} total_pnl_pct={self.pnl_pct:.4f} ts_now: {format_ms(exit_order.fills[-1].ts_ms)}")

    def _entry_fill_price(self, position: Any) -> float:
        entries = [order for order in position.orders if not order.reduce_only and order.filled_size > 0]
        entry = entries[0] if entries else None
        if entry is None:
            raise RuntimeError(f"position missing entry fill: position_id={position.position_id}")
        return float(entry.avg_fill_price)

    def _position_change_pct(self, position: Any) -> float:
        position.recalc()
        entry_cash = sum((abs(order.signed_cash()) for order in position.orders if not order.reduce_only), Decimal("0"))
        if entry_cash == 0:
            raise RuntimeError(f"position missing entry notional: position_id={position.position_id}")
        return float(position.pnl() / entry_cash * Decimal("100"))


def position_markers(positions: list[Any], timestamps: list[int]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for position in positions:
        if position.opened_ts is not None and position.avg_entry_px is not None:
            markers.append(position_marker("entry", position.opened_ts, position.avg_entry_px, position, timestamps))
        if position.closed_ts is not None and position.avg_exit_px is not None:
            markers.append(position_marker("exit", position.closed_ts, position.avg_exit_px, position, timestamps))
    return markers


def position_primitives(positions: list[Any], orders: list[Any], timestamps: list[int]) -> list[dict[str, Any]]:
    tpsl_by_position = _tpsl_by_position(orders)
    primitives: list[dict[str, Any]] = []
    for position in positions:
        if position.opened_ts is None or position.closed_ts is None:
            continue
        if position.avg_entry_px is None or position.avg_exit_px is None:
            continue
        primitives.extend(position_window_primitives(position, timestamps, tpsl_by_position.get(position.position_id, {})))
    return primitives


def position_marker(kind: str, ts_ms: int, price: str, position: Any, timestamps: list[int]) -> dict[str, Any]:
    index = bisect_right(timestamps, ts_ms) - 1
    index = max(0, min(len(timestamps) - 1, index))
    color = "#22c55e" if kind == "entry" else "#ef4444"
    return {
        "name": f"{kind} {position.side} {position.exit_reason or ''}".strip(),
        "value": [index, float(price)],
        "kind": kind,
        "side": position.side,
        "pnl": position.net_pnl,
        "time": chart_time(ts_ms),
        "itemStyle": {"color": "rgba(0,0,0,0)", "borderColor": color, "borderWidth": 2.6},
    }


def _tpsl_by_position(orders: list[Any]) -> dict[int, dict[str, float]]:
    output: dict[int, dict[str, float]] = {}
    for order in orders:
        if order.submit_tpsl not in {"tp", "sl"}:
            continue
        price = order.submit_trigger_price or order.submit_price
        try:
            output.setdefault(order.position_id, {})[order.submit_tpsl] = float(price)
        except (TypeError, ValueError):
            continue
    return output


def position_window_primitives(position: Any, timestamps: list[int], tpsl: dict[str, float]) -> list[dict[str, Any]]:
    start = bisect_right(timestamps, int(position.opened_ts)) - 1
    end = bisect_right(timestamps, int(position.closed_ts)) - 1
    start = max(0, min(len(timestamps) - 1, start))
    end = max(0, min(len(timestamps) - 1, end))
    left = min(start, end)
    right = max(start, end)
    entry = float(position.avg_entry_px)
    exit = float(position.avg_exit_px)
    bounds = [tpsl["tp"], tpsl["sl"]] if "tp" in tpsl and "sl" in tpsl else [entry, exit]
    low = min(bounds)
    high = max(bounds)
    if high == low:
        pad = max(1, abs(entry) * 0.001)
        low -= pad
        high += pad
    side_color = "rgba(249,115,22,0.9)" if position.side == "short" else "rgba(20,184,166,0.9)"
    tp_color = "rgba(34,197,94,0.95)"
    sl_color = "rgba(239,68,68,0.95)"
    has_tpsl = "tp" in tpsl and "sl" in tpsl
    top_color = tp_color if has_tpsl and tpsl["tp"] > tpsl["sl"] else sl_color if has_tpsl else side_color
    bottom_color = tp_color if has_tpsl and tpsl["tp"] < tpsl["sl"] else sl_color if has_tpsl else side_color
    return [
        {
            "type": "dashbox",
            "value": [left, right, high, low],
            "color": side_color,
            "top_color": top_color,
            "bottom_color": bottom_color,
            "side": position.side,
            "tp": tpsl.get("tp"),
            "sl": tpsl.get("sl"),
            "exit_reason": position.exit_reason or "",
        },
        {"type": "hline", "value": [left, right, entry], "color": "rgba(148,163,184,0.82)", "label": "entry"},
        {"type": "hline", "value": [left, right, exit], "color": "rgba(99,102,241,0.82)", "label": "exit"},
    ]


def chart_time(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
