from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nuubot.core.models.mconfig import BotrunConfig


class SweeprunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    botrun: BotrunConfig
    meta: dict[str, Any] = Field(default_factory=dict)
