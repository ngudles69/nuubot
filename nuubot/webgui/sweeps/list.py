from __future__ import annotations

import json

from fasthtml.common import *
from monsterui.all import Card, CardTitle, Toast, ToastHT, ToastVT
from starlette.responses import RedirectResponse

from nuubot.webgui.layout import shell


def register(rt, server) -> None:
    @rt("/sweeps", methods="get")
    def get(request):
        rows = list(reversed(server.sweepmgr.list()["sweeps"]))
        flash = request.session.pop("toast", None)
        return shell(
            Section(
                Card(
                    CardTitle("Sweeps"),
                    A("Create Sweep", href="/sweeps/create", cls="uk-btn uk-btn-primary"),
                    A("Archived", href="/sweeps/archived", cls="uk-btn uk-btn-default"),
                    Div(sweeps_table(rows), cls="table-wrap"),
                    *toast_from_flash(flash),
                ),
                cls="panel sweeps-panel",
            )
        )

    @rt("/sweeps/archived", methods="get")
    def get(request):
        rows = list(reversed(server.sweepmgr.list_archives()["sweeps"]))
        flash = request.session.pop("toast", None)
        return shell(
            Section(
                Card(
                    CardTitle("Archived Sweeps"),
                    A("Active Sweeps", href="/sweeps", cls="uk-btn uk-btn-default"),
                    Div(sweeps_table(rows, archived=True), cls="table-wrap"),
                    *toast_from_flash(flash),
                ),
                cls="panel sweeps-panel",
            )
        )

    @rt("/sweeps/archived/{sweep_id}/metrics", methods="get")
    def get(request, sweep_id: int):
        result = server.sweepmgr.metrics(sweep_id, archived=True)
        return shell(
            Section(
                Card(
                    CardTitle(f"Archived Sweep {sweep_id} Metrics"),
                    Pre(json.dumps(result, indent=2, sort_keys=True), cls="result-json"),
                    A("Back", href="/sweeps/archived", cls="uk-btn uk-btn-default"),
                ),
                cls="panel sweeps-panel",
            )
        )

    @rt("/sweeps/{sweep_id}/metrics", methods="get")
    def get(request, sweep_id: int):
        result = server.sweepmgr.metrics(sweep_id)
        return shell(
            Section(
                Card(
                    CardTitle(f"Sweep {sweep_id} Metrics"),
                    Pre(json.dumps(result, indent=2, sort_keys=True), cls="result-json"),
                    A("Back", href="/sweeps", cls="uk-btn uk-btn-default"),
                ),
                cls="panel sweeps-panel",
            )
        )

    @rt("/sweeps/table", methods="get")
    def get(request):
        rows = list(reversed(server.sweepmgr.list()["sweeps"]))
        return sweeps_table(rows)

    @rt("/sweeps/{sweep_id}/run", methods="post")
    def post(request, sweep_id: int):
        if sweep_id <= 0:
            request.session["toast"] = ("sweep_id must be positive", "alert-error")
            return RedirectResponse("/sweeps", status_code=303)
        try:
            server.sweepmgr.run(sweep_id)
            if request.headers.get("hx-request") == "true":
                rows = list(reversed(server.sweepmgr.list()["sweeps"]))
                return sweeps_table(rows)
            request.session["toast"] = (f"Sweep ID {sweep_id} submitted", "alert-success")
            return RedirectResponse("/sweeps", status_code=303)
        except Exception as exc:
            if request.headers.get("hx-request") == "true":
                rows = list(reversed(server.sweepmgr.list()["sweeps"]))
                return sweeps_table(rows, {sweep_id: str(exc)})
            request.session["toast"] = (str(exc), "alert-error")
            return RedirectResponse("/sweeps", status_code=303)

    @rt("/sweeps/{sweep_id}/clone", methods="post")
    def post(request, sweep_id: int):
        try:
            new_id = server.sweepmgr.clone(sweep_id)
            request.session["toast"] = (f"Sweep ID {new_id} cloned", "alert-success")
            return RedirectResponse(f"/sweeps/{new_id}/edit", status_code=303)
        except Exception as exc:
            request.session["toast"] = (str(exc), "alert-error")
            return RedirectResponse("/sweeps", status_code=303)

    @rt("/sweeps/{sweep_id}/delete", methods="post")
    def post(request, sweep_id: int):
        try:
            server.sweepmgr.delete(sweep_id)
            request.session["toast"] = (f"Sweep ID {sweep_id} deleted", "alert-success")
        except Exception as exc:
            request.session["toast"] = (str(exc), "alert-error")
        return RedirectResponse("/sweeps", status_code=303)

    @rt("/sweeps/{sweep_id}/archive", methods=["get", "post"])
    def post(request, sweep_id: int):
        try:
            server.sweepmgr.archive(sweep_id)
            request.session["toast"] = (f"Sweep ID {sweep_id} archived", "alert-success")
        except Exception as exc:
            request.session["toast"] = (str(exc), "alert-error")
        return RedirectResponse("/sweeps", status_code=303)

    @rt("/sweeps/{sweep_id}/unarchive", methods=["get", "post"])
    def post(request, sweep_id: int):
        try:
            server.sweepmgr.unarchive(sweep_id)
            request.session["toast"] = (f"Sweep ID {sweep_id} unarchived", "alert-success")
        except Exception as exc:
            request.session["toast"] = (str(exc), "alert-error")
        return RedirectResponse("/sweeps/archived", status_code=303)


