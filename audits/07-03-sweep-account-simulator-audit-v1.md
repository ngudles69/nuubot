# sweep account simulator audit v1

Audit target: `911b6af Add sweep account simulator ledger`

Compared against: `24ba423 Update handoff for signaler ownership`

Status: FAIL

## findings

High: `nuubot/sweeps/executors/swtradebot.py:97` and
`nuubot/sweeps/executors/swtradebot.py:160` close before recon. If TP/SL fills
inside the throttle window, `stop()` or signal-close cancels the ledger trigger
orders and submits a cleanup close before pulling simulator/exchange history.
The audit reproduced this: simulator had entry + TP fill, but ledger saved TP as
canceled and added a separate close order.

Required fix: before any manual cleanup close, run
`account.recon(now_ms, "pre_close")`, call `_sync_position()`, and return if the
position is already closed. Add a test for "trigger filled after last recon,
then stop".

Medium: `nuubot/sweeps/sweeprun.py:263`, `nuubot/sweeps/sweep.py:244`, and
`nuubot/sweep.py:40` label synthetic tick count as `bars`. That already confused
comparison with sweep 28.

Required fix: track/report `ticks_processed` or `events_processed`; optionally
also track loaded 1m bars separately. Do not call `37,843,200` bars.

Medium: `nuubot/exchange/simulator.py:133` returns fake zero balance through
public `TradingAccount.balance()`. This is a half-wired account API.

Required fix: either compute simulator equity/available from configured starting
balance, fills, and fees, or fail loud with `NotImplementedError` until balance
is actually used.

Low: `nuubot/sweeps/executors/executor.py:21` accepts `sweeprun=None` and uses
`getattr(..., default)` for simulator config. That is an unneeded fallback now
that `SweeprunSettings` owns defaults.

Required fix: make `sweeprun` required and access fields directly.

Low: `nuubot/account/ledger.py:83` and `nuubot/account/ledger.py:87` duplicate
fill recording via `record_fills()` and `record_fills_count()`. The second name
describes return plumbing, not intent.

Required fix: keep one `record_fills()` that returns changed positions plus
recorded count, and update callers.

Low/perf: `nuubot/account/account.py:85` pulls all fills on every recon. The 60s
throttle makes this acceptable for now, but it scales with full fill history.

Required fix when this grows: pass `start_time` from last recon or filter by
open order IDs.

## proof checked

- Read `AGENTS.md`, `wiki/AGENTS.md`, `wiki/coding/rules.md`, and coding
  samples.
- `git diff --check 24ba423 911b6af`: pass.
- All `tests/test_*.py`: pass.
- Real sweep DB evidence:
  - sweep 41 complete `36/36`
  - `4784` positions
  - `14373` orders
  - `9568` fills
  - `6544` signals
  - `47,980 ms`
- Verified no source import of `nuubot.sweeps.trading`.

## proof missing

- No live Hyperliquid raw-shape proof.
- No real partial-fill exchange proof.
- No fresh post-commit server sweep rerun during this read-only audit.
- No test for TP/SL fill pending in simulator history when `stop()` runs before
  next recon.

## assumptions and open questions

- Assumed sweep 38-50 DBs are valid local proof artifacts for the committed code
  path.
- Assumed `balance()` is intended as real account API because the user
  explicitly requested it.

## bloat check

No old wrapper, fake runner, dead source import, or compatibility path found.
Found one fake public API (`balance`), one close/recon edge-case logic bug, one
metrics clarity issue, one fallback, one small duplicate helper, and one known
bounded-recon performance issue.
