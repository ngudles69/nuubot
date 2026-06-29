from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from nuubot.core.dtypes import DataNetwork, ExecNetwork, HyperliquidNetwork, Mode


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str


class GeneralConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Mode


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_dir: str
    data_dir: str
    db_dir: str
    logs_dir: str
    results_dir: str


class DatabasesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    server: str
    mainnet: str
    testnet: str
    simnet: str
    backtest: str
    sweeps: str

    @field_validator("server", "mainnet", "testnet", "simnet", "backtest", "sweeps")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError("database names must not have surrounding whitespace")
        if not value or not ("a" <= value[0] <= "z"):
            raise ValueError("database names must start with a lowercase letter")
        if any(not (("a" <= char <= "z") or ("0" <= char <= "9") or char == "_") for char in value):
            raise ValueError("database names must use lowercase letters, digits, and underscores")
        return value


class HyperliquidConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_network: HyperliquidNetwork


class HyperliquidAccountCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network: HyperliquidNetwork
    name: str
    address: str
    api_key: SecretStr


class HyperliquidCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accounts: list[HyperliquidAccountCredentials] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_account_names(self) -> "HyperliquidCredentials":
        names = [account.name for account in self.accounts]
        if len(names) != len(set(names)):
            raise ValueError("hyperliquid account names must be unique")
        return self


class CredentialsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hyperliquid: HyperliquidCredentials


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace: WorkspaceConfig
    general: GeneralConfig
    data_network: DataNetwork = DataNetwork.MAINNET
    exec_network: ExecNetwork = ExecNetwork.MAINNET
    paths: PathsConfig
    databases: DatabasesConfig
    hyperliquid: HyperliquidConfig
    credentials: CredentialsConfig
