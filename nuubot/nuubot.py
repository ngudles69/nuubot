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

    def setup(self, path: Path = CONFIG_PATH) -> "Nuubot":
        self.config = load_config(path)
        self.datastore = Datastore(self.config).init()
        return self

    def stop(self) -> None:
        if self.datastore is not None:
            self.datastore.stop()


def nuubot_setup(path: Path = CONFIG_PATH) -> Nuubot:
    nuubot = Nuubot()
    return nuubot.setup(path)
