from __future__ import annotations

import argparse
from copy import deepcopy
import logging
import os

import uvicorn
from uvicorn.config import LOGGING_CONFIG


class UvicornMessageFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.getMessage() in {
            "Waiting for application startup.",
            "Waiting for application shutdown.",
        }:
            return False
        replacements = {
            "Application startup complete.": "Server startup complete.",
            "Shutting down": "Server shutdown in progress.",
            "Application shutdown complete.": "Server shutdown complete.",
        }
        replacement = replacements.get(record.getMessage())
        if replacement is not None:
            record.msg = replacement
            record.args = ()
        return True


def main() -> None:
    args = parse_args()
    host = os.getenv("NUUBOT_HOST", "127.0.0.1")
    port = int(os.getenv("NUUBOT_PORT", "5001"))
    print("INFO:     Server startup in progress.", flush=True)
    uvicorn.run(
        "nuubot.server.webgui:app",
        host=host,
        port=port,
        reload=args.reload,
        reload_dirs=["nuubot"] if args.reload else None,
        reload_includes=["*.py"] if args.reload else None,
        log_config=log_config(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", dest="reload", action="store_true", default=False)
    parser.add_argument("--no-reload", dest="reload", action="store_false")
    return parser.parse_args()


def log_config() -> dict:
    config = deepcopy(LOGGING_CONFIG)
    config["filters"] = {"nuubot_messages": {"()": "nuubot.server.server.UvicornMessageFilter"}}
    config["handlers"]["default"]["filters"] = ["nuubot_messages"]
    return config
