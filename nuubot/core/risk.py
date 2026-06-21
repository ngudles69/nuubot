from __future__ import annotations

from nuubot.core.logger import logger
from nuubot.core.models.mconfig import RiskConfig

log = logger("workspace/logs/runtime.log")


class Risk:
    def __init__(self, config: RiskConfig) -> None:
        self.score_value = config.score

    async def init(self) -> None:
        pass

    async def start(self) -> None:
        pass

    async def score(self) -> int:
        return self.score_value

    async def exit(self) -> bool:
        return self.score_value >= 100

    async def stop(self) -> None:
        pass
