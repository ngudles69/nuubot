from __future__ import annotations

from pathlib import Path
import tomllib
from typing import Any

from nuubot.config.models import AppConfig


class Config:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.credentials_path = self.path.with_name("credentials.toml")

    def load(self) -> AppConfig:
        data = read_toml(self.path)
        data["credentials"] = read_toml(self.credentials_path)
        config = AppConfig.model_validate(data)
        config.set_mode()
        return config


def read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))
