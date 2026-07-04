# foundation adversarial audit

Date: 2026-07-04

Scope: commits `1ad3e4e^..HEAD`; sweep, sweeprun, signaler, `SwEmacross`,
`SwTradeBot`, account/ledger/position/order/fill simulator path, WebGUI sweep
charts, tests, and wiki alignment.

Result: FAIL

## findings

### P1 - order submit timestamps are wrong for unfilled/canceled orders

Evidence:

- `nuubot/sweeps/sweeprun.py:531` persists `submit_ts=min(fill_times) if fill_times else 0`.
- `nuubot/account/order.py:43` has no submit timestamp field on `Order`.
- Read-only DB check on `workspace/db/sweep_54.db`:
  - `select count(*) from "order" where submit_ts=0` -> `4805`.

Why it matters:

Canceled TP/SL orders and other unfilled orders become timestamp `0`, which
breaks chart tables, event ordering, and trading evidence.

Violated standard:

- `wiki/design/state.md:268-274`: orders are intent and exchange evidence; do
  not silently overwrite trading evidence.

Fix direction:

Store submit timestamp on `Order` at submit/intent time, set it in
`TradingAccount.place_orders()` or before submit, and persist that value. Add a
regression that canceled trigger orders keep their real submit timestamp.

### P1 - chart signal overlays are regenerated, not run truth

Evidence:

- `nuubot/server/sweepmgr.py:238` calls `signaler_chart_display(...)` from
  stored config and candles.
- `nuubot/sweeps/signalers/swemacross.py:198-222` recomputes EMA/signals and
  returns `source = "regenerated"`.
- `nuubot/sweeps/sweeprun.py:397-407` already persists actual signal events.
- Read-only DB check from reviewers: `workspace/db/sweep_54.db` has `6544`
  persisted signal events, but chart markers do not use them.

Why it matters:

The WebGUI can display current-code signals, not the signals that actually
caused the recorded run. After code or data changes, the chart can lie.

Violated standard:

- `AGENTS.md`: evidence claims need real artifacts.
- `wiki/design/webgui.md:90-101`: chart display should preserve strategy
  boundaries and be testable.

Fix direction:

Build signal markers from persisted `EventRow` signal events for the
sweeprun. If indicator lines stay regenerated, label them as preview/current
calculation or persist run-derived indicator display data when `savedb=true`.

### P2 - account row identity is ambiguous across botruns

Evidence:

- `nuubot/sweeps/sweeprun.py:463-469` builds a generated `bot_id`, then
  `upsert`s `AccountRow(acct_id=acct_id, bot_id=bot_id, ...)`.
- `nuubot/datastore/schemas.py:109` makes `acct_id` the primary key.
- Read-only DB check on `workspace/db/sweep_54.db`:
  - `account_count = 1`
  - `botrun_count = 4784`
  - `distinct_position_bot_id = 4784`
  - account row: `sgrid|6000001|sgrid`

Why it matters:

Thousands of generated botruns share one account row. Depending on upsert
behavior, that row represents only one botrun or silently changes. Either way,
the account-to-bot evidence is not trustworthy.

Violated standard:

- `wiki/design/state.md:155-160`: account rows key accounts; in sweep DB,
  `account.bot_id` can link the account to a generated bot.
- `wiki/design/state.md:273`: do not silently overwrite trading evidence.

Fix direction:

Choose one meaning. Either make the account row sweep/account-level with
`bot_id=None`, or create per-botrun/per-generated-bot account identities. Do
not mutate one `acct_id` row across many botruns.

### P2 - strategy modules return renderer-shaped chart dictionaries

Evidence:

- `wiki/design/webgui.md:103-121` defines `ChartDisplay` and says strategy
  modules should use approved constructors, not raw dictionaries or raw
  renderer objects.
- `nuubot/sweeps/signalers/swemacross.py:206-249` returns raw line/marker dicts
  and includes ECharts-shaped `itemStyle`.
- `nuubot/sweeps/executors/swtradebot.py:135-140` returns raw `markers` and
  `primitives`.
- `nuubot/sweeps/executors/swtradebot.py:355-412` builds renderer-ish
  `dashbox`/`hline` dictionaries with colors.

Why it matters:

Renderer policy leaks into signalers/executors. The next signaler/executor will
copy raw display dicts instead of a stable WebGUI-owned display contract.

Violated standard:

- `wiki/design/webgui.md:120-121`
- `wiki/design/webgui.md:162-171`

Fix direction:

Put minimal `ChartDisplay` primitives/constructors under `nuubot/webgui/**`.
Signalers/executors return approved display objects only; WebGUI flattens them
to ECharts.

### P2 - SweepManager owns too much WebGUI presentation shape

Evidence:

- `nuubot/server/sweepmgr.py:219-258` builds full chart payloads.
- `nuubot/server/sweepmgr.py:520-594` builds summary groups with display
  labels, tones, and formatting.
- `nuubot/server/sweepmgr.py:596-734` builds UI table/tree rows.

Why it matters:

`SweepManager` is becoming a WebGUI read-model/presentation layer. That blurs
control-plane ownership and makes future CLI/API callers inherit UI-shaped
payloads.

Violated standard:

- `wiki/design/sweepmanager.md:14-26`: SweepManager owns control-plane
  operations and result summary reads.
- `wiki/design/webgui.md:63-64`: WebGUI owns HTML page shape and display code.

Fix direction:

Keep `SweepManager` returning raw rows/metrics needed by callers. Move chart,
summary, and table presentation assembly into `nuubot/webgui/**` or a
WebGUI-owned read-model module.

