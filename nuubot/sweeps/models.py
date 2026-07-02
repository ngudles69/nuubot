from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from nuubot.core.models.mconfig import ExecutorConfig, MarketConfig, RiskConfig, SignalerConfig


class SweeprunSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str
    data_dir: str
    max_loop: int = Field(default=0, ge=0)
    meta: dict[str, Any] = Field(default_factory=dict)


class SweeprunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: MarketConfig
    signaler: SignalerConfig
    executor: ExecutorConfig
    risk: RiskConfig = Field(default_factory=RiskConfig)
    sweeprun: SweeprunSettings
