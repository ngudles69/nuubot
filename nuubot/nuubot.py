from dataclasses import dataclass
from pathlib import Path

from nuubot.config import load_config
from nuubot.config.models import AppConfig
from nuubot.datastore import Datastore

CONFIG_PATH = Path(__file__).resolve().parents[1] / "workspace" / "config" / "config.toml"


@dataclass
class Nuubot:
    config: AppConfig | None = None
    datastore: Datastore | None = None

    def setup(self) -> "Nuubot":
        self.config = load_config(CONFIG_PATH)
        self.datastore = Datastore(self.config).init()
        return self

    def stop(self) -> None:
        self.datastore.stop()
