# foundation evidence fix implementation audit

Date: 2026-07-05

Scope: current working tree changes for order submit timestamps,
sweeprun-local account rows, and WebGUI chart signal markers from persisted
events.

Result: PASS

## audit result

Prior implementation-audit failure was resolved.

Evidence:

- `nuubot/server/sweepmgr.py` keeps regenerated indicator line source and adds
  `marker_source = "persisted_events"` for persisted signal markers.
- `tests/test_sweep_metrics.py` has a DB-backed `sweeprun_chart()` regression
  asserting `source == "regenerated"`, `marker_source == "persisted_events"`,
  and marker reason comes from persisted event data.
- `nuubot/account/account.py` sets `Order.submit_ts` at submit time.
- `nuubot/sweeps/sweeprun.py` persists `order.submit_ts`.
- `nuubot/sweeps/sweeprun.py` writes sweeprun-local account ids:
  `sr_<sweeprun_id>_<account>`, with `AccountRow.bot_id = None`.
- `wiki/design/state.md` and `wiki/design/webgui.md` document the accepted
  account and persisted-marker rules.

## proof checked

- `uv run python -m compileall -q nuubot tests`
- `uv run python -m tests.test_sweep_metrics`
- `uv run python -m tests.test_swtradebot`
- all `tests/test_*.py`
- `git diff --check` passed with LF/CRLF warnings only.

## remaining proof gaps

- No WebGUI screenshot/browser proof for the chart path.

## additional proof

- Restarted stale server on port `5002` and ran a fresh current-code server.
- Created and ran sweep `55` through the HTTP API.
- Sweep `55` completed `36/36` with `0` failed.
- SQLite proof on `workspace/db/sweep_55.db`:
  - `submit_ts_zero|0`
  - `account_count|36`
  - `bad_account_bot_id|0`
- WebGUI chart route proof:
  - `GET /sweeps/55/runs/1` contains
    `"marker_source":"persisted_events"`.
  - The same payload keeps `"source":"regenerated"`.

## disposition

No blockers remain in the accepted evidence-fix scope.
