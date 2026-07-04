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
.sweeps-panel { max-width: none; }
.panel h1 { font-size: 24px; margin: 0; font-weight: 700; }
.panel p { margin: 0 0 18px; color: hsl(var(--muted-foreground)); }
.table-wrap { overflow-x: auto; }
.metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 14px 0 18px; }
.metric {
  border: 1px solid hsl(var(--border));
  border-radius: 6px;
  padding: 10px 12px;
  background: hsl(var(--muted) / 0.18);
}
.metric-label { color: hsl(var(--muted-foreground)); font-size: 12px; }
.metric-value { font-size: 18px; font-weight: 700; margin-top: 2px; }
.chart-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  margin: 8px 0 2px;
}
.chart-readout {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  min-height: 28px;
  min-width: 0;
  color: hsl(var(--muted-foreground));
  font: 12px ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}
.chart-readout .readout-symbol { color: hsl(var(--foreground)); font-weight: 700; }
.chart-readout .readout-key { color: hsl(var(--muted-foreground)); }
.chart-readout .readout-value { color: hsl(var(--foreground)); }
.chart-readout .is-up { color: #22c55e; }
.chart-readout .is-down { color: #ef4444; }
.chart-legend { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 10px; color: #cbd5e1; font-size: 12px; }
.chart-legend-item { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
.chart-legend-swatch { width: 24px; height: 12px; border-radius: 3px; background: var(--legend-color); border: 1px solid rgba(255,255,255,0.28); }
.chart-legend-line { width: 24px; height: 0; border-top: 2px solid var(--legend-color); }
.chart-legend-dot { width: 12px; height: 12px; border-radius: 999px; background: var(--legend-color); }
.chart-legend-diamond { width: 13px; height: 13px; transform: rotate(45deg); background: var(--legend-color); }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; margin: 14px 0 18px; }
.summary-card {
  border: 1px solid hsl(var(--border));
  border-radius: 6px;
  padding: 10px 12px;
  background: hsl(var(--muted) / 0.14);
}
.summary-title { font-size: 12px; font-weight: 700; color: hsl(var(--foreground)); margin-bottom: 8px; }
.summary-row { display: grid; grid-template-columns: minmax(88px, 1fr) auto; gap: 10px; font-size: 12px; line-height: 1.65; }
.summary-label { color: hsl(var(--muted-foreground)); }
.summary-value { color: hsl(var(--foreground)); font-weight: 650; text-align: right; }
.summary-value.positive { color: #22c55e; }
.summary-value.negative { color: #ef4444; }
.chart-host { width: 100%; height: 936px; }
.chart-tabs { margin-top: 18px; border-top: 1px solid hsl(var(--border)); padding-top: 12px; }
.tab-buttons { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.tab-button {
  border: 1px solid hsl(var(--border));
  border-radius: 6px;
  padding: 7px 10px;
  background: hsl(var(--muted) / 0.12);
  color: hsl(var(--muted-foreground));
  font-size: 13px;
  cursor: pointer;
}
.tab-button.active { color: hsl(var(--foreground)); background: hsl(var(--accent)); }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th, .data-table td { border-bottom: 1px solid hsl(var(--border)); padding: 6px 8px; white-space: nowrap; text-align: left; }
.data-table th {
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  user-select: none;
  font-weight: 650;
  position: sticky;
  top: 0;
  background: hsl(var(--card));
  z-index: 1;
}
.data-table td { color: hsl(var(--foreground)); }
.data-table td.positive { color: #22c55e; font-weight: 650; }
.data-table td.negative { color: #ef4444; font-weight: 650; }
.data-table tr:hover td { background: hsl(var(--muted) / 0.12); }
.chart-tabs .table-wrap { max-height: 520px; overflow: auto; border: 1px solid hsl(var(--border)); border-radius: 6px; }
.position-filter {
  width: 260px;
  margin: 0 0 8px;
  padding: 7px 9px;
  border: 1px solid hsl(var(--border));
  border-radius: 6px;
  background: hsl(var(--background));
  color: hsl(var(--foreground));
  font-size: 12px;
}
.tree-toggle {
  width: 22px;
  height: 22px;
  border: 1px solid hsl(var(--border));
  border-radius: 4px;
  background: hsl(var(--muted) / 0.12);
  color: hsl(var(--muted-foreground));
  cursor: pointer;
  line-height: 1;
}
.tree-toggle.open { transform: rotate(90deg); color: hsl(var(--foreground)); }
.tree-row.hidden { display: none; }
.bot-row td { background: hsl(var(--muted) / 0.10); font-weight: 700; }
.position-row td:first-child, .order-row td:first-child, .fill-row td:first-child { padding-left: 18px; }
.order-row td { color: #cbd5e1; background: hsl(var(--muted) / 0.06); }
.fill-row td { color: hsl(var(--muted-foreground)); background: hsl(var(--muted) / 0.035); }
.config-json {
  max-height: 520px;
  overflow: auto;
  border: 1px solid hsl(var(--border));
  border-radius: 6px;
  padding: 12px;
  font: 12px ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}
.result-json {
  max-height: 70vh;
  overflow: auto;
  font: 12px ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}
.template-field {
  width: min(100%, 980px);
  min-height: 520px;
  resize: vertical;
  font: 13px ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
}
th.actions, td.actions { text-align: right; white-space: nowrap; }
th.center, td.center { text-align: center; }
.action-row { display: flex; justify-content: flex-end; align-items: center; gap: 6px; }
.action-row form { display: inline; margin: 0; }
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
    """Wrap page content in the WebGUI shell."""

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
