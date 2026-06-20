from __future__ import annotations

import logging
from pathlib import Path


def logger(path: str) -> logging.Logger:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(str(log_path.resolve()))
    if not log.handlers:
        handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)
        log.propagate = False
    return log
