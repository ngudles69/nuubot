# handoff2

Last updated: 2026-07-04

## purpose

This is the WebGUI handoff for `D:\rust\nuubot_webgui`.

If the user asks to read `HANDOFF2.md`, use this file to resume the WebGUI
workstream: sweep result browsing, sweeprun charts, signaler overlays, and
trade/debug visualization.

## focus

Build a WebGUI chart that explains why a sweeprun traded:

- candles
- actual signaler-calculated columns
- actual signal rows
- bot entry/exit rings
- bot entry-to-exit dashed box

The goal is visual strategy debugging:

- why did the bot enter here?
- was entry too early or too late?
- did the signal happen on the same bar as the bot entry?
- why did this trade lose?
- is the indicator state wrong or misleading?

## current status

- Server is running at `http://127.0.0.1:5002`.
- WebGUI now reads sweep DBs from `D:/rust/nuubot/workspace/db`.
- `/sweeps` lists existing sweep DBs.
- `/sweeps/53` shows sweep detail and 36 sweepruns.
- `/sweeps/53/runs/1` shows a first ECharts candlestick chart.
- Current chart uses candles, regenerated EMA fast/slow lines, regenerated
  crossover signal markers, and executor-owned display primitives.
- TradeBot chart display currently emits entry/exit rings plus standard
  `dashbox` and `hline` primitives. The dashbox uses persisted TP/SL trigger
  order prices as the upper/lower bounds when available.
- OHLCV is shown in a TradingView-style readout above the chart. The ECharts
  hover tooltip is timestamp-only, not OHLCV.
- The sweeprun chart page has dense summary cards above the chart:
  - Info
  - Performance
  - Ratios
  - PnL / Win Rate
  - Wins
  - Losses
- The chart height is 936px. The volume pane height is 240px.
- The chart page does not show a Back button.
- The chart readout and legend share one row:
  - OHLCV readout left
  - custom legend right
- A volume pane is shown under the price chart, synced to the same zoom.
  The volume y-axis labels/ticks/line are hidden, matching the
  `nuutrader2-web` pattern, and the pane is scaled tall enough to read.
- Candlestick body borders match the body color, so candles do not show a
  bright separate outline; wicks/tails remain visible.
- Bot window boxes use the shared `dashbox` primitive, not dotted lines.
- EMA signal diamonds are offset 2% of candle close away from candle highs/lows.
- Signaler and executor values in the Info card use browser title tooltips for
  their parameters.
- Below the chart, tabs show sortable tables for:
  - Bots
  - Orders
  - Fills
  - Config
- The `Bots` tab is hierarchical:
  - botrun rows
  - chevron opens positions for that bot
  - position chevron opens orders sorted by submit time descending
  - order chevron opens fills sorted by fill time descending
- Position rows default to closed time descending inside each botrun.
- Position rows can be filtered and sorted by visible position columns.
- Flat `Orders` and `Fills` tabs remain.
- Position table `Net PnL` cells are green/red.
- Top-card coloring:
  - PnL values are green/red.
  - Max DD is red.
  - Wins count is green.
  - Losses count is red.
- Info card shows `Bots`, which is currently the tradebot cycle/bot count.
- PnL displays actual net PnL value plus percent.
- EMA overlay generation belongs to `SwEmacross.chart_display(...)`, not
  `SweepManager`.
- Entry/exit markers are rings, not filled circles.
- EMA cross signal markers are candle-relative: long/bullish below candle low,
  short/bearish above candle high.
- TradeBot boxes use persisted TP/SL trigger prices as upper/lower bounds when
  both are available; otherwise they fall back to entry/exit prices.
- Executor chart display should stay executor-owned. Future grid hedge, DCA,
  pyramid, and other executors should return generic primitives such as
  `dashbox`, `hline`, and markers rather than hardcoding WebGUI renderer logic.
- EMA overlays are regenerated/current-code preview data because sweep 53 did
  not save signaler frames.

## files changed

- `workspace/config/config.toml`
- `nuubot/config/config.py`
- `nuubot/server/sweepmgr.py`
- `nuubot/webgui/layout.py`
- `nuubot/webgui/sweeps/list.py`
- `HANDOFF2.md`

## decisions made

- Keep code/file changes inside `D:\rust\nuubot_webgui`.
- `D:\rust\nuubot\workspace\**` is valid reference/test/runtime data.
- Use `D:\rust\nuutrader2-web` as the ECharts behavior reference, not as a
  wholesale copy source.
- Keep this WebGUI as FastHTML plus direct ECharts for now. Do not add a React
  build system.
- For TradeBot, draw the bot window as:
  - left edge: entry timestamp
  - right edge: exit timestamp
  - top/bottom: max/min of entry price and exit price
  - dashed line box
- Entry and exit should be rings, not filled circles.
- Future chart overlays must come from the actual signaler state used by the
  sweeprun when available.
- Do not pretend regenerated indicators are exact original proof. If old sweeps
  lack saved signaler frames, either show no indicator overlay or label it as
  regenerated/current-code.

## signaler chart-display direction

When a signaler is created, it should also define how it appears on the chart.

Each signaler needs a chart display function or method that returns generic
chart-display data for WebGUI. WebGUI should call the signaler display hook and
render the returned lines, markers, and triggers without knowing signaler
internals.

Examples:

