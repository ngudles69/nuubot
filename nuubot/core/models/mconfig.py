from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nuubot.core.dtypes import Mode


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bot_id: int = 0
    mode: Mode
    max_loop: int = Field(ge=0)
    loop_seconds: float = Field(ge=0)
    min_timer_interval_ms: int = Field(default=1000, ge=1)


class MarketConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    interval: str


class BacktestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: str
    stop: str
    data_dir: str


class SignalerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    interval: str
    partial: bool = False
    params: dict[str, Any] = Field(default_factory=dict)


class TradebotExecutorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["tradebot"]
    take_profit_pct: float = Field(ge=0)
    stop_loss_pct: float = Field(ge=0)
    max_cycles: int = Field(ge=0)


NumberLike = str | int | float


class GhbotGridConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grid_enabled: bool
    grid_account: str
    grid_direction: str
    grid_investment_usdc: NumberLike
    grid_leverage: int
    grid_levels: int = Field(ge=3)
    grid_min_order_age_s: int
    grid_slippage_reserve_pct: NumberLike
    grid_spread_multiplier: NumberLike
    grid_winactive_order: int
    grid_win_interval_s: int
    grid_win_active_recalc_levels: int
    grid_level_reentry_cooldown_s: int
    grid_close_on_stop: bool


class GhbotHedgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hedge_enabled: bool
    hedge_account: str
    hedge_direction: str
    hedge_investment_usdc: NumberLike
    hedge_leverage: int
    hedge_reserve_pct: NumberLike
    hedge_entry_pct: NumberLike
    hedge_sl_pct: NumberLike
    hedge_take_profit_pct: NumberLike
    hedge_trailing_stop_pct: NumberLike
    hedge_cooldown_s: int
    hedge_grace_period_s: int
    hedge_max_retries: int
    hedge_sl_peg_mode: str


class GhbotRiskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_max_dd_pct: NumberLike
    risk_max_hedge_losses: int


class GhbotAuditConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_window_secs: int


class GhbotExecutorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["ghbot"]
    upper_bound_pct: NumberLike
    lower_bound_pct: NumberLike
    grid: GhbotGridConfig
    hedge: GhbotHedgeConfig
    risk: GhbotRiskConfig
    audit: GhbotAuditConfig
    max_cycles: int = Field(default=0, ge=0)


ExecutorConfig = TradebotExecutorConfig | GhbotExecutorConfig


class RiskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(default=1, ge=1, le=100)


class BotrunConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    runtime: RuntimeConfig
    market: MarketConfig
    signalers: list[SignalerConfig] = Field(min_length=1)
    executor: ExecutorConfig
    risk: RiskConfig = Field(default_factory=RiskConfig)
    backtest: BacktestConfig | None = None

    @model_validator(mode="after")
    def check_mode_sections(self) -> "BotrunConfig":
        if self.runtime.mode in {Mode.BACKTEST, Mode.SWEEP} and self.backtest is None:
            raise ValueError(f"{self.runtime.mode} mode requires [backtest]")
        return self
