from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from nuubot.core.dtypes import DataNetwork, ExecNetwork, HyperliquidNetwork, Mode


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str


class GeneralConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Mode


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=5001, ge=1, le=65535)
    reload: bool = False


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_dir: str
    data_dir: str
    db_dir: str
    logs_dir: str
    results_dir: str


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
    server: ServerConfig = Field(default_factory=ServerConfig)
    data_network: DataNetwork = DataNetwork.MAINNET
    exec_network: ExecNetwork = ExecNetwork.MAINNET
    paths: PathsConfig
    hyperliquid: HyperliquidConfig
    credentials: CredentialsConfig