- `SwEmacross.chart_display(...)` should add:
  - fast EMA line
  - slow EMA line
  - crossover markers
  - `enter_long`
  - `enter_short`
  - `exit_long`
  - `exit_short`
  - reason labels
- A future MACD signaler `chart_display(...)` should add:
  - MACD line
  - signal line
  - histogram if wanted
  - trigger markers
  - entry/exit signal markers

The signaler owns what to show. WebGUI owns rendering the generic chart display
payload.

Current code direction:

- `nuubot/sweeps/signalers/signaler.py` exposes generic `chart_display(...)`.
- `nuubot/sweeps/signalers/swemacross.py` owns the EMA line and crossover
  marker payload.
- `SweepManager` should only pass sweeprun config plus a candle loader into
  the generic signaler chart-display hook.

## persistence direction

For `savedb=true`, sweeps should persist:

- actual calculated signaler columns
- actual signal decision rows

The signaler must save this data per sweeprun. Different sweepruns can use
different signaler settings, for example `SwEmacross` fast/slow EMA periods.
The chart must display the exact columns and signals for that sweeprun's
settings, not a shared/global signaler output.

For `SwEmacross`, persist at least:

- `ts_ms`
- `open`
- `high`
- `low`
- `close`
- `volume`
- fast EMA
- slow EMA
- `enter_long`
- `enter_short`
- `exit_long`
- `exit_short`
- `reason`

Recommended storage shape:

- generic `signaler_frame` table or artifact per sweep DB
- keyed by `sweep_id`, `sweeprun_id`, `signaler`, `dataset`, `ts_ms`
- compact `data_json` for the signaler-declared display/debug columns

## proof run

- `uv run python -m compileall -q nuubot tests`
- `$env:PYTHONPATH='.'; uv run python tests\test_sweep_metrics.py`
- `$env:PYTHONPATH='.'; uv run python tests\test_swemacross.py`
- manager probe:
  - sweep 53 detail returned 36 sweepruns
  - sweeprun 53/1 returned 4,344 candles and 272 markers
- HTTP proof:
  - `/status`
  - `/sweeps`
  - `/sweeps/53`
  - `/sweeps/53/runs/1`
- Playwright screenshots:
  - `tests/ss/sweep-53-detail.png`
  - `tests/ss/sweeprun-53-1-chart.png`
  - `tests/ss/sweeprun-53-1-ema-fixed.png`
  - `tests/ss/sweeprun-53-1-readout.png`
  - `tests/ss/sweeprun-53-1-dense-full-v2.png`
  - `tests/ss/sweeprun-53-1-volume-full.png`
  - `tests/ss/sweeprun-53-1-volume-candles-full.png`
  - `tests/ss/sweeprun-53-1-volume-double-pnl-full.png`
  - `tests/ss/sweeprun-53-1-bots-tree-full.png`
  - `tests/ss/sweeprun-53-1-bots-expanded-full.png`
  - `tests/ss/sweeprun-53-1-marker-spacing-05-full.png`
  - `tests/ss/sweeprun-53-1-marker-spacing-02-full.png`
  - `tests/ss/sweeprun-53-1-executor-primitives-full.png`
- Browser proof for `/sweeps/53/runs/1`:
  - top readout showed `BTCUSDT 1h | 2025-04-09 08:00 | O 77694.12 | H 77880.00 | L 77085.00 | C 77304.35 | V 1.26K | -389.77 (-0.50%)`
  - absolute tooltip text was only `2025-04-09 08:00`
  - full-size 1920x1080 Playwright screenshot showed 5 summary cards,
    816px chart, and 520px contained table area
  - later full-size 1920x1080 Playwright screenshot showed 6 summary cards,
    shared readout/legend row, volume pane, and no Back button
  - latest Playwright option check confirmed:
    - 2 ECharts grids
    - volume y-axis label hidden
    - volume y-axis line hidden
    - volume grid height `120`
    - candle border colors match candle body colors
  - latest Playwright screenshot/probe confirmed:
    - summary order `Info`, `Performance`, `Ratios`, `PnL / Win Rate`,
      `Wins`, `Losses`
    - Info includes `Bots 136`
    - PnL shows `-15,378.60 (-17.78%)`
    - volume grid height `240`
    - chart host height `936`
    - position `Net PnL` cells have green/red classes
  - latest Playwright tree proof confirmed:
    - tabs `Bots (136)`, `Orders (409)`, `Fills (272)`, `Config`
    - bot expand showed position rows
    - position expand showed order rows
    - order expand showed fill rows
    - position filter matched `take_profit`
    - position sort changed first visible PnL
    - Config tab rendered sweeprun config JSON
  - tab switch proof:
    - Orders tab first ID `100000100103`
    - Fills tab first ID `10000010010101`
    - Fills price sort first value `76,181.13`

## proof not run

- No proof yet for persisted signaler frames.
- No proof yet for EMA line overlays from saved columns. Current EMA overlay is
  regenerated from candles and config only.
- No proof yet for MACD or any non-EMA signaler display.

## blockers

None for the current WebGUI chart baseline.

Next design/implementation choice:

- exact persistence shape for signaler frames: table rows vs per-sweeprun
  artifact blob.

## next action

Design and implement persisted signaler frame output for `SwEmacross` when
`savedb=true`, then switch WebGUI EMA overlays from regenerated preview data to
saved sweeprun-specific signaler data when available.

Persisted `SwEmacross` output must be keyed by `sweeprun_id`, because fast/slow
EMA settings vary by sweeprun.
