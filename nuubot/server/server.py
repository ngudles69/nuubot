from __future__ import annotations

from copy import deepcopy
import logging
from typing import TYPE_CHECKING

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from nuubot import nuubot_setup
from nuubot.core.logger import logger
from nuubot.core.telemetry import pt_now_ts_ms
from nuubot.server.botmgr import botmgr_setup
from nuubot.server.sweepmgr import sweepmgr_setup
from nuubot.webgui.app import WebGui

log = logger()

if TYPE_CHECKING:
    from nuubot.nuubot import Nuubot
    from nuubot.server.botmgr import BotManager
    from nuubot.server.sweepmgr import SweepManager


class Server:
    def __init__(self) -> None:
        self.nuubot: "Nuubot | None" = None
        self.botmgr: "BotManager | None" = None
        self.sweepmgr: "SweepManager | None" = None
        self.webgui: "WebGui | None" = None

    def init(self) -> "Server":
        self.nuubot = nuubot_setup()
        self.botmgr = botmgr_setup(self.nuubot)
        self.sweepmgr = sweepmgr_setup(self.nuubot)
        self.webgui = WebGui(self).init()
        return self

    def stop(self) -> None:
        pt_stop_ts_ms = pt_now_ts_ms()
        log.info("Server STOPPING...")
        if self.sweepmgr is not None:
            for result_thread in list(self.sweepmgr.result_threads.values()):
                result_thread.join()
        if self.nuubot is not None:
            self.nuubot.stop()
        log.info("Server STOPPED in %.3f secs.", (pt_now_ts_ms() - pt_stop_ts_ms) / 1000)


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
    """Start the Nuubot web server."""

    # Start timing.
    pt_start_ts_ms = pt_now_ts_ms()
    log.info("Server STARTING...")

    # Initialize server.
    server = Server().init()
    config = server.nuubot.config.server

    # Log startup.
    log.info("Server STARTED in %.3f secs.", (pt_now_ts_ms() - pt_start_ts_ms) / 1000)

    # Run web server.
    uvicorn.run(
        server.webgui.app,
        host=config.host,
        port=config.port,
        reload=config.reload,
        reload_dirs=["nuubot"] if config.reload else None,
        reload_includes=["*.py"] if config.reload else None,
        log_config=log_config(),
    )


def log_config() -> dict:
    config = deepcopy(LOGGING_CONFIG)
    config["filters"] = {"nuubot_messages": {"()": "nuubot.server.server.UvicornMessageFilter"}}
    config["handlers"]["default"]["filters"] = ["nuubot_messages"]
    return config


if __name__ == "__main__":
    main()
