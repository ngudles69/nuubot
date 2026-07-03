# handoff

Last updated: 2026-07-03

## focus

Sweep-local account, ledger, position, order, fill, simulator, and recon path.

## current status

- Current work is uncommitted.
- `nuubot/sweeps/trading.py` was hardcut and removed.
- Account/execution pieces now live in:
  - `nuubot/account/account.py`
  - `nuubot/account/ledger.py`
  - `nuubot/account/position.py`
  - `nuubot/account/order.py`
  - `nuubot/account/fill.py`
  - `nuubot/exchange/simulator.py`
- `SwTradeBot` imports `Order` and `TradingAccount` from `nuubot.account`.
- Active sweep template:
  `workspace/templates/sweeps/emacross-tradebot-2025-halves.toml`
  - executor account: `sgrid`
  - `take_profit_pct = 3.0`
  - `stop_loss_pct = 1.0`
  - `savedb = true`
- `Sweeprun` replays 1m execution bars as three synthetic ticks:
  - up bar: `open -> high -> low -> close`
  - down bar: `open -> low -> high -> close`
- The simulator supports market entries plus trigger TP/SL exits.
- `TradingAccount.recon()` pulls simulator evidence through
  `get_user_fills()` and `get_open_orders()`, matching the intended
  live/sim command shape.
- Audit fixes already applied:
  - partial fills no longer infer `filled` unless cumulative fills cover the
    order size.
  - `ReconResult.fills_recorded` now reports actual newly recorded fills.

## active server

- Server was restarted after the latest code changes.
- `http://127.0.0.1:5001/status` returned `running`.
- Latest real sweep proof is sweep `38`.

## active agents

None. The read-only adversarial audit agent completed and was closed.

## blockers

- No correctness blocker known for the current sweep path.
- Known performance issue: recon currently pulls all fills on every synthetic
  tick. Sweep 38 processed `37,843,200` tick events and spent most time in
  `timing_executor_next_ms`.

## files changed

- Added `nuubot/account/`
- Added `nuubot/exchange/`
- Deleted `nuubot/sweeps/trading.py`
- Updated sweep executor, sweep persistence/reporting, sweep template, tests,
  scratchpad, and durable wiki design pages around account/recon/sweep state.

Run `git status --short` for the exact uncommitted set.

## proof run

- `$env:PYTHONPATH='.'; rtk uv run python tests/test_sweep_trading.py`
- `$env:PYTHONPATH='.'; rtk uv run python tests/test_swtradebot.py`
- `$env:PYTHONPATH='.'; rtk uv run python -m compileall -q nuubot tests`
- `$env:PYTHONPATH='.';` all `tests\test_*.py`
- `git diff --check`
  - clean except existing LF/CRLF warnings.
- Real server proof:
  - restarted `./server.sh`
  - created sweep `38` from the real template
  - ran `POST /api/sweeps/38/run`
  - metrics endpoint reported `complete_count=36`, `failed_count=0`,
    `progress=36/36`
- Sweep 38 report:
  - `rtk uv run python -m nuubot.sweep 38`
  - `account_count=1`
  - `botrun_count=4789`
  - `signal_count=6544`
  - `position_count=4789`
  - `order_count=14388`
  - `fill_count=9578`
  - `win_loss=24/36 (66.7%)`
  - `profit_factor=4.54`
  - `ev=+10.62%`
  - `total_ms=117215`
- Sweep 38 DB sanity:
  - `zero_avg_exit_px=0`
  - `open_positions=0`
  - `open_orders=0`
  - `wrong_tp_reason=0`
  - `wrong_sl_reason=0`
  - `uncanceled_sibling=0`

## proof not run

- No live Hyperliquid proof.
- No rejected-order or insufficient-balance proof.
- No `savedb=false` speed comparison after the account split.

## decisions made

- Use `create_position`, not `add_position`, for ledger-owned position
  creation.
- Use `open`, not `working`, for recon-eligible orders/positions.
- `TradingAccount` is the account boundary; it owns one ledger and one
  exchange/simulator connection.
- Ledger only owns positions and position accounting.
- Position owns order collection and position accounting.
- Order owns submitted intent plus exchange state and fills.
- Fill is immutable execution evidence.
- Recon applies the minimum needed exchange truth: open positions, open orders,
  and fills.

## next action

Optimize recon scope before more strategy tuning:
track a fill checkpoint or query only open-order `cloid`/`oid` evidence so the
tick path does not rescan all fills on every synthetic tick.
