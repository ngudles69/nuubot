from __future__ import annotations

from pathlib import Path
import tomllib

from nuubot.core.logger import logger
from nuubot.core.models.mconfig import BotrunConfig, SweeprunConfig, SweepConfig

log = logger("workspace/logs/runtime.log")


def load_botrun_config(path: Path) -> BotrunConfig:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return BotrunConfig.model_validate(data)
    except Exception as e:
        log.error(f"load_botrun_config error: {e}")
        raise


def load_sweeprun_config(path: Path) -> SweeprunConfig:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return SweeprunConfig.model_validate(data)
    except Exception as e:
        log.error(f"load_sweeprun_config error: {e}")
        raise


def load_sweep_config(path: Path) -> SweepConfig:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return SweepConfig.model_validate(data)
    except Exception as e:
        log.error(f"load_sweep_config error: {e}")
        raise
