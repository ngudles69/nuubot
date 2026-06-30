from __future__ import annotations

from fasthtml.common import *
from monsterui.all import Card, CardTitle, Toast, ToastHT, ToastVT
from starlette.responses import RedirectResponse

from nuubot.server import sweepmgr as sweepmgr_api
from nuubot.server.state import ensure_server_state
from nuubot.webgui.layout import shell


def register(rt) -> None:
    @rt("/sweeps", methods="get")
    def get(request):
        ensure_server_state(request.app)
        rows = list(reversed(sweepmgr_api.list_sweeps(request.app.state.sweepmgr)["sweeps"]))
        flash = request.session.pop("toast", None)
        return shell(
            Section(
                Card(
                    CardTitle("Sweeps"),
                    A("Create Sweep", href="/sweeps/create", cls="uk-btn uk-btn-primary"),
                    sweeps_table(rows),
                    *toast_from_flash(flash),
                ),
                cls="panel",
            )
        )

    @rt("/sweeps/table", methods="get")
    def get(request):
        ensure_server_state(request.app)
        rows = list(reversed(sweepmgr_api.list_sweeps(request.app.state.sweepmgr)["sweeps"]))
        return sweeps_table(rows)

    @rt("/sweeps/{sweep_id}/run", methods="post")
    def post(request, sweep_id: int):
        if sweep_id <= 0:
            request.session["toast"] = ("sweep_id must be positive", "alert-error")
            return RedirectResponse("/sweeps", status_code=303)
        try:
            ensure_server_state(request.app)
            sweepmgr_api.run_sweep(request.app.state.sweepmgr, sweep_id)
            if request.headers.get("hx-request") == "true":
                rows = list(reversed(sweepmgr_api.list_sweeps(request.app.state.sweepmgr)["sweeps"]))
                return sweeps_table(rows)
            request.session["toast"] = (f"Sweep ID {sweep_id} submitted", "alert-success")
            return RedirectResponse("/sweeps", status_code=303)
        except Exception as exc:
            if request.headers.get("hx-request") == "true":
                rows = list(reversed(sweepmgr_api.list_sweeps(request.app.state.sweepmgr)["sweeps"]))
                return sweeps_table(rows, {sweep_id: str(exc)})
            request.session["toast"] = (str(exc), "alert-error")
            return RedirectResponse("/sweeps", status_code=303)


def sweeps_table(rows: list[dict], errors: dict[int, str] | None = None):
    errors = errors or {}
    attrs = {
        "id": "sweeps-table",
        "cls": "uk-table uk-table-divider uk-table-hover uk-table-sm uk-table-middle",
    }
    if any(sweep_is_active(row) for row in rows):
        attrs |= {"hx_get": "/sweeps/table", "hx_trigger": "every 2s", "hx_swap": "outerHTML"}
    return Table(
        Thead(
            Tr(
                Th("ID"),
                Th("Description"),
                Th("Status"),
                Th("Progress"),
                Th("Runs"),
                Th("Created"),
                Th("Actions", cls="actions"),
            )
        ),
        Tbody(*[sweep_row(row, errors.get(row["sweep_id"], "")) for row in rows]),
        **attrs,
    )


def sweep_row(row: dict, error: str = ""):
    progress = row["progress"] if row["total_count"] else ""
    status = error or row["status"]
    return Tr(
        Td(row["sweep_id"]),
        Td(row["sweep_desc"]),
        Td(
            Span(status, cls="run-status"),
            Span("submitting", cls="submit-status"),
        ),
        Td(progress),
        Td(row["sweeprun_count"]),
        Td(row["created_at"]),
        Td(
            A("Edit", href=f"/sweeps/{row['sweep_id']}/edit", cls="uk-btn uk-btn-sm uk-btn-default"),
            Form(
                Button("Run", cls="uk-btn uk-btn-sm uk-btn-default"),
                action=f"/sweeps/{row['sweep_id']}/run",
                method="post",
                hx_post=f"/sweeps/{row['sweep_id']}/run",
                hx_target="#sweeps-table",
                hx_swap="outerHTML",
                hx_indicator=f"#sweep-row-{row['sweep_id']}",
            ),
            cls="actions",
        ),
        id=f"sweep-row-{row['sweep_id']}",
    )


def sweep_is_active(row: dict) -> bool:
    return (
        row["status"] in {"queued", "running", "submitted"}
        or int(row.get("queued_count", 0)) > 0
        or int(row.get("running_count", 0)) > 0
    )


def load_row(sweepmgr, sweep_id: int) -> dict:
    for row in sweepmgr_api.list_sweeps(sweepmgr)["sweeps"]:
        if row["sweep_id"] == sweep_id:
            return row
    raise RuntimeError(f"sweep row missing: {sweep_id}")


def toast_from_flash(flash):
    if flash:
        message, alert_cls = flash
        return (toast(message, alert_cls),)
    return ()


def toast(message: str, alert_cls: str = "alert-success"):
    return Toast(message, cls=(ToastHT.end, ToastVT.top), alert_cls=alert_cls, dur=3.0)
