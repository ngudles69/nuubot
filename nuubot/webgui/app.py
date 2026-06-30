from __future__ import annotations

from fasthtml.common import *

from nuubot.server.api import register_api
from nuubot.webgui.layout import CSS, HEADERS, placeholder
from nuubot.webgui.sweeps import create as sweep_create
from nuubot.webgui.sweeps import list as sweep_list


class WebGui:
    def __init__(self, server) -> None:
        self.server = server
        self.app = None
        self.rt = None

    def init(self) -> "WebGui":
        self.app, self.rt = fast_app(
            hdrs=(*HEADERS, Style(CSS)),
            title="nuubot",
            secret_key="nuubot-webgui",
            pico=False,
        )

        @self.app.on_event("shutdown")
        async def shutdown():
            self.server.stop()

        self.register_pages()
        sweep_create.register(self.rt, self.server)
        sweep_list.register(self.rt, self.server)
        register_api(self.rt, self.server)
        return self

    def register_pages(self) -> None:
        rt = self.rt

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
