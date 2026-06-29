from __future__ import annotations

from starlette.responses import JSONResponse


def register_api(rt) -> None:
    @rt("/ping")
    def get():
        return "pong"

    @rt("/status")
    def get():
        return JSONResponse({"status": "running"})
