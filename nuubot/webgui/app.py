from __future__ import annotations

from fasthtml.common import *

from nuubot.server.api import register_api

CSS = """
:root {
  color-scheme: dark;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #101214;
  color: #e8eaed;
}
body {
  margin: 0;
}
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: 52px 1fr;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  border-bottom: 1px solid #2a3036;
  background: #171a1f;
}
.brand {
  font-size: 17px;
  font-weight: 700;
}
.status {
  font-size: 13px;
  color: #7fd6a8;
}
.body {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 0;
}
.sidebar {
  border-right: 1px solid #2a3036;
  background: #171a1f;
  padding: 14px;
}
.navitem {
  display: block;
  padding: 9px 10px;
  border-radius: 6px;
  color: #d9dde3;
  text-decoration: none;
  font-size: 14px;
}
.navitem:hover {
  background: #242a31;
}
.main {
  padding: 22px;
}
.panel {
  max-width: 920px;
}
.panel h1 {
  font-size: 24px;
  margin: 0 0 10px;
}
.panel p {
  margin: 0 0 18px;
  color: #a8b0ba;
}
.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.action {
  border: 1px solid #3a424c;
  background: #1c2026;
  color: #e8eaed;
  border-radius: 6px;
  padding: 9px 12px;
  font-size: 14px;
}
@media (max-width: 760px) {
  .body {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #2a3036;
  }
}
"""

app, rt = fast_app(hdrs=(Style(CSS),), title="nuubot", secret_key="nuubot-webgui")


def shell(content):
    return Div(
        Header(
            Div("nuubot", cls="brand"),
            Div("server online", cls="status"),
            cls="topbar",
        ),
        Div(
            Aside(
                Nav(
                    A("Dashboard", href="/", cls="navitem"),
                    A("Bots", href="/bots", cls="navitem"),
                    A("Sweeps", href="/sweeps", cls="navitem"),
                    A("Server", href="/server", cls="navitem"),
                ),
                cls="sidebar",
            ),
            Main(content, cls="main"),
            cls="body",
        ),
        cls="shell",
    )


def placeholder(title: str, text: str):
    return shell(
        Section(
            H1(title),
            P(text),
            Div(
                Button("Create bot", cls="action"),
                Button("Create sweep", cls="action"),
                Button("Refresh", cls="action"),
                cls="actions",
            ),
            cls="panel",
        )
    )


@rt("/")
def get():
    return placeholder("Dashboard", "Control surface for bots, sweeps, and server status.")


@rt("/bots")
def get():
    return placeholder("Bots", "Bot creation and lifecycle controls will live here.")


@rt("/sweeps")
def get():
    return placeholder("Sweeps", "Sweep creation and run controls will live here.")


@rt("/server")
def get():
    return placeholder("Server", "Server health, Ray status, and datastore status will live here.")


register_api(rt)
