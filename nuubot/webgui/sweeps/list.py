from __future__ import annotations

import json

from fasthtml.common import *
from monsterui.all import Card, CardTitle, Toast, ToastHT, ToastVT
from starlette.responses import RedirectResponse

from nuubot.webgui.layout import shell


def register(rt, server) -> None:
    """Register sweep list, metrics, and action routes."""

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

    @rt("/sweeps/{sweep_id}", methods="get")
    def get(request, sweep_id: int):
        result = server.sweepmgr.detail(sweep_id)
        return sweep_detail_page(result)

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

    @rt("/sweeps/{sweep_id}/runs/{sweeprun_id}", methods="get")
    def get(request, sweep_id: int, sweeprun_id: int):
        result = server.sweepmgr.sweeprun_chart(sweep_id, sweeprun_id)
        return sweeprun_chart_page(result)

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
    """Render the sweeps table."""

    # Configure table.
    errors = errors or {}
    attrs = {
        "id": "sweeps-table",
        "cls": "uk-table uk-table-divider uk-table-hover uk-table-sm uk-table-middle",
    }
    if any(sweep_is_active(row) for row in rows):
        attrs |= {"hx_get": "/sweeps/table", "hx_trigger": "every 2s", "hx_swap": "outerHTML"}

    # Build table.
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
    """Render one sweep table row."""

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
    """Render active sweep actions."""

    sweep_id = row["sweep_id"]
    return Div(
        A("View", href=f"/sweeps/{sweep_id}", cls="uk-btn uk-btn-sm uk-btn-default"),
        A("Metrics", href=f"/sweeps/{sweep_id}/metrics", cls="uk-btn uk-btn-sm uk-btn-default"),
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


def sweep_detail_page(result: dict):
    sweep_id = result["sweep_id"]
    return shell(
        Section(
            Card(
                CardTitle(f"Sweep {sweep_id}: {result['name']}"),
                A("Back", href="/sweeps", cls="uk-btn uk-btn-default"),
                A("Metrics JSON", href=f"/sweeps/{sweep_id}/metrics", cls="uk-btn uk-btn-default"),
                metric_grid([
                    ("Status", result["status"]),
                    ("Progress", result["progress"]),
                    ("Sweepruns", result["sweeprun_count"]),
                    ("Win/Lose", result["win_loss"]),
                    ("Profit Factor", result["profit_factor"]),
                    ("Expected Value", result["ev"]),
                    ("Positions", result["position_count"]),
                    ("Fills", result["fill_count"]),
                ]),
                Div(sweepruns_table(sweep_id, result["sweepruns"]), cls="table-wrap"),
            ),
            cls="panel sweeps-panel",
        )
    )


def metric_grid(items: list[tuple[str, object]]):
    return Div(
        *[
            Div(
                Div(label, cls="metric-label"),
                Div(str(value), cls="metric-value"),
                cls="metric",
            )
            for label, value in items
        ],
        cls="metric-grid",
    )


def sweepruns_table(sweep_id: int, rows: list[dict]):
    return Table(
        Thead(
            Tr(
                Th("Run"),
                Th("Symbol"),
                Th("Interval", cls="center"),
                Th("Status", cls="center"),
                Th("PnL", cls="center"),
                Th("Trades", cls="center"),
                Th("Wins", cls="center"),
                Th("Losses", cls="center"),
                Th("Ticks", cls="center"),
                Th("Actions", cls="actions"),
            )
        ),
        Tbody(*[sweeprun_row(sweep_id, row) for row in rows]),
        cls="uk-table uk-table-divider uk-table-hover uk-table-sm uk-table-middle",
    )


def sweeprun_row(sweep_id: int, row: dict):
    return Tr(
        Td(row["sweeprun_id"]),
        Td(row["symbol"]),
        Td(row["interval"], cls="center"),
        Td(row["status"], cls="center"),
        Td(row["pnl_pct"], cls="center"),
        Td(row["trades"], cls="center"),
        Td(row["wins"], cls="center"),
        Td(row["losses"], cls="center"),
        Td(row["ticks"], cls="center"),
        Td(A("Chart", href=f"/sweeps/{sweep_id}/runs/{row['sweeprun_id']}", cls="uk-btn uk-btn-sm uk-btn-default"), cls="actions"),
    )


def sweeprun_chart_page(result: dict):
    sweep_id = result["sweep_id"]
    run = result["sweeprun"]
    title = f"Sweep {sweep_id} Run {run['sweeprun_id']} Chart"
    return shell(
        Section(
            Card(
                CardTitle(title),
                summary_grid(result["summary_groups"]),
                Div(
                    Div(id="chart-readout", cls="chart-readout"),
                    chart_legend(result),
                    cls="chart-toolbar",
                ),
                Div(id="sweeprun-chart", cls="chart-host"),
                chart_tables(result["tables"]),
                Script(src="https://cdn.jsdelivr.net/npm/echarts@6.0.0/dist/echarts.min.js"),
                Script(chart_script(result)),
                Script(tables_script()),
            ),
            cls="panel sweeps-panel",
        )
    )


def summary_grid(groups: list[dict]):
    return Div(
        *[
            Div(
                Div(group["title"], cls="summary-title"),
                *[
                    Div(
                        Span(item["label"], cls="summary-label"),
                        Span(item["value"], cls=f"summary-value {item.get('tone', '')}", title=item.get("title", "")),
                        cls="summary-row",
                    )
                    for item in group["items"]
                ],
                cls="summary-card",
            )
            for group in groups
        ],
        cls="summary-grid",
    )


def chart_legend(result: dict):
    items = [
        ("executor", "#5b7cfa", "swatch"),
        ("TP", "#22c55e", "line"),
        ("SL", "#ef4444", "line"),
        (result["symbol"], "#22c55e", "swatch"),
        *[(line["name"], line["color"], "line") for line in result["indicators"]["lines"]],
        ("signals", "#a3e635", "diamond"),
        ("entry/exit", "#6366f1", "dot"),
    ]
    return Div(
        *[
            Span(
                Span(cls=f"chart-legend-{kind}", style=f"--legend-color:{color}"),
                Span(label),
                cls="chart-legend-item",
            )
            for label, color, kind in items
        ],
        cls="chart-legend",
    )


def chart_tables(tables: list[dict]):
    return Div(
        Div(
            *[
                Button(
                    tab_label(table),
                    type="button",
                    cls=f"tab-button {'active' if index == 0 else ''}",
                    **{"data-tab": table["key"]},
                )
                for index, table in enumerate(tables)
            ],
            cls="tab-buttons",
        ),
        *[
            Div(
                table_panel(table),
                id=f"tab-{table['key']}",
                cls=f"tab-panel {'active' if index == 0 else ''}",
            )
            for index, table in enumerate(tables)
        ],
        cls="chart-tabs",
    )


def tab_label(table: dict):
    if table["key"] == "config":
        return "Config"
    if table["key"] == "bots":
        return f"Bots ({len(table['rows'])})"
    return f"{table['title']} ({len(table['rows'])})"


def table_panel(table: dict):
    if table["key"] == "bots":
        return bots_table(table)
    if table["key"] == "config":
        return Pre(table["config_json"], cls="config-json")
    return Div(sortable_table(table), cls="table-wrap")


def bots_table(table: dict):
    return Div(
        Input(type="search", placeholder="Filter positions", cls="position-filter", **{"data-filter": "bots"}),
        Div(
            Table(
                Thead(
                    Tr(
                        Th(""),
                        Th("Bot / Position", **{"data-position-sort": 0}),
                        Th("Status", **{"data-position-sort": 2}),
                        Th("Side", **{"data-position-sort": 1}),
                        Th("Entry", **{"data-position-sort": 3}),
                        Th("Exit", **{"data-position-sort": 4}),
                        Th("Net PnL", **{"data-position-sort": 5}),
                        Th("Opened", **{"data-position-sort": 6}),
                        Th("Closed", **{"data-position-sort": 7}),
                        Th("Exit Reason", **{"data-position-sort": 8}),
                    )
                ),
                Tbody(*[row for bot in table["rows"] for row in bot_rows(bot)]),
                cls="data-table tree-table",
            ),
            cls="table-wrap",
        ),
    )


def bot_rows(bot: dict):
    botrun = bot["botrun"]
    bot_id = f"bot-{botrun['id']}"
    rows = [
        Tr(
            Td(tree_button(bot_id, "bot")),
            Td(f"Bot {botrun['index']}"),
            Td(botrun["status"]),
            Td(f"positions: {botrun['position_count']}"),
            Td(""),
            Td(""),
            Td(botrun["pnl"], cls=pnl_class(botrun["pnl"])),
            Td(""),
            Td(""),
            Td(""),
            cls="tree-row bot-row",
            **{"data-bot": bot_id},
        )
    ]
    for position in bot["positions"]:
        rows.append(position_row(bot_id, position))
        for order in position["orders"]:
            rows.append(order_row(position["cells"][0], order))
            for fill in order["fills"]:
                rows.append(fill_row(order["cells"][0], fill))
    return rows


def position_row(bot_id: str, position: dict):
    position_id = str(position["cells"][0])
    cells = position["cells"]
    attrs = {
        "data-parent-bot": bot_id,
        "data-position": position_id,
        "data-filter-text": " ".join(str(value) for value in cells).lower(),
    }
    attrs.update({f"data-sort-{index}": str(value) for index, value in enumerate(cells)})
    return Tr(
        Td(tree_button(position_id, "position") if position["orders"] else ""),
        Td(str(cells[0])),
        Td(str(cells[2])),
        Td(str(cells[1])),
        Td(str(cells[3])),
        Td(str(cells[4])),
        Td(str(cells[5]), cls=pnl_class(cells[5])),
        Td(str(cells[6])),
        Td(str(cells[7])),
        Td(str(cells[8])),
        cls="tree-row position-row hidden",
        **attrs,
    )


def order_row(position_id: object, order: dict):
    cells = order["cells"]
    order_id = str(cells[0])
    return Tr(
        Td(tree_button(order_id, "order") if order["fills"] else ""),
        Td(f"Order {cells[0]}"),
        Td(str(cells[6])),
        Td(str(cells[2])),
        Td(str(cells[4])),
        Td(str(cells[7])),
        Td(""),
        Td(str(cells[9])),
        Td(""),
        Td(str(cells[5])),
        cls="tree-row order-row hidden",
        **{"data-parent-position": str(position_id), "data-order": order_id},
    )


def fill_row(order_id: object, fill: list):
    return Tr(
        Td(""),
        Td(f"Fill {fill[0]}"),
        Td(""),
        Td(str(fill[2])),
        Td(str(fill[3])),
        Td(str(fill[4])),
        Td(str(fill[6]), cls=pnl_class(fill[6])),
        Td(str(fill[7])),
        Td(""),
        Td(f"fee {fill[5]}"),
        cls="tree-row fill-row hidden",
        **{"data-parent-order": str(order_id)},
    )


def tree_button(target: str, level: str):
    return Button("›", type="button", cls="tree-toggle", **{"data-target": str(target), "data-level": level})


def sortable_table(table: dict):
    return Table(
        Thead(Tr(*[Th(column, **{"data-sort": index}) for index, column in enumerate(table["columns"])])),
        Tbody(*[Tr(*[table_cell(table, column, value) for column, value in zip(table["columns"], row, strict=True)]) for row in table["rows"]]),
        cls="data-table",
    )


def table_cell(table: dict, column: str, value: object):
    cls = ""
    if column in {"Net PnL", "Closed PnL", "PnL"}:
        cls = pnl_class(value)
    return Td(str(value), cls=cls)


def pnl_class(value: object):
    text = str(value).replace(",", "").replace("%", "").split(" ")[0]
    try:
        number = float(text)
        return "positive" if number >= 0 else "negative"
    except ValueError:
        return ""


def chart_script(result: dict) -> str:
    payload = json.dumps(result, separators=(",", ":")).replace("</", "<\\/")
    return f"""
const sweepChartPayload = {payload};
const sweepChartHost = document.getElementById("sweeprun-chart");
const sweepChartReadout = document.getElementById("chart-readout");
if (!window.echarts) {{
  sweepChartHost.textContent = "ECharts failed to load";
}} else {{
  const chart = echarts.init(sweepChartHost, undefined, {{ renderer: "canvas" }});
  function fmtPrice(value) {{
    return Number(value).toFixed(2);
  }}
  function fmtVolume(value) {{
    const number = Number(value);
    if (!Number.isFinite(number)) return "";
    if (Math.abs(number) >= 1e9) return `${{(number / 1e9).toFixed(2)}}B`;
    if (Math.abs(number) >= 1e6) return `${{(number / 1e6).toFixed(2)}}M`;
    if (Math.abs(number) >= 1e3) return `${{(number / 1e3).toFixed(2)}}K`;
    return number.toFixed(2);
  }}
  function readoutPart(key, value, cls = "") {{
    return `<span><span class="readout-key">${{key}}</span> <span class="readout-value ${{cls}}">${{value}}</span></span>`;
  }}
  function readoutIndex(value) {{
    const numeric = Number(value);
    if (Number.isInteger(numeric) && numeric >= 0 && numeric < sweepChartPayload.ohlcv.length) return numeric;
    const categoryIndex = sweepChartPayload.categories.indexOf(value);
    return categoryIndex >= 0 ? categoryIndex : sweepChartPayload.ohlcv.length - 1;
  }}
  function updateReadout(index) {{
    const readoutAt = readoutIndex(index);
    const candle = sweepChartPayload.ohlcv[readoutAt];
    if (!candle || !sweepChartReadout) return;
    const change = Number(candle.close) - Number(candle.open);
    const changePct = Number(candle.open) === 0 ? 0 : change / Number(candle.open) * 100;
    const changeCls = change >= 0 ? "is-up" : "is-down";
    sweepChartReadout.innerHTML = [
      `<span class="readout-symbol">${{sweepChartPayload.symbol}} ${{sweepChartPayload.interval}}</span>`,
      `<span>${{sweepChartPayload.categories[readoutAt] || ""}}</span>`,
      readoutPart("O", fmtPrice(candle.open)),
      readoutPart("H", fmtPrice(candle.high)),
      readoutPart("L", fmtPrice(candle.low)),
      readoutPart("C", fmtPrice(candle.close), changeCls),
      readoutPart("V", fmtVolume(candle.volume)),
      `<span class="${{changeCls}}">${{change >= 0 ? "+" : ""}}${{fmtPrice(change)}} (${{changePct.toFixed(2)}}%)</span>`
    ].join("");
  }}
  function hoveredIndex(params) {{
    const rows = Array.isArray(params) ? params : [params];
    const row = rows.find((item) => item && item.seriesType === "candlestick") || rows.find((item) => item && item.dataIndex != null);
    return row ? readoutIndex(row.dataIndex) : sweepChartPayload.ohlcv.length - 1;
  }}
  function volumeData() {{
    return sweepChartPayload.ohlcv.map((candle) => ({{
      value: Number(candle.volume) || 0,
      itemStyle: {{
        color: Number(candle.close) >= Number(candle.open)
          ? "rgba(34,197,94,0.58)"
          : "rgba(239,68,68,0.58)"
      }}
    }}));
  }}
  function volumeAxisMax() {{
    const maxVolume = Math.max(...sweepChartPayload.ohlcv.map((candle) => Number(candle.volume) || 0), 0);
    return maxVolume > 0 ? maxVolume / 0.85 : undefined;
  }}
  function primitiveLine(x1, y1, x2, y2, color) {{
    return {{
      type: "line",
      shape: {{ x1, y1, x2, y2 }},
      style: {{ stroke: color, lineWidth: 1.2, lineDash: [8, 5], opacity: 0.95 }},
      silent: true
    }};
  }}
  function buildPrimitiveSeries(primitives) {{
    return {{
      name: "executor",
      type: "custom",
      coordinateSystem: "cartesian2d",
      xAxisIndex: 0,
      yAxisIndex: 0,
      encode: {{ x: [0, 1], y: [2, 3] }},
      data: primitives,
      silent: true,
      tooltip: {{ show: false }},
      z: 8,
      renderItem: (params, api) => {{
        const item = primitives[params.dataIndex];
        if (item.type === "hline") {{
          const left = api.coord([item.value[0], item.value[2]]);
          const right = api.coord([item.value[1], item.value[2]]);
          return primitiveLine(left[0], left[1], right[0], right[1], item.color);
        }}
        const leftTop = api.coord([item.value[0], item.value[2]]);
        const rightTop = api.coord([item.value[1], item.value[2]]);
        const leftBottom = api.coord([item.value[0], item.value[3]]);
        const rightBottom = api.coord([item.value[1], item.value[3]]);
        return {{
          type: "group",
          children: [
            primitiveLine(leftTop[0], leftTop[1], rightTop[0], rightTop[1], item.top_color || item.color),
            primitiveLine(leftBottom[0], leftBottom[1], rightBottom[0], rightBottom[1], item.bottom_color || item.color),
            primitiveLine(leftTop[0], leftTop[1], leftBottom[0], leftBottom[1], item.color),
            primitiveLine(rightTop[0], rightTop[1], rightBottom[0], rightBottom[1], item.color)
          ]
        }};
      }}
    }};
  }}
  function buildCoreSeries() {{
    return [
      {{
        name: sweepChartPayload.symbol,
        type: "candlestick",
        data: sweepChartPayload.candles,
        itemStyle: {{
          color: "#22c55e",
          color0: "#ef4444",
          borderColor: "#22c55e",
          borderColor0: "#ef4444"
        }}
      }},
      {{
        name: "volume",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData(),
        barWidth: "60%",
        barMinWidth: 1,
        silent: true,
        tooltip: {{ show: false }},
        z: 1
      }}
    ];
  }}
  function buildIndicatorLineSeries(lines) {{
    return lines.map((line) => ({{
      name: line.name,
      type: "line",
      data: line.data,
      xAxisIndex: 0,
      yAxisIndex: 0,
      showSymbol: false,
      smooth: true,
      lineStyle: {{ width: 1.5, color: line.color }},
      itemStyle: {{ color: line.color }},
      connectNulls: false,
      silent: true,
      z: 9
    }}));
  }}
  function buildSignalerSeries(display) {{
    return [
      ...buildIndicatorLineSeries(display.lines),
      {{
        name: "signals",
        type: "scatter",
        data: display.markers,
        symbol: "diamond",
        symbolSize: 15,
        z: 13,
        tooltip: {{
          formatter: (item) => `${{item.data.name}}<br/>${{item.data.reason}}<br/>${{item.data.time}}<br/>price: ${{item.value[1]}}`
        }}
      }}
    ];
  }}
  function buildExecutorSeries(display) {{
    return [
      buildPrimitiveSeries(display.primitives),
      {{
        name: "entry/exit",
        type: "scatter",
        data: display.markers,
        symbol: "circle",
        symbolSize: 18,
        z: 12,
        tooltip: {{
          formatter: (item) => `${{item.data.name}}<br/>${{item.data.time}}<br/>price: ${{item.value[1]}}<br/>pnl: ${{item.data.pnl}}`
        }}
      }}
    ];
  }}
  chart.setOption({{
    backgroundColor: "transparent",
    animation: false,
    tooltip: {{
      trigger: "axis",
      confine: true,
      axisPointer: {{ type: "cross" }},
      formatter: (params) => {{
        const index = hoveredIndex(params);
        updateReadout(index);
        return sweepChartPayload.categories[index] || "";
      }}
    }},
    legend: {{ show: false }},
    grid: [
      {{ left: 64, right: 40, top: 14, height: 570 }},
      {{ left: 64, right: 40, top: 606, height: 240 }}
    ],
    xAxis: [
      {{ type: "category", data: sweepChartPayload.categories, scale: true, axisLabel: {{ show: false }}, axisTick: {{ show: false }} }},
      {{ type: "category", gridIndex: 1, data: sweepChartPayload.categories, scale: true, axisLabel: {{ color: "#9ca3af" }} }}
    ],
    yAxis: [
      {{ scale: true, axisLabel: {{ color: "#9ca3af" }}, splitLine: {{ lineStyle: {{ color: "#1f2937" }} }} }},
      {{
        gridIndex: 1,
        scale: true,
        max: volumeAxisMax(),
        axisLabel: {{ show: false }},
        axisTick: {{ show: false }},
        axisLine: {{ show: false }},
        splitLine: {{ show: false }}
      }}
    ],
    dataZoom: [
      {{ type: "inside", xAxisIndex: [0, 1] }},
      {{ type: "slider", xAxisIndex: [0, 1], height: 22, bottom: 24 }}
    ],
    series: [
      ...buildExecutorSeries(sweepChartPayload.executor_display),
      ...buildCoreSeries(),
      ...buildSignalerSeries(sweepChartPayload.indicators)
    ]
  }});
  updateReadout(sweepChartPayload.ohlcv.length - 1);
  chart.on("updateAxisPointer", (event) => {{
    const info = event.axesInfo && event.axesInfo[0];
    if (info && info.value != null) updateReadout(info.value);
  }});
  window.addEventListener("resize", () => chart.resize());
}}
"""


def tables_script() -> str:
    return """
document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab-button").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(`tab-${button.dataset.tab}`)?.classList.add("active");
  });
});

function setTreeOpen(button, open) {
  if (!button) return;
  button.classList.toggle("open", open);
}

function hideOrderTree(orderId) {
  document.querySelectorAll(`[data-parent-order="${orderId}"]`).forEach((row) => row.classList.add("hidden"));
}

function hidePositionTree(positionId) {
  document.querySelectorAll(`[data-parent-position="${positionId}"]`).forEach((row) => {
    row.classList.add("hidden");
    setTreeOpen(row.querySelector(".tree-toggle"), false);
    hideOrderTree(row.dataset.order);
  });
}

document.querySelectorAll(".tree-toggle").forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.dataset.target;
    const level = button.dataset.level;
    const opening = !button.classList.contains("open");
    setTreeOpen(button, opening);
    if (level === "bot") {
      document.querySelectorAll(`[data-parent-bot="${target}"]`).forEach((row) => {
        row.classList.toggle("hidden", !opening);
        if (!opening) {
          setTreeOpen(row.querySelector(".tree-toggle"), false);
          hidePositionTree(row.dataset.position);
        }
      });
    } else if (level === "position") {
      document.querySelectorAll(`[data-parent-position="${target}"]`).forEach((row) => {
        row.classList.toggle("hidden", !opening);
        if (!opening) {
          setTreeOpen(row.querySelector(".tree-toggle"), false);
          hideOrderTree(row.dataset.order);
        }
      });
    } else if (level === "order") {
      document.querySelectorAll(`[data-parent-order="${target}"]`).forEach((row) => row.classList.toggle("hidden", !opening));
    }
  });
});

document.querySelectorAll(".position-filter").forEach((input) => {
  input.addEventListener("input", () => {
    const term = input.value.trim().toLowerCase();
    document.querySelectorAll(".order-row,.fill-row").forEach((row) => row.classList.add("hidden"));
    document.querySelectorAll(".tree-toggle").forEach((button) => setTreeOpen(button, false));
    document.querySelectorAll(".bot-row").forEach((bot) => {
      const positions = Array.from(document.querySelectorAll(`[data-parent-bot="${bot.dataset.bot}"]`));
      if (!term) {
        bot.classList.remove("hidden");
        positions.forEach((row) => row.classList.add("hidden"));
        return;
      }
      let matched = false;
      positions.forEach((row) => {
        const hit = row.dataset.filterText.includes(term);
        row.classList.toggle("hidden", !hit);
        matched = matched || hit;
      });
      bot.classList.toggle("hidden", !matched);
      setTreeOpen(bot.querySelector(".tree-toggle"), matched);
    });
  });
});

document.querySelectorAll("th[data-position-sort]").forEach((header) => {
  header.addEventListener("click", () => {
    const column = Number(header.dataset.positionSort);
    const direction = header.dataset.direction === "asc" ? -1 : 1;
    header.dataset.direction = direction === 1 ? "asc" : "desc";
    document.querySelectorAll(".bot-row").forEach((bot) => {
      const tbody = bot.parentElement;
      let anchor = bot;
      const positions = Array.from(document.querySelectorAll(`[data-parent-bot="${bot.dataset.bot}"]`));
      positions.sort((left, right) => {
        const a = left.getAttribute(`data-sort-${column}`) || "";
        const b = right.getAttribute(`data-sort-${column}`) || "";
        const an = Number(a.replaceAll(",", ""));
        const bn = Number(b.replaceAll(",", ""));
        if (Number.isFinite(an) && Number.isFinite(bn)) return (an - bn) * direction;
        return a.localeCompare(b) * direction;
      });
      positions.forEach((position) => {
        tbody.insertBefore(position, anchor.nextSibling);
        anchor = position;
        const orders = Array.from(document.querySelectorAll(`[data-parent-position="${position.dataset.position}"]`));
        orders.forEach((order) => {
          tbody.insertBefore(order, anchor.nextSibling);
          anchor = order;
          document.querySelectorAll(`[data-parent-order="${order.dataset.order}"]`).forEach((fill) => {
            tbody.insertBefore(fill, anchor.nextSibling);
            anchor = fill;
          });
        });
      });
    });
  });
});

document.querySelectorAll(".data-table th[data-sort]").forEach((header) => {
  header.addEventListener("click", () => {
    const table = header.closest("table");
    const tbody = table.querySelector("tbody");
    const column = Number(header.dataset.sort);
    const direction = header.dataset.direction === "asc" ? -1 : 1;
    header.dataset.direction = direction === 1 ? "asc" : "desc";
    const rows = Array.from(tbody.querySelectorAll("tr"));
    rows.sort((left, right) => {
      const a = left.children[column].innerText.trim();
      const b = right.children[column].innerText.trim();
      const an = Number(a.replaceAll(",", ""));
      const bn = Number(b.replaceAll(",", ""));
      if (Number.isFinite(an) && Number.isFinite(bn)) return (an - bn) * direction;
      return a.localeCompare(b) * direction;
    });
    tbody.replaceChildren(...rows);
  });
});
"""
