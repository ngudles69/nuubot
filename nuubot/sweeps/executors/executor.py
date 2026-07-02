from __future__ import annotations

from typing import Any

from nuubot.bots.executors.tradebot.tradebot import TradeConfig
from nuubot.sweeps.executors.swtradebot import SwTradeBot


def build_executor(config_id: int, config: Any, run_log: Any) -> Any:
    if config.name == "tradebot":
        trade_config = TradeConfig(
            config_id,
            config.take_profit_pct,
            config.stop_loss_pct,
            config.max_cycles,
            config.symbol,
            "default",
        )
        return SwTradeBot(trade_config, run_log)
    raise ValueError(f"unsupported sweep executor: {config.name}")
