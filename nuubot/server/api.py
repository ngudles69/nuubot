from __future__ import annotations

from starlette.responses import JSONResponse

from nuubot.server import sweepmgr as sweepmgr_api
from nuubot.server.state import ensure_server_state


def register_api(rt) -> None:
    @rt("/ping")
    def get():
        return "pong"

    @rt("/status")
    def get():
        return JSONResponse({"status": "running"})

    @rt("/api/sweeps", methods="get")
    def get(request):
        try:
            ensure_server_state(request.app)
            data = sweepmgr_api.list_sweeps(request.app.state.sweepmgr)
            return ok(data)
        except Exception as exc:
            return error(str(exc), 400)

    @rt("/api/sweeps", methods="post")
    async def post(request):
        template = (await request.body()).decode("utf-8").strip()
        if not template:
            return error("template is required", 400)
        try:
            ensure_server_state(request.app)
            data = sweepmgr_api.create_sweep(request.app.state.sweepmgr, template)
            return ok(data, 201)
        except Exception as exc:
            return error(str(exc), 400)

    @rt("/api/sweeps/{sweep_id}", methods="get")
    def get(request, sweep_id: int):
        try:
            ensure_server_state(request.app)
            data = sweepmgr_api.load_sweep(request.app.state.sweepmgr, sweep_id)
            return ok(data)
        except Exception as exc:
            return error(str(exc), 400)

    @rt("/api/sweeps/{sweep_id}/run", methods="post")
    def post(request, sweep_id: int):
        if sweep_id <= 0:
            return error("sweep_id must be positive", 400)
        try:
            ensure_server_state(request.app)
            data = sweepmgr_api.run_sweep(request.app.state.sweepmgr, sweep_id)
            return ok(data, 202)
        except Exception as exc:
            return error(str(exc), 400)

    @rt("/api/sweeps/{sweep_id}/status", methods="get")
    def get(request, sweep_id: int):
        if sweep_id <= 0:
            return error("sweep_id must be positive", 400)
        try:
            ensure_server_state(request.app)
            data = sweepmgr_api.status_sweep(request.app.state.sweepmgr, sweep_id)
            return ok(data)
        except Exception as exc:
            return error(str(exc), 400)


def ok(data, status_code: int = 200):
    return JSONResponse({"ok": True, "data": data}, status_code=status_code)


def error(message: str, status_code: int):
    return JSONResponse({"ok": False, "error": message}, status_code=status_code)
