from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nuubot.config import Config
from nuubot.config.models import AppConfig
from nuubot.datastore import Datastore


@dataclass
class Nuubot:
    config: AppConfig
    datastore: Datastore

    @classmethod
    def setup(cls, path: Path | str = "workspace/config/config.toml") -> Nuubot:
        config = Config(path).load()
        datastore = Datastore(config).init()
        return cls(config=config, datastore=datastore)

    def stop(self) -> None:
        self.datastore.stop()


def nuubot_setup(path: Path | str = "workspace/config/config.toml") -> Nuubot:
    return Nuubot.setup(path)
