from __future__ import annotations

from typing import Any

from nuubot.core.models.mconfig import BotrunConfig
from nuubot.core.market_data import required


def expand_values(value: Any) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    if isinstance(value, dict):
        current = float(required(value, "start", "params"))
        stop = float(required(value, "stop", "params"))
        step = float(required(value, "step", "params"))
        output = []
        while current <= stop + 1e-12:
            output.append(round(current, 10))
            current += step
        return output
    raise TypeError(f"bad parameter shape: {value}")


def sweep_bot_data(config: BotrunConfig, bot_id: int, ema_fast: int, ema_slow: int) -> dict[str, Any]:
    bot_data = config.model_dump()
    bot_data["runtime"]["bot_id"] = bot_id
    bot_data["runtime"]["mode"] = "sweep"
    bot_data["signalers"][0]["params"]["fast"] = ema_fast
    bot_data["signalers"][0]["params"]["slow"] = ema_slow
    return bot_data
