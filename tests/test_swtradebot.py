from __future__ import annotations

import asyncio
import logging

from nuubot.bots.executors.tradebot.tradebot import TradeConfig
from nuubot.core.dtypes import Bar
from nuubot.sweeps.executors import SwTradeBot
from nuubot.sweeps.signalers import SwSignal


def main() -> None:
    asyncio.run(tradebot_one_step_loop_shape())
    asyncio.run(tradebot_submits_trigger_exits())
    asyncio.run(tradebot_recons_at_most_once_per_minute())
    asyncio.run(tradebot_validates_risk_score())


async def tradebot_one_step_loop_shape() -> None:
    bot = SwTradeBot(TradeConfig(1, 0.0, 0.0, 0), logging.getLogger("test"))
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
    position = bot.account.ledger.position(bot.position_id)
    assert position is not None
    assert [order.role for order in position.orders] == ["entry", "take_profit", "stop_loss"]
    assert position.orders[1].trigger_price == position.orders[0].price * 103 / 100
    assert position.orders[2].trigger_price == position.orders[0].price * 99 / 100

    await bot.next(Bar(2, 103.0, 103.0, 103.0, 103.0, 1.0), SwSignal(), 1)
    assert bot.status == "stopped"
    assert bot.telemetry()["pnl_pct"] == 3.0


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


class CountingAccount:
    def __init__(self) -> None:
        self.ingests = 0
        self.recons = 0

    def init(self) -> None:
        pass

    def close(self) -> None:
        pass

    def ingest_bbo(self, bar: Bar) -> None:
        self.ingests += 1

    def recon(self, ts_ms: int, reason: str) -> None:
        _ = ts_ms, reason
        self.recons += 1


if __name__ == "__main__":
    main()
