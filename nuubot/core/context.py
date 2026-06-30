from __future__ import annotations

from dataclasses import dataclass

from nuubot.core.models.mconfig import BotrunConfig


@dataclass
class IdCtx:
    sweep_id: int
    sweeprun_id: int
    bot_id: int
    account_id: str
    bot_config: BotrunConfig
