---
title: webgui design
created: 2026-06-29
updated: 2026-07-04
type: wiki
status: active
tags: [design, server, webgui, fasthtml]
---

# webgui design

## purpose

WebGUI is the operator display and command-control surface.

It is part of Server, not a peer application.

## package

```text
nuubot/server/__main__.py
nuubot/server/api.py
nuubot/server/server.py
nuubot/server/sweepmgr.py
nuubot/server/webgui.py
nuubot/webgui/app.py
nuubot/webgui/layout.py
nuubot/webgui/sweeps/create.py
nuubot/webgui/sweeps/list.py
```

Start it with:

```bash
./server.sh
```

Server does not use Uvicorn reload by default. Stop and start the server after
code changes. Use `--reload` only when explicitly needed.

Repo-root helpers:

```bash
./server.sh
```

## rules

- Use FastHTML with MonsterUI standard components.
- Keep the first layout simple: header bar, sidebar, main content.
- Prefer server-rendered pages, normal forms, POST/redirect, and MonsterUI
  `Toast(...)`.
- HTMX attributes are allowed for standard request indicators, server-rendered
  swaps, and conditional 2-second polling while sweeps are active. Do not add
  hand-written browser JavaScript for this.
- Do not add custom browser JavaScript for tables, polling, toasts, file
  dialogs, or command actions unless explicitly approved.
- User-edited bot/sweep templates stay as TOML.
- API submit body for create flows may be raw TOML text.
- DB storage uses canonical JSON after manager/domain validation.
- Sweep run progress comes from SQLite rows, not worker memory.
- Keep route handlers small.
- WebGUI display code may build HTML.
- WebGUI owns HTML page shape, toast shape, and redirect behavior.
- Browser pages use FastHTML-style routes without `.html`.
- API routes use `/api/...` URLs.
- App behavior must go through Server/BotManager/SweepManager.
- Do not add a separate frontend build system.
- Do not put WebGUI in a peer package.
- `nuubot/server/webgui.py` is the Server-facing GUI entry.
- `nuubot/webgui/**` owns the actual FastHTML display code.

## chart display standard

WebGUI owns the chart display standard.

Signalers and executors help construct chart displays, but they do not own
ECharts options, FastHTML page shape, browser JavaScript, colors, line widths,
legend rendering, or tooltip behavior.

If a signaler and executor both return an empty chart display, the page shows
only the core chart:

- candlesticks
- volume
- OHLCV readout
- crosshair and timestamp tooltip
- default chart controls

The page flow is:

```text
core chart data -> WebGUI
signaler.chart_display(...) -> ChartDisplay
executor.chart_display(...) -> ChartDisplay
WebGUI combines displays -> ECharts payload
```

Do not pass a mutable chart object into signalers or executors. They return
approved display objects. This keeps strategy code independent of ECharts and
makes display output testable without a browser.

### display object

Use one boring display shape:

```python
@dataclass
class ChartDisplay:
    line_list: list[ChartLine]
    box_list: list[ChartBox]
    marker_list: list[ChartMarker]
```

WebGUI may flatten this into the current JSON payload shape before sending it
to the browser.

### approved constructors

Signalers and executors should use WebGUI-approved constructors instead of
crafting raw dictionaries or raw ECharts objects.

Initial constructors:

```python
plot(...)
hline(...)
vline(...)
box(...)
marker_signal_entry(...)
marker_signal_exit(...)
marker_executor_entry(...)
marker_executor_exit(...)
```

Constructor intent:

- `plot(...)`: indicator series such as EMA, SMA, MACD, RSI, Guppy lines.
- `hline(...)`: horizontal level over a time range, fixed pane level, entry
  price, exit price, TP, SL, RSI 30/70, MACD zero.
- `vline(...)`: timestamp boundary or event marker.
- `box(...)`: time and price window such as active bot range, TP/SL zone,
  volume-profile region, grid range, or risk window.
- `marker_signal_entry(...)`: signaler entry event.
- `marker_signal_exit(...)`: signaler exit event.
- `marker_executor_entry(...)`: actual executor entry transaction.
- `marker_executor_exit(...)`: actual executor exit transaction.

Future marker constructors may be added under the same prefix pattern, for
example:

```python
marker_executor_rebalance(...)
marker_executor_liquidation(...)
marker_signal_warning(...)
marker_data_gap(...)
marker_risk_block(...)
```

