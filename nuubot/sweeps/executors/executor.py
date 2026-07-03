from __future__ import annotations

from typing import Any, Protocol

from nuubot.bots.executors.tradebot.tradebot import TradeConfig
from nuubot.core.dtypes import Bar, BotRunResult
from nuubot.sweeps.executors.swtradebot import SwTradeBot
from nuubot.sweeps.signalers import SwSignal


class SwExecutor(Protocol):
    status: str

    async def init(self) -> None: ...
    async def start(self) -> None: ...
    async def next(self, bar: Bar, signal: SwSignal, risk_score: int) -> None: ...
    async def stop(self, bar: Bar | None, bars: int) -> BotRunResult: ...
    def telemetry(self) -> dict[str, Any]: ...


def create_executor(config_id: int, config: Any, run_log: Any, sweeprun: Any | None = None) -> SwExecutor:
    if config.name == "tradebot":
        trade_config = TradeConfig(
            config_id,
            config.take_profit_pct,
            config.stop_loss_pct,
            config.max_cycles,
            config.symbol,
            config.account,
            getattr(sweeprun, "simulator_slippage_pct", 0.05),
            getattr(sweeprun, "simulator_commission_pct", 0.05),
            getattr(sweeprun, "simulator_recon_interval_ms", 60_000),
        )
        return SwTradeBot(trade_config, run_log)
    raise ValueError(f"unsupported sweep executor: {config.name}")
