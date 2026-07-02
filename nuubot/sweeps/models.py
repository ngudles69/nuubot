from __future__ import annotations

from typing import Any

from pydantic import Field

from nuubot.core.models.mconfig import BotrunConfig


class SweeprunConfig(BotrunConfig):
    meta: dict[str, Any] = Field(default_factory=dict)
