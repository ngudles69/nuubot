from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from nuubot.core.dtypes import MODE_NETWORKS, DataNetwork, ExecNetwork, Mode


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str


class GeneralConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Mode
    data_network: DataNetwork | None = None
    exec_network: ExecNetwork | None = None


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


class HyperliquidConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_network: Literal["mainnet", "testnet", "simnet"]


class DatabaseCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str
    port: int = Field(ge=1, le=65535)
    user: str
    password: SecretStr


class HyperliquidAccountCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network: Literal["mainnet", "testnet", "simnet"]
    name: str
    address: str
    api_key: SecretStr


class HyperliquidCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accounts: list[HyperliquidAccountCredentials] = Field(min_length=1)


class CredentialsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database: DatabaseCredentials
    hyperliquid: HyperliquidCredentials


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace: WorkspaceConfig
    general: GeneralConfig
    paths: PathsConfig
    databases: DatabasesConfig
    hyperliquid: HyperliquidConfig
    credentials: CredentialsConfig

    def set_mode(self) -> None:
        self.general.data_network, self.general.exec_network = MODE_NETWORKS[self.general.mode]
