from __future__ import annotations

from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from nuubot.core.models.mconfig import RiskConfig, SignalerConfig


class SweeprunSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str
    data_dir: str
    max_loop: int = Field(default=0, ge=0)
    meta: dict[str, Any] = Field(default_factory=dict)


class SweeprunExecutorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    interval: str
    name: Literal["tradebot"]
    take_profit_pct: float = Field(ge=0)
    stop_loss_pct: float = Field(ge=0)
    max_cycles: int = Field(ge=0)


class SweeprunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signaler: SignalerConfig
    executor: SweeprunExecutorConfig
    risk: RiskConfig = Field(default_factory=RiskConfig)
    sweeprun: SweeprunSettings
