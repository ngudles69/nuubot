from __future__ import annotations

from pathlib import Path

from fasthtml.common import *
from monsterui.all import Card, CardTitle, Toast, ToastHT, ToastVT
from starlette.responses import RedirectResponse

from nuubot.server import sweepmgr as sweepmgr_api
from nuubot.server.state import ensure_server_state
from nuubot.webgui.layout import shell

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[3] / "workspace" / "templates" / "ema-1h-fast.toml"


def register(rt) -> None:
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
            ensure_server_state(request.app)
            data = sweepmgr_api.create_sweep(request.app.state.sweepmgr, template)
            request.session["toast"] = (f"Sweep ID {data['sweep_id']} created", "alert-success")
            return RedirectResponse("/sweeps", status_code=303)
        except Exception as exc:
            return create_page(template, str(exc))


def create_page(template: str, error: str = ""):
    message = ()
    if error:
        message = (Toast(error, cls=(ToastHT.end, ToastVT.top), alert_cls="alert-error", dur=3.0),)
    return shell(
        Section(
            Card(
                CardTitle("Create Sweep"),
                Form(
                    Textarea(template, name="template", cls="uk-textarea template-field", spellcheck="false"),
                    Button("Create Sweep", cls="uk-btn uk-btn-primary"),
                    method="post",
                    action="/sweeps/create",
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
