# handoff

Last updated: 2026-07-05

## focus

Foundation evidence fixes after the adversarial review of sweeps, `SwTradeBot`,
account/ledger/order/fill persistence, and WebGUI sweep chart overlays.

## current status

- Latest committed/pushed evidence-fix state before the write-once hotfix:
  `58c798b Fix sweep evidence persistence`.
- Current working tree has the write-once `submit_ts` hotfix pending commit.
- Accepted user decision: sweep detail account rows should be stored at
  sweeprun level so each sweeprun can stand on its own.
- No active subagents remain.

## fixed

- `Order.submit_ts` is now set at order submit time in
  `TradingAccount.place_orders()`.
- `TradingAccount.place_orders()` now fails loud if an order already has
  `submit_ts`, so submit evidence is write-once.
- Sweeprun ledger persistence now writes `OrderRow.submit_ts` from
  `order.submit_ts`, not from fill times.
- Sweep account rows are now sweeprun-local:
  `sr_<sweeprun_id>_<account_name>`.
- Sweeprun-local `AccountRow.bot_id` is `None`; generated bot linkage remains
  on botrun, position, order, and fill rows.
- WebGUI sweep chart signal markers now come from persisted signal `EventRow`
  payloads.
- Regenerated indicator lines remain labeled `source = "regenerated"` and
  marker evidence is separately labeled `marker_source = "persisted_events"`.
- `wiki/design/state.md` documents sweeprun-local sweep account rows.
- `wiki/design/webgui.md` documents persisted signal markers for completed
  sweepruns.

## files changed

- `nuubot/account/account.py`
- `nuubot/account/order.py`
- `nuubot/sweeps/sweeprun.py`
- `nuubot/server/sweepmgr.py`
- `tests/test_swtradebot.py`
- `tests/test_sweep_metrics.py`
- `tests/test_sweep_trading.py`
- `wiki/design/state.md`
- `wiki/design/webgui.md`
- `audits/07-04-foundation-adversarial-audit-v1.md`
- `audits/07-05-foundation-evidence-fix-implementation-audit-v1.md`
- `HANDOFF.md`

## proof run

- `uv run python tests\test_sweep_metrics.py`
- `uv run python tests\test_swtradebot.py`
- `uv run python tests\test_sweep_trading.py`
- `uv run python -m compileall -q nuubot tests`
- `$env:PYTHONPATH='.'; Get-ChildItem tests\test_*.py | Sort-Object Name | ForEach-Object { uv run python $_.FullName }`
- `git diff --check`
- Restarted stale server on port `5002`, started current-code server, and ran
  sweep `55` through the HTTP API.
- `bash ./report.sh 55`
- SQLite proof on `workspace/db/sweep_55.db`.
- `GET /sweeps/55/runs/1` chart payload check.

Result:

- Focused tests passed.
- Full compile passed.
- All `tests/test_*.py` passed.
- `git diff --check` passed with LF/CRLF warnings only.
- Read-only implementation audit recheck passed.
- Current-code server is running on port `5002`, PID `11332`.
- Sweep `55` completed `36/36` with `0` failed.
- `workspace/db/sweep_55.db` proof:
  - `submit_ts_zero|0`
  - `account_count|36`
  - `bad_account_bot_id|0`
- Chart route proof:
  - `"marker_source":"persisted_events"`
  - `"source":"regenerated"`

## proof not run

- No WebGUI Playwright/screenshot proof yet.
- No live Hyperliquid proof.

## deferred

- Strategy modules still return renderer-shaped chart dictionaries.
- `SweepManager` still owns too much WebGUI presentation assembly.
- Custom WebGUI table JavaScript still needs explicit approval/documentation or
  removal.
- `HANDOFF2.md` cleanup remains pending.

## blockers

None known for the accepted evidence-fix scope.

## next action

Next cleanup slice: decide and fix the remaining WebGUI architecture findings:
renderer-shaped chart dictionaries, `SweepManager` presentation assembly,
custom table JavaScript policy, and stale `HANDOFF2.md`.
