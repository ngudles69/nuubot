from __future__ import annotations

import asyncio
import logging

from nuubot.account import TradingAccount
from nuubot.bots.executors.tradebot.tradebot import TradeConfig
from nuubot.core.dtypes import Bar
from nuubot.sweeps.executors import SwTradeBot
from nuubot.sweeps.signalers import SwSignal


def main() -> None:
    asyncio.run(tradebot_one_step_loop_shape())
    asyncio.run(tradebot_submits_trigger_exits())
    asyncio.run(tradebot_stop_recons_before_manual_close())
    asyncio.run(tradebot_manual_close_pnl_uses_actual_fills())
    asyncio.run(tradebot_recons_at_most_once_per_minute())
    asyncio.run(tradebot_validates_risk_score())


async def tradebot_one_step_loop_shape() -> None:
    bot = SwTradeBot(TradeConfig(1, 0.0, 0.0, 0, simulator_slippage_pct=0, simulator_commission_pct=0), logging.getLogger("test"))
    await bot.init()
    await bot.start()

    await bot.next(Bar(1, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(enter_long=True, reason="entry"), 1)
    assert bot.telemetry()["active"]
    assert bot.telemetry()["side"] == "long"

    await bot.next(Bar(2, 110.0, 110.0, 110.0, 110.0, 1.0), SwSignal(), 1)
    result = await bot.stop(Bar(3, 110.0, 110.0, 110.0, 110.0, 1.0), 2)

    assert result.trades == 1
    assert result.wins == 1
    assert result.pnl_pct == 10.0
    assert not bot.telemetry()["active"]


async def tradebot_submits_trigger_exits() -> None:
    bot = SwTradeBot(TradeConfig(1, 3.0, 1.0, 0, simulator_slippage_pct=0, simulator_commission_pct=0, simulator_recon_interval_ms=0), logging.getLogger("test"))
    await bot.init()
    await bot.start()

    await bot.next(Bar(1, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(enter_long=True, reason="entry", signal_ts_ms=1), 1)
    position = bot.account.position(bot.position_id)
    assert [order.role for order in position.orders] == ["entry", "take_profit", "stop_loss"]
    assert position.orders[1].trigger_price == position.orders[0].price * 103 / 100
    assert position.orders[2].trigger_price == position.orders[0].price * 99 / 100

    await bot.next(Bar(2, 103.0, 103.0, 103.0, 103.0, 1.0), SwSignal(), 1)
    assert bot.status == "stopped"
    assert bot.telemetry()["pnl_pct"] == 3.0


async def tradebot_stop_recons_before_manual_close() -> None:
    bot = SwTradeBot(TradeConfig(1, 3.0, 1.0, 0, simulator_slippage_pct=0, simulator_commission_pct=0, simulator_recon_interval_ms=60_000), logging.getLogger("test"))
    await bot.init()
    await bot.start()

    await bot.next(Bar(1, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(enter_long=True, reason="entry", signal_ts_ms=1), 1)
    position = bot.account.position(bot.position_id)

    await bot.next(Bar(20_001, 103.0, 103.0, 103.0, 103.0, 1.0), SwSignal(), 1)
    assert bot.telemetry()["active"]

    result = await bot.stop(Bar(30_001, 103.0, 103.0, 103.0, 103.0, 1.0), 2)

    assert result.pnl_pct == 3.0
    assert result.cycles == 1
    assert position.status == "closed"
    assert [order.role for order in position.orders] == ["entry", "take_profit", "stop_loss"]
    assert position.orders[1].status == "filled"
    assert position.orders[2].status == "canceled"


async def tradebot_manual_close_pnl_uses_actual_fills() -> None:
    bot = SwTradeBot(TradeConfig(1, 0.0, 0.0, 0, simulator_slippage_pct=10, simulator_commission_pct=0), logging.getLogger("test"))
    await bot.init()
    await bot.start()

    await bot.next(Bar(1, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(enter_long=True, reason="entry", signal_ts_ms=1), 1)
    result = await bot.stop(Bar(2, 100.0, 100.0, 100.0, 100.0, 1.0), 1)

    assert round(result.pnl_pct, 4) == round(-20 / 110 * 100, 4)
    assert result.losses == 1


async def tradebot_recons_at_most_once_per_minute() -> None:
    account = CountingAccount()
    bot = SwTradeBot(TradeConfig(1, 0.0, 0.0, 0), logging.getLogger("test"), account)
    await bot.init()
    await bot.start()

    await bot.next(Bar(60_000, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(), 1)
    await bot.next(Bar(80_000, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(), 1)
    await bot.next(Bar(100_000, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(), 1)
    await bot.next(Bar(119_999, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(), 1)
    await bot.next(Bar(120_000, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(), 1)

    assert account.ingests == 5
    assert account.recons == 1


async def tradebot_validates_risk_score() -> None:
    bot = SwTradeBot(TradeConfig(1, 0.0, 0.0, 0), logging.getLogger("test"))
    await bot.init()
    try:
        await bot.next(Bar(1, 100.0, 100.0, 100.0, 100.0, 1.0), SwSignal(), 0)
    except ValueError as exc:
        assert "risk_score" in str(exc)
    else:
        raise AssertionError("SwTradeBot accepted invalid risk_score")


class CountingAccount(TradingAccount):
    def __init__(self) -> None:
        super().__init__()
        self.ingests = 0
        self.recons = 0

    def ingest_bbo(self, bar: Bar) -> None:
        super().ingest_bbo(bar)
        self.ingests += 1

    def recon(self, ts_ms: int, reason: str) -> None:
        super().recon(ts_ms, reason)
        self.recons += 1


if __name__ == "__main__":
    main()
