from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bot_id: int = 0
    exec_network: Literal["mainnet", "testnet", "simnet", "backtest"]
    data_network: Literal["mainnet", "testnet", "file"]
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


class ExecutorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Literal["tradebot"]
    take_profit_pct: float = Field(ge=0)
    stop_loss_pct: float = Field(ge=0)
    max_cycles: int = Field(ge=0)


class RiskConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(default=1, ge=1, le=100)


class BotrunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: RuntimeConfig
    market: MarketConfig
    signalers: list[SignalerConfig] = Field(min_length=1)
    executor: ExecutorConfig
    risk: RiskConfig = Field(default_factory=RiskConfig)
    backtest: BacktestConfig | None = None

    @model_validator(mode="after")
    def check_mode_sections(self) -> "BotrunConfig":
        if self.runtime.exec_network == "backtest" and self.runtime.data_network != "file":
            raise ValueError("backtest exec_network requires data_network = file")
        if self.runtime.data_network == "file" and self.backtest is None:
            raise ValueError("file data_network requires [backtest]")
        return self


class SweeprunConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    botrun: BotrunConfig
    start: str = ""
    stop: str = ""


class SweepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sweep: dict[str, Any]
    params: dict[str, Any]
    botrun: BotrunConfig

    @model_validator(mode="before")
    @classmethod
    def read_botrun_sections(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "botrun" in value:
            return value
        botrun_keys = ("runtime", "market", "signalers", "executor", "risk", "backtest")
        botrun = {key: value[key] for key in botrun_keys if key in value}
        return {
            "sweep": value.get("sweep", {}),
            "params": value.get("params", {}),
            "botrun": botrun,
        }
