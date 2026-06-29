from __future__ import annotations

from fasthtml.common import *
from monsterui.all import Card, CardTitle, Theme, UkIcon

HEADERS = (*Theme.green.headers(mode="dark"),)

CSS = """
body { margin: 0; background: hsl(var(--background)); color: hsl(var(--foreground)); }
.shell { min-height: 100vh; display: grid; grid-template-rows: 56px 1fr; }
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 18px;
  border-bottom: 1px solid hsl(var(--border));
  background: hsl(var(--card));
}
.brand {
  color: hsl(var(--foreground));
  font-size: 17px;
  font-weight: 700;
  text-decoration: none;
}
.userlink {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  border: 1px solid hsl(var(--border));
  color: hsl(var(--muted-foreground));
  text-decoration: none;
}
.body { display: grid; grid-template-columns: 220px 1fr; min-height: 0; }
.sidebar { border-right: 1px solid hsl(var(--border)); background: hsl(var(--card)); padding: 14px; }
.navitem {
  display: block;
  padding: 9px 10px;
  border-radius: 6px;
  color: hsl(var(--muted-foreground));
  text-decoration: none;
  font-size: 14px;
}
.navitem:hover { background: hsl(var(--accent)); color: hsl(var(--accent-foreground)); }
.main { padding: 22px; }
.panel { max-width: 1120px; }
.panel h1 { font-size: 24px; margin: 0; font-weight: 700; }
.panel p { margin: 0 0 18px; color: hsl(var(--muted-foreground)); }
.template-field {
  width: min(100%, 980px);
  min-height: 520px;
  resize: vertical;
  font: 13px ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}
th.actions, td.actions { text-align: right; white-space: nowrap; }
.submit-status { display: none; }
.htmx-request .run-status { display: none; }
.htmx-request .submit-status { display: inline; }
.toast { top: 70px; z-index: 60; }
.uk-card { border: 1px solid hsl(var(--border)); }
@media (max-width: 760px) {
  .body { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid hsl(var(--border)); }
}
"""


def shell(content):
    return Div(
        Header(
            A("nuubot", href="/", cls="brand"),
            A(UkIcon("user", height=17, width=17), href="/user", cls="userlink", title="User"),
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
    return shell(Section(Card(CardTitle(title), P(text)), cls="panel"))
