from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from nuubot.datastore import BotRow
from nuubot.nuubot import Nuubot

BOT_DB_RE = re.compile(r"^[A-Za-z0-9_-]+_bot_(\d+)\.db$")


@dataclass
class BotManager:
    nuubot: Nuubot

    def archive_dir(self) -> Path:
        if self.nuubot.datastore.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        return self.nuubot.datastore.dbroot / "archived"

    def _one_bot_path(self, bot_id: int, *, archived: bool) -> Path:
        if bot_id <= 0:
            raise RuntimeError(f"invalid bot_id: {bot_id}")
        root = self.archive_dir() if archived else self.nuubot.datastore.dbroot
        if root is None:
            raise RuntimeError("datastore DB root missing")
        paths = [path for path in root.glob(f"*_bot_{bot_id}.db") if BOT_DB_RE.match(path.name)]
        if len(paths) != 1:
            place = "archived bot" if archived else "bot"
            raise RuntimeError(f"{place} DB expected 1 file, got {len(paths)}: {bot_id}")
        return paths[0]

    def archive(self, bot_id: int) -> None:
        source = self._one_bot_path(bot_id, archived=False)
        target = self.archive_dir() / source.name
        if target.exists():
            raise RuntimeError(f"bot already archived: {bot_id}")
        bot = self.nuubot.datastore.get(source, BotRow, bot_id=bot_id)
        if bot.status in {"starting", "running", "stopping"}:
            raise RuntimeError(f"cannot archive active bot: {bot_id}")
        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)

    def unarchive(self, bot_id: int) -> None:
        source = self._one_bot_path(bot_id, archived=True)
        target = self.nuubot.datastore.dbpath(source.name)
        if target.exists():
            raise RuntimeError(f"bot already active: {bot_id}")
        source.replace(target)


def botmgr_setup(nuubot: Nuubot) -> BotManager:
    if nuubot.config is None or nuubot.datastore is None:
        raise RuntimeError("nuubot_setup() must complete before botmgr_setup()")
    return BotManager(nuubot)
