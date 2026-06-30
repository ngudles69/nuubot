from dataclasses import dataclass
from pathlib import Path

from nuubot.config import load_config
from nuubot.config.models import AppConfig
from nuubot.core.exchange_meta import ensure_exchange_meta
from nuubot.datastore import Datastore

CONFIG_PATH = Path(__file__).resolve().parents[1] / "workspace" / "config" / "config.toml"
SERVER_DB = "server.db"


@dataclass
class Nuubot:
    config: AppConfig | None = None
    datastore: Datastore | None = None
    server_db: str = SERVER_DB

    def setup(self, path: Path = CONFIG_PATH) -> "Nuubot":
        self.config = load_config(path)
        dbroot = Path(self.config.workspace.root) / self.config.paths.db_dir
        self.datastore = Datastore(dbroot)
        self.datastore.dbinit(self.server_db)
        ensure_exchange_meta(
            self.datastore,
            self.server_db,
            data_network=self.config.data_network,
            default_network=self.config.hyperliquid.default_network,
        )
        return self

    def stop(self) -> None:
        self.datastore = None


def nuubot_setup(path: Path = CONFIG_PATH) -> Nuubot:
    nuubot = Nuubot()
    return nuubot.setup(path)
