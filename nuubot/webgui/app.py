from __future__ import annotations

from fasthtml.common import *

from nuubot.server.api import register_api
from nuubot.server.state import start_server_state, stop_server_state
from nuubot.webgui.layout import CSS, HEADERS, placeholder
from nuubot.webgui.sweeps import create as sweep_create
from nuubot.webgui.sweeps import list as sweep_list

app, rt = fast_app(hdrs=(*HEADERS, Style(CSS)), title="nuubot", secret_key="nuubot-webgui", pico=False)


@app.on_event("startup")
async def startup():
    start_server_state(app)


@app.on_event("shutdown")
async def shutdown():
    stop_server_state(app)


@rt("/")
def get():
    return placeholder("Dashboard", "Control surface for bots, sweeps, and server status.")


@rt("/bots")
def get():
    return placeholder("Bots", "Bot creation and lifecycle controls will live here.")


@rt("/server")
def get():
    return placeholder("Server", "Server health, sweep workers, and datastore status will live here.")


@rt("/user")
def get():
    return placeholder("User", "User settings will live here.")


sweep_create.register(rt)
sweep_list.register(rt)
register_api(rt)
