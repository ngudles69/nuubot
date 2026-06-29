from __future__ import annotations

import os

import uvicorn

from nuubot import nuubot_setup
from nuubot.server.webgui import app


def main() -> None:
    host = os.getenv("NUUBOT_HOST", "127.0.0.1")
    port = int(os.getenv("NUUBOT_PORT", "5001"))
    nuubot = nuubot_setup()
    try:
        print(f"nuubot server: http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)
    finally:
        nuubot.stop()
