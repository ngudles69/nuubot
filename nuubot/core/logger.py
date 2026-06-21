"""Logger

Logging standard:

Every non-definition module uses module-level logging by default:

from nuubot.core.logger import logger
log = logger("workspace/logs/runtime.log")

Use `now=` when a function owns runtime clock context:

log.debug("runtime init", now=clock.now_ms())

Without `now=`, the log line only shows the wall-clock logging timestamp.

Module-level logging is permanent. The target file may temporarily change
during debugging.

Do not embed loggers inside normal objects. Specific owner objects like bots,
sweepruns, and sweeps may use class/object-level logs when they need their own
output file.

Specific bots, sweepruns, or sweeps may define their own file logger when they
need separate output. Keep the file/path choice explicit and simple.

2026-06-21 01:18:38,393 [ INFO] process_risk
2026-06-21 01:18:38,393 [DEBUG] results:
{
  "field": 112
}

Prefer next-line pretty JSON for long structured payloads. Keep short payloads
like BBO snapshots inline when that is easier to read. Let the code choose the
readable shape. User readability is the priority; if in doubt, ask the user.
"""

from __future__ import annotations

import logging
from typing import Any
from pathlib import Path


class NuuLogger:
    def __init__(self, log: logging.Logger) -> None:
        self.log = log

    def debug(self, message: str, *args: Any, now: int | None = None, **kwargs: Any) -> None:
        self.log.debug(self._message(message, now), *args, **kwargs)

    def info(self, message: str, *args: Any, now: int | None = None, **kwargs: Any) -> None:
        self.log.info(self._message(message, now), *args, **kwargs)

    def warning(self, message: str, *args: Any, now: int | None = None, **kwargs: Any) -> None:
        self.log.warning(self._message(message, now), *args, **kwargs)

    def error(self, message: str, *args: Any, now: int | None = None, **kwargs: Any) -> None:
        self.log.error(self._message(message, now), *args, **kwargs)

    def _message(self, message: str, now: int | None) -> str:
        if now is None:
            return message
        return f"{message} now_ms={now}"


def logger(path: str) -> NuuLogger:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(str(log_path.resolve()))
    if not log.handlers:
        handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)5s] %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)
        log.propagate = False
    return NuuLogger(log)