def sweeps_table(rows: list[dict], errors: dict[int, str] | None = None, archived: bool = False):
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
                Th("Name"),
                Th("Description"),
                Th("Status", cls="center"),
                Th("Progress", cls="center"),
                Th("Runs", cls="center"),
                Th("Win/Lose", cls="center"),
                Th("Profit Factor", cls="center"),
                Th("Expected Value", cls="center"),
                Th("Last Run Date", cls="center"),
                Th("Actions", cls="actions"),
            )
        ),
        Tbody(*[sweep_row(row, errors.get(row["sweep_id"], ""), archived) for row in rows]),
        **attrs,
    )


def sweep_row(row: dict, error: str = "", archived: bool = False):
    progress = row["progress"] if row["total_count"] else ""
    status = error or row["status"]
    return Tr(
        Td(row["sweep_id"]),
        Td(row["name"]),
        Td(row["sweep_desc"]),
        Td(
            Span(status, cls="run-status"),
            Span("submitting", cls="submit-status"),
            cls="center",
        ),
        Td(progress, cls="center"),
        Td(row["sweeprun_count"], cls="center"),
        Td(row["win_loss"], cls="center"),
        Td(row["profit_factor"], cls="center"),
        Td(row["ev"], cls="center"),
        Td(row["updated_at"] or row["created_at"], cls="center"),
        Td(
            archived_actions(row["sweep_id"]) if archived else active_actions(row),
            cls="actions",
        ),
        id=f"sweep-row-{row['sweep_id']}",
    )


def active_actions(row: dict):
    sweep_id = row["sweep_id"]
    return Div(
        A("View", href=f"/sweeps/{sweep_id}/metrics", cls="uk-btn uk-btn-sm uk-btn-default"),
        Form(
            Button("Run", cls="uk-btn uk-btn-sm uk-btn-default"),
            action=f"/sweeps/{sweep_id}/run",
            method="post",
            hx_post=f"/sweeps/{sweep_id}/run",
            hx_target="#sweeps-table",
            hx_swap="outerHTML",
            hx_indicator=f"#sweep-row-{sweep_id}",
        ),
        A("Edit", href=f"/sweeps/{sweep_id}/edit", cls="uk-btn uk-btn-sm uk-btn-default"),
        Form(Button("Clone", cls="uk-btn uk-btn-sm uk-btn-default"), action=f"/sweeps/{sweep_id}/clone", method="post"),
        Form(Button("Archive", cls="uk-btn uk-btn-sm uk-btn-default"), action=f"/sweeps/{sweep_id}/archive", method="post"),
        Form(Button("Delete", cls="uk-btn uk-btn-sm uk-btn-danger"), action=f"/sweeps/{sweep_id}/delete", method="post"),
        cls="action-row",
    )


def archived_actions(sweep_id: int):
    return Div(
        A("View", href=f"/sweeps/archived/{sweep_id}/metrics", cls="uk-btn uk-btn-sm uk-btn-default"),
        Form(Button("Unarchive", cls="uk-btn uk-btn-sm uk-btn-default"), action=f"/sweeps/{sweep_id}/unarchive", method="post"),
        cls="action-row",
    )


def sweep_is_active(row: dict) -> bool:
    return (
        row["status"] in {"queued", "running", "submitted"}
        or int(row.get("queued_count", 0)) > 0
        or int(row.get("running_count", 0)) > 0
    )


def toast_from_flash(flash):
    if flash:
        message, alert_cls = flash
        return (toast(message, alert_cls),)
    return ()


def toast(message: str, alert_cls: str = "alert-success"):
    return Toast(message, cls=(ToastHT.end, ToastVT.top), alert_cls=alert_cls, dur=3.0)
