"""Server API routes.

All routes must use the standard response envelope documented in
`wiki/design/server-api.md`.
"""

from __future__ import annotations

from starlette.responses import JSONResponse


def register_api(rt, server) -> None:
    """Register JSON API routes."""

    @rt("/ping")
    def get():
        return ok("ping", "pong")

    @rt("/status")
    def get():
        return ok("server_status", {"status": "running"})

    @rt("/api/sweeps", methods="get")
    def get(request):
        try:
            data = server.sweepmgr.list()
            return ok("sweeps_list", data)
        except Exception as exc:
            return error("sweeps_list", str(exc), 400)

    @rt("/api/sweeps", methods="post")
    async def post(request):
        template = (await request.body()).decode("utf-8").strip()
        if not template:
            return error("sweep_create", "template is required", 400)
        try:
            sweep_id = server.sweepmgr.create(template)
            return ok("sweep_create", {"sweep_id": sweep_id}, 201, sweep_id)
        except Exception as exc:
            return error("sweep_create", str(exc), 400)

    @rt("/api/sweeps/{sweep_id}", methods="get")
    def get(request, sweep_id: int):
        try:
            config = server.sweepmgr.load(sweep_id)
            return ok("sweep_get", {"sweep_id": sweep_id, "config": config}, 200, sweep_id)
        except Exception as exc:
            return error("sweep_get", str(exc), 400, sweep_id)

    @rt("/api/sweeps/{sweep_id}/run", methods="post")
    def post(request, sweep_id: int):
        if sweep_id <= 0:
            return error("sweep_run", "sweep_id must be positive", 400, sweep_id)
        try:
            data = server.sweepmgr.run(sweep_id)
            return ok("sweep_run", data, 202, sweep_id)
        except Exception as exc:
            return error("sweep_run", str(exc), 400, sweep_id)

    @rt("/api/sweeps/{sweep_id}/metrics", methods="get")
    def get(request, sweep_id: int):
        if sweep_id <= 0:
            return error("sweep_metrics", "sweep_id must be positive", 400, sweep_id)
        try:
            data = server.sweepmgr.metrics(sweep_id)
            return ok("sweep_metrics", data, 200, sweep_id)
        except Exception as exc:
            return error("sweep_metrics", str(exc), 400, sweep_id)


def ok(response_type: str, data, status_code: int = 200, response_id: int | None = None):
    return JSONResponse({"status": "ok", "response": response(response_type, data, response_id)}, status_code=status_code)


def error(response_type: str, message: str, status_code: int, response_id: int | None = None):
    data = {"error": {"code": f"{response_type}_failed", "message": message}}
    return JSONResponse({"status": "err", "response": response(response_type, data, response_id)}, status_code=status_code)


def response(response_type: str, data, response_id: int | None = None):
    payload = {"type": response_type, "data": data}
    if response_id is not None:
        payload["id"] = response_id
    return payload
