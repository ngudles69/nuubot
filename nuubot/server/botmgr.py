from __future__ import annotations

from dataclasses import dataclass

from nuubot.nuubot import Nuubot


@dataclass
class BotManager:
    nuubot: Nuubot


def botmgr_setup(nuubot: Nuubot) -> BotManager:
    if nuubot.config is None or nuubot.datastore is None:
        raise RuntimeError("nuubot_setup() must complete before botmgr_setup()")
    return BotManager(nuubot)
