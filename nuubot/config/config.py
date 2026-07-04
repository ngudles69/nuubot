from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any

from nuubot.config.models import AppConfig
from nuubot.core.dtypes import DataNetwork, ExecNetwork, Mode


def load_config(path: Path) -> AppConfig:
    filedata = read_config_data(path)
    config = create_config(filedata)
    return config


def read_config_data(path: Path) -> dict[str, Any]:
    config_path = path.with_name("config.toml")
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    credentials_path = config_path.with_name("credentials.toml")
    if not credentials_path.exists():
        credentials_path = Path(data["workspace"]["root"]) / data["paths"]["config_dir"] / "credentials.toml"
    data["credentials"] = tomllib.loads(credentials_path.read_text(encoding="utf-8"))
    return data


def create_config(data: dict[str, Any]) -> AppConfig:
    config = AppConfig.model_validate(data)
    set_networks(config)
    return config


def set_networks(config: AppConfig) -> None:
    """Set data and execution networks from runtime mode."""

    data_network = None
    exec_network = None

    if config.general.mode == Mode.MAINNET:
        data_network = DataNetwork.MAINNET
        exec_network = ExecNetwork.MAINNET
    elif config.general.mode == Mode.TESTNET:
        data_network = DataNetwork.TESTNET
        exec_network = ExecNetwork.TESTNET
    elif config.general.mode == Mode.SIMNET:
        data_network = DataNetwork.MAINNET
        exec_network = ExecNetwork.SIMNET
    elif config.general.mode == Mode.BACKTEST:
        data_network = DataNetwork.FILENET
        exec_network = ExecNetwork.SIMNET
    elif config.general.mode == Mode.SWEEP:
        data_network = DataNetwork.FILENET
        exec_network = ExecNetwork.SWEEP

    if data_network is None or exec_network is None:
        raise ValueError(f"unsupported mode: {config.general.mode}")

    config.data_network = data_network
    config.exec_network = exec_network
