from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from nuubot.core.models.mconfig import BotrunConfig


class SweeprunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    botrun: BotrunConfig
    start: str = ""
    stop: str = ""


class SweepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sweep: dict[str, Any]
    params: dict[str, Any]
    botrun: BotrunConfig

    @model_validator(mode="before")
    @classmethod
    def read_botrun_sections(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "botrun" in value:
            return value
        botrun_keys = ("runtime", "market", "signalers", "executor", "risk", "backtest")
        botrun = {key: value[key] for key in botrun_keys if key in value}
        return {
            "sweep": value.get("sweep", {}),
            "params": value.get("params", {}),
            "botrun": botrun,
        }
