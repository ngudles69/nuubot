from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

from nuubot.core.models.mconfig import RiskConfig, SignalerConfig


class SweeprunSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    end: str
    data_dir: str
    savedb: bool = True
    simulator_slippage_pct: float = Field(default=0.05, ge=0)
    simulator_commission_pct: float = Field(default=0.05, ge=0)
    simulator_recon_interval_ms: int = Field(default=60_000, ge=0)
    investment_usdc: float = Field(default=10000.0, gt=0)
    trade_use: str = "pct"
    trade_amount: float = Field(default=100.0, gt=0)
    trade_pct: float = Field(default=2.0, gt=0)
    max_loop: int = Field(default=0, ge=0)
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_trade_sizing(self) -> "SweeprunSettings":
        if self.trade_use not in {"pct", "amount"}:
            raise ValueError(f"trade_use must be pct or amount: {self.trade_use}")
        trade_usdc = self.trade_amount if self.trade_use == "amount" else self.investment_usdc * self.trade_pct / 100
        if trade_usdc < 10:
            raise ValueError(f"trade size must be at least 10 USDC: {trade_usdc}")
        return self


class SweeprunExecutorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    account: str = "sgrid"
    interval: str
    name: str
    take_profit_pct: float = Field(ge=0)
    stop_loss_pct: float = Field(ge=0)
    max_cycles: int = Field(ge=0)


class SweeprunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signaler: SignalerConfig
    executor: SweeprunExecutorConfig
    risk: RiskConfig = Field(default_factory=RiskConfig)
    sweeprun: SweeprunSettings