### ownership

WebGUI owns:

- `ChartDisplay`, `ChartLine`, `ChartBox`, `ChartMarker`
- approved constructors
- primitive validation
- ECharts rendering
- colors and themes
- marker shape
- dash style
- legend labels
- default visibility
- pane placement
- tooltip/readout behavior

Signalers own:

- which indicator lines exist
- which fixed levels exist
- where signal entry/exit markers are placed
- signal reasons and labels

Executors own:

- which bot windows exist
- which TP/SL, level, entry, exit, DCA, pyramid, or grid lines exist
- where actual transaction entry/exit markers are placed
- executor reasons and labels

### examples

EMA cross signaler:

```python
return ChartDisplay(
    line_list=[
        plot("EMA 5", ema_fast),
        plot("EMA 20", ema_slow),
    ],
    box_list=[],
    marker_list=[
        marker_signal_entry(index, price, side="long", reason="ema_cross_up"),
        marker_signal_exit(index, price, side="long", reason="ema_cross_down"),
    ],
)
```

Guppy signaler:

```python
return ChartDisplay(
    line_list=[
        plot("EMA 3", ema3, group="guppy_fast"),
        plot("EMA 5", ema5, group="guppy_fast"),
        plot("EMA 8", ema8, group="guppy_fast"),
        plot("EMA 10", ema10, group="guppy_fast"),
        plot("EMA 12", ema12, group="guppy_fast"),
        plot("EMA 15", ema15, group="guppy_fast"),
        plot("EMA 30", ema30, group="guppy_slow"),
        plot("EMA 35", ema35, group="guppy_slow"),
        plot("EMA 40", ema40, group="guppy_slow"),
        plot("EMA 45", ema45, group="guppy_slow"),
        plot("EMA 50", ema50, group="guppy_slow"),
        plot("EMA 60", ema60, group="guppy_slow"),
    ],
    box_list=[],
    marker_list=[],
)
```

RSI signaler:

```python
return ChartDisplay(
    line_list=[
        plot("RSI", rsi, pane="rsi"),
        hline(70, title="RSI upper", pane="rsi"),
        hline(30, title="RSI lower", pane="rsi"),
    ],
    box_list=[],
    marker_list=[],
)
```

MACD signaler:

```python
return ChartDisplay(
    line_list=[
        plot("MACD", macd, pane="macd"),
        plot("Signal", signal, pane="macd"),
        hline(0, title="Zero", pane="macd"),
    ],
    box_list=[],
    marker_list=[],
)
```

TradeBot executor:

```python
return ChartDisplay(
    line_list=[
        hline(start, end, entry_price, role="entry_price"),
        hline(start, end, exit_price, role="exit_price"),
    ],
    box_list=[
        box(start, end, upper=tp, lower=sl, role="tp_sl_window"),
    ],
    marker_list=[
        marker_executor_entry(start, entry_price, side="long"),
        marker_executor_exit(end, exit_price, side="long", reason="take_profit"),
    ],
)
```

Future grid hedge executor:

```python
return ChartDisplay(
    line_list=[
        hline(start, end, upper_bound, role="grid_upper"),
        hline(start, end, lower_bound, role="grid_lower"),
        hline(start, end, level_price, role="grid_level"),
    ],
    box_list=[
        box(start, end, upper=upper_bound, lower=lower_bound, role="grid_range"),
    ],
    marker_list=[
        marker_executor_entry(index, price, side="long"),
        marker_executor_exit(index, price, side="long", reason="level_exit"),
    ],
)
```

### rule

If a signaler or executor needs a display shape that the approved constructors
cannot express, add one standard primitive to WebGUI first. Do not let one
strategy return arbitrary renderer-specific chart config.

## first routes

```text
GET /        dashboard
GET /bots    bot control surface
GET/POST /bots/{bot_id}/archive
GET/POST /bots/{bot_id}/unarchive
GET /sweeps  sweep list
GET /sweeps/archived  archived sweep list
GET /sweeps/create  create sweep form
GET /sweeps/{sweep_id}/metrics  sweep metrics JSON
GET /sweeps/archived/{sweep_id}/metrics  archived sweep metrics JSON
GET/POST /sweeps/{sweep_id}/archive
GET/POST /sweeps/{sweep_id}/unarchive
GET /server  server status surface
GET /user    user settings placeholder
GET /ping    plain liveness
GET /status  JSON status
```
