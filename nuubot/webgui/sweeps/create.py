from __future__ import annotations

import json
from pathlib import Path

from fasthtml.common import *
from monsterui.all import Card, CardTitle, Toast, ToastHT, ToastVT
from starlette.responses import RedirectResponse

from nuubot.webgui.layout import shell

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[3] / "workspace" / "templates" / "sweeps" / "emacross-tradebot-2025-halves.toml"


def register(rt, server) -> None:
    @rt("/sweeps/create", methods="get")
    def get(error: str = ""):
        return create_page(default_template(), error)

    @rt("/sweeps/create", methods="post")
    async def post(request):
        form = await request.form()
        template = str(form.get("template", "")).strip()
        if not template:
            return create_page("", "template is required")
        try:
            sweep_id = server.sweepmgr.create(template)
            request.session["toast"] = (f"Sweep ID {sweep_id} created", "alert-success")
            return RedirectResponse("/sweeps", status_code=303)
        except Exception as exc:
            return create_page(template, str(exc))

    @rt("/sweeps/{sweep_id}/edit", methods="get")
    def get(request, sweep_id: int, error: str = ""):
        config = server.sweepmgr.load(sweep_id)
        template = json.dumps(config, indent=2, sort_keys=True)
        return create_page(template, error, title=f"Edit Sweep {sweep_id}", action=f"/sweeps/{sweep_id}/edit", primary="Save Sweep", rerun=True)

    @rt("/sweeps/{sweep_id}/edit", methods="post")
    async def post(request, sweep_id: int):
        form = await request.form()
        template = str(form.get("template", "")).strip()
        if not template:
            return create_page("", "template is required", title=f"Edit Sweep {sweep_id}", action=f"/sweeps/{sweep_id}/edit", primary="Save Sweep", rerun=True)
        try:
            server.sweepmgr.update(sweep_id, template)
            if form.get("run"):
                server.sweepmgr.run(sweep_id)
                request.session["toast"] = (f"Sweep ID {sweep_id} saved and submitted", "alert-success")
            else:
                request.session["toast"] = (f"Sweep ID {sweep_id} saved", "alert-success")
            return RedirectResponse("/sweeps", status_code=303)
        except Exception as exc:
            return create_page(template, str(exc), title=f"Edit Sweep {sweep_id}", action=f"/sweeps/{sweep_id}/edit", primary="Save Sweep", rerun=True)


def create_page(template: str, error: str = "", *, title: str = "Create Sweep", action: str = "/sweeps/create", primary: str = "Create Sweep", rerun: bool = False):
    message = ()
    if error:
        message = (Toast(error, cls=(ToastHT.end, ToastVT.top), alert_cls="alert-error", dur=3.0),)
    buttons = [Button(primary, cls="uk-btn uk-btn-primary")]
    if rerun:
        buttons.append(Button("Save and Run", name="run", value="1", cls="uk-btn uk-btn-default"))
    return shell(
        Section(
            Card(
                CardTitle(title),
                Form(
                    Textarea(template, name="template", cls="uk-textarea template-field", spellcheck="false"),
                    Div(*buttons, cls="actions"),
                    method="post",
                    action=action,
                    cls="space-y-4",
                ),
                *message,
            ),
            cls="panel",
        )
    )


def default_template() -> str:
    if DEFAULT_TEMPLATE.exists():
        return DEFAULT_TEMPLATE.read_text(encoding="utf-8")
    return ""
