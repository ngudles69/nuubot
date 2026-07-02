"""Internal datastore objects."""

from __future__ import annotations

from nuubot.core.context import IdCtx
from nuubot.datastore.schemas import FillRow, OrderRow, PositionRow


class Position:
    def __init__(self, ctx: IdCtx, *, side: str, price: float, ts_ms: int) -> None:
        self.ctx = ctx
        self.id = ctx.bot_id
        self.side = side
        self.price = price
        self.ts_ms = ts_ms
        self.init()

    def init(self) -> None:
        self.sweep_id = self.ctx.sweep_id
        self.sweeprun_id = self.ctx.sweeprun_id
        self.bot_id = self.ctx.bot_id
        self.botrun_id = self.ctx.bot_id
        self.acct_id = self.ctx.account_id
        self.symbol = self.ctx.bot_config.market.symbol

    def row(self) -> PositionRow:
        """Build the datastore row for this position."""

        size = "1" if self.side == "long" else "-1"
        return PositionRow(
            position_id=self.id,
            sweep_id=self.sweep_id,
            sweeprun_id=self.sweeprun_id,
            bot_id=self.bot_id,
            botrun_id=self.botrun_id,
            acct_id=self.acct_id,
            symbol=self.symbol,
            status="open",
            side=self.side,
            current_sz=size,
            max_abs_sz="1",
            avg_entry_px=str(self.price),
            mark_px=str(self.price),
            entry_cash=str(self.price),
            open_entry_cash=str(self.price),
            exit_cash="0",
            entry_fee="0",
            exit_fee="0",
            total_fee="0",
            gross_pnl="0",
            realized_pnl="0",
            unrealized_pnl="0",
            net_pnl="0",
            opened_ts=self.ts_ms,
            last_update_ts=self.ts_ms,
        )


class Order:
    def __init__(self, ctx: IdCtx, *, position_id: int, side: str, price: float, ts_ms: int, reduceonly: bool) -> None:
        self.ctx = ctx
        self.position_id = position_id
        self.side = side
        self.price = price
        self.ts_ms = ts_ms
        self.reduceonly = reduceonly
        self.init()

    def init(self) -> None:
        self.sweep_id = self.ctx.sweep_id
        self.sweeprun_id = self.ctx.sweeprun_id
        self.bot_id = self.ctx.bot_id
        self.botrun_id = self.ctx.bot_id
        self.acct_id = self.ctx.account_id
        self.symbol = self.ctx.bot_config.market.symbol
        self.id = self.position_id * 10 + (2 if self.reduceonly else 1)
        self.cloid = f"sweep-{self.sweeprun_id}-{self.bot_id}-{self.position_id}-{self.side}-{self.ts_ms}"

    def row(self) -> OrderRow:
        """Build the datastore row for this order."""

        return OrderRow(
            order_id=self.id,
            sweep_id=self.sweep_id,
            sweeprun_id=self.sweeprun_id,
            cloid=self.cloid,
            bot_id=self.bot_id,
            botrun_id=self.botrun_id,
            position_id=self.position_id,
            acct_id=self.acct_id,
            submit_cloid=self.cloid,
            submit_ts=self.ts_ms,
            submit_coin=self.symbol,
            submit_side=self.side,
            submit_quantity="1",
            submit_price=str(self.price),
            submit_reduceonly=self.reduceonly,
            submit_type="market",
            status="filled",
            filled_quantity="1",
            avg_fill_price=str(self.price),
            fill_count=1,
            first_fill_ts=self.ts_ms,
            last_fill_ts=self.ts_ms,
            fee="0",
        )


class Fill:
    def __init__(
        self,
        ctx: IdCtx,
        *,
        order_id: int,
        side: str,
        price: float,
        ts_ms: int,
        closed_pnl: float | None,
    ) -> None:
        self.ctx = ctx
        self.id = order_id
        self.order_id = order_id
        self.side = side
        self.price = price
        self.ts_ms = ts_ms
        self.closed_pnl = closed_pnl
        self.init()

    def init(self) -> None:
        self.sweep_id = self.ctx.sweep_id
        self.sweeprun_id = self.ctx.sweeprun_id
        self.bot_id = self.ctx.bot_id
        self.botrun_id = self.ctx.bot_id
        self.acct_id = self.ctx.account_id
        self.symbol = self.ctx.bot_config.market.symbol

    def row(self) -> FillRow:
        """Build the datastore row for this fill."""

        return FillRow(
            fill_id=self.id,
            sweep_id=self.sweep_id,
            sweeprun_id=self.sweeprun_id,
            bot_id=self.bot_id,
            botrun_id=self.botrun_id,
            order_id=self.order_id,
            acct_id=self.acct_id,
            coin=self.symbol,
            side=self.side,
            px=str(self.price),
            sz="1",
            time=self.ts_ms,
            fee="0",
            closedPnl=None if self.closed_pnl is None else str(self.closed_pnl),
        )
