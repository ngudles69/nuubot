from __future__ import annotations

import logging
from pathlib import Path

LOG_DIR = Path("workspace/logs")
DEFAULT_LOG_NAME = "server.log"


def logger(name: str = DEFAULT_LOG_NAME) -> logging.Logger:
    log_path = LOG_DIR / name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(str(log_path.resolve()))
    if not log.handlers:
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d [%(levelname)5s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "%(levelname)s:     %(message)s",
            )
        )
        log.addHandler(file_handler)
        log.addHandler(console_handler)
        log.setLevel(logging.DEBUG)
        log.propagate = False
    return log