### P2 - WebGUI table behavior uses custom browser JS against wiki rules

Evidence:

- `nuubot/webgui/sweeps/list.py:352-354` injects ECharts plus custom chart and
  table scripts.
- `nuubot/webgui/sweeps/list.py:830-958` implements tabs, tree expansion,
  filtering, and sorting in browser JS.
- `wiki/design/webgui.md:53-57` allows HTMX for swaps/polling and says not to
  add custom browser JavaScript for tables unless explicitly approved.

Why it matters:

This may be acceptable for a dense operator chart page, but it is currently a
wiki violation. Leaving it unrecorded makes the next WebGUI slice copy the same
pattern by accident.

Fix direction:

Either remove the table JS in favor of simpler/server-rendered behavior, or
explicitly approve this exception and update `wiki/design/webgui.md` with the
allowed scope.

### P3 - stale `HANDOFF2.md` landed on `main`

Evidence:

- `HANDOFF2.md` is from the `D:\rust\nuubot_webgui` stream and references
  port `5002`.
- `HANDOFF.md` is the canonical current restart state for this checkout.

Why it matters:

Two handoff files create restart ambiguity. Handoff is not durable design
canon.

Violated standard:

- `AGENTS.md`: `wiki/**` is durable truth; handoff is current restart state.

Fix direction:

Collapse current restart state into `HANDOFF.md`; keep durable WebGUI facts in
`wiki/design/webgui.md`; delete/archive stale `HANDOFF2.md` when approved.

## proof checked

- `uv run python -m compileall -q nuubot tests`
- `$env:PYTHONPATH='.'; Get-ChildItem tests\test_*.py | Sort-Object Name | ForEach-Object { uv run python $_.FullName }`
- `git diff --check`
- Read-only SQLite check on `workspace/db/sweep_54.db`:
  - `account_count|1`
  - `botrun_count|4784`
  - `distinct_position_bot_id|4784`
  - `orders_submit_zero|4805`
  - `sgrid|6000001|sgrid`

## proof missing

- No fresh post-merge real sweep after `3ce1c25`.
- No WebGUI screenshot/chart overlay proof after `3ce1c25`.
- No server/API proof for `/sweeps/{id}/runs/{sweeprun_id}`.
- No live Hyperliquid proof.
- No rejected-order proof.
- No regression for persisted order submit timestamps on canceled trigger
  orders.
- No regression proving chart markers come from persisted signal events.

## bloat check

No fake server, fake simulator balance, fake runner, or mock-only sweep path was
found in this pass.

Found bloat/drift: raw chart dictionaries outside WebGUI, WebGUI presentation
assembly inside `SweepManager`, custom browser JS for tables, and stale
`HANDOFF2.md`.

Found correctness risks: corrupted order timestamps, ambiguous account-row
identity, and chart markers regenerated from current code instead of run
evidence.

## fix disposition 2026-07-05

Fixed in the correctness slice:

- P1 order submit timestamps:
  - `Order.submit_ts` is set by `TradingAccount.place_orders()`.
  - `Sweeprun._save_botrun_ledger()` persists `order.submit_ts`.
  - Regression added in `tests/test_swtradebot.py`.
- P1 chart signal markers:
  - `SweepManager.sweeprun_chart()` replaces regenerated signal markers with
    markers built from persisted `EventRow` signal payloads.
  - Indicator line source remains `regenerated`; marker source is separately
    labeled `persisted_events`.
  - Regression added in `tests/test_sweep_metrics.py`.
- P2 account row identity:
  - Sweep detail account rows are now sweeprun-local:
    `sr_<sweeprun_id>_<account_name>`.
  - `AccountRow.bot_id` is `None`; generated bot linkage stays on botrun,
    position, order, and fill rows.
  - `wiki/design/state.md` documents the canonical sweep account row meaning.

Proof after fixes:

- `uv run python tests\test_sweep_metrics.py`
- `uv run python tests\test_swtradebot.py`
- `uv run python -m compileall -q nuubot tests`
- `$env:PYTHONPATH='.'; Get-ChildItem tests\test_*.py | Sort-Object Name | ForEach-Object { uv run python $_.FullName }`
- `git diff --check` passed with LF/CRLF warnings only.

Deferred from this slice:

- Strategy modules still return renderer-shaped chart dictionaries.
- `SweepManager` still owns too much WebGUI presentation assembly.
- Custom WebGUI table JavaScript still needs explicit approval/documentation or
  removal.
- `HANDOFF2.md` cleanup remains pending.
- No fresh post-fix real sweep DB or Playwright screenshot proof has been run
  yet.

Additional real-path proof:

- Restarted stale server on port `5002` and ran a fresh current-code server.
- Created and ran sweep `55` through the HTTP API:
  - `POST /api/sweeps`
  - `POST /api/sweeps/55/run`
  - `GET /api/sweeps/55/metrics`
- Sweep `55` completed `36/36` with `0` failed.
- `bash ./report.sh 55` passed.
- SQLite proof on `workspace/db/sweep_55.db`:
  - `submit_ts_zero|0`
  - `account_count|36`
  - `bad_account_bot_id|0`
  - account ids use `sr_<sweeprun_id>_<account_name>`, for example
    `sr_10_sgrid`.
- WebGUI chart proof:
  - `GET /sweeps/55/runs/1` contains
    `"marker_source":"persisted_events"`.
  - The same payload keeps `"source":"regenerated"` for indicator lines.
