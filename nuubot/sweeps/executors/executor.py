from __future__ import annotations

from typing import Any, Protocol

from nuubot.bots.executors.tradebot.tradebot import TradeConfig
from nuubot.core.dtypes import Bar, BotRunResult
from nuubot.sweeps.executors.swtradebot import SwTradeBot
from nuubot.sweeps.models import SweeprunSettings
from nuubot.sweeps.signalers import SwSignal


class SwExecutor(Protocol):
    status: str

    async def init(self) -> None: ...
    async def start(self) -> None: ...
    async def next(self, bar: Bar, signal: SwSignal, risk_score: int) -> None: ...
    async def stop(self, bar: Bar | None, ticks: int) -> BotRunResult: ...
    def telemetry(self) -> dict[str, Any]: ...


def create_executor(config_id: int, config: Any, run_log: Any, sweeprun: SweeprunSettings) -> SwExecutor:
    if config.name == "tradebot":
        trade_config = TradeConfig(
            config_id,
            config.take_profit_pct,
            config.stop_loss_pct,
            config.max_cycles,
            config.symbol,
            config.account,
            sweeprun.simulator_slippage_pct,
            sweeprun.simulator_commission_pct,
            sweeprun.simulator_recon_interval_ms,
        )
        return SwTradeBot(trade_config, run_log)
    raise ValueError(f"unsupported sweep executor: {config.name}")
