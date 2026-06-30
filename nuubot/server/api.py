from __future__ import annotations

from starlette.responses import JSONResponse


def register_api(rt, server) -> None:
    @rt("/ping")
    def get():
        return "pong"

    @rt("/status")
    def get():
        return JSONResponse({"status": "running"})

    @rt("/api/sweeps", methods="get")
    def get(request):
        try:
            data = server.sweepmgr.list()
            return ok(data)
        except Exception as exc:
            return error(str(exc), 400)

    @rt("/api/sweeps", methods="post")
    async def post(request):
        template = (await request.body()).decode("utf-8").strip()
        if not template:
            return error("template is required", 400)
        try:
            sweep_id = server.sweepmgr.create(template)
            return ok({"sweep_id": sweep_id}, 201)
        except Exception as exc:
            return error(str(exc), 400)

    @rt("/api/sweeps/{sweep_id}", methods="get")
    def get(request, sweep_id: int):
        try:
            config = server.sweepmgr.load(sweep_id)
            return ok({"sweep_id": sweep_id, "config": config})
        except Exception as exc:
            return error(str(exc), 400)

    @rt("/api/sweeps/{sweep_id}/run", methods="post")
    def post(request, sweep_id: int):
        if sweep_id <= 0:
            return error("sweep_id must be positive", 400)
        try:
            data = server.sweepmgr.run(sweep_id)
            return ok(data, 202)
        except Exception as exc:
            return error(str(exc), 400)

    @rt("/api/sweeps/{sweep_id}/status", methods="get")
    def get(request, sweep_id: int):
        if sweep_id <= 0:
            return error("sweep_id must be positive", 400)
        try:
            data = server.sweepmgr.status(sweep_id)
            return ok(data)
        except Exception as exc:
            return error(str(exc), 400)


def ok(data, status_code: int = 200):
    return JSONResponse({"ok": True, "data": data}, status_code=status_code)


def error(message: str, status_code: int):
    return JSONResponse({"ok": False, "error": message}, status_code=status_code)
