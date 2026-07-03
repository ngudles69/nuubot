# handoff

Last updated: 2026-07-03

## focus

Sweep-local account, ledger, position, order, fill, simulator, recon, and sweep
reporting.

## current status

- Last committed/pushed baseline before audit fixes: `911b6af Add sweep account simulator ledger`.
- Audit fixes are implemented and intended to be committed as the closeout commit.
- Active server is running at `http://127.0.0.1:5001`.
- Latest real proof sweep is `53`.

## changed areas

- `nuubot/account/`
- `nuubot/exchange/simulator.py`
- `nuubot/sweeps/executors/`
- `nuubot/sweeps/sweeprun.py`
- `nuubot/sweeps/sweep.py`
- `nuubot/sweep.py`
- `tests/test_sweep_trading.py`
- `tests/test_swtradebot.py`
- `tests/test_sweep_run_guards.py`
- `wiki/design/objects/account.md`
- `wiki/design/sweeps.md`
- `nuubot/sweeps/sweeprun.md`
- `audits/07-03-sweep-account-simulator-audit-v1.md`
- `audits/07-03-sweep-account-simulator-audit-v2.md`

## decisions made

- `TradingAccount` is the bot-facing account boundary.
- `SwTradeBot` owns account `ingest_bbo()` and throttled `recon()` for its single configured account.
- `Sweeprun` feeds replay ticks to the executor and owns timing/persistence only.
- Manual stop does pre-close recon first, then submits a market close only if still open.
- Reported trade PnL uses actual ledger fills and entry notional, so slippage and fees are included.
- Synthetic replay throughput is reported as `ticks`, not bars.
- Sweep executor account validation is required; no `None` bypass.

## proof run

- `$env:PYTHONPATH='.';` all `tests\test_*.py`
- `python -m compileall nuubot tests`
- `git diff --check`
  - clean except existing LF/CRLF warnings.
- Server:
  - restarted through `./server.sh`
  - `/status` returned `running`
- Real sweep:
  - created sweep `53` from `workspace/templates/sweeps/emacross-tradebot-2025-halves.toml`
  - ran `POST /api/sweeps/53/run`
  - completed `36/36`, failed `0`
  - `positions=4784`, `orders=14373`, `fills=9568`, `signals=6544`
  - `total_ms=48130`, `ticks=37843200`, workers `8`
- Report:
  - `python -m nuubot.sweep 53`
  - `profit_factor=0.04`, `ev=-15.94%`
  - PnL changed materially because reported bot PnL now includes actual fills plus commission/slippage.
- DB check:
  - `workspace/db/sweep_53.db`
  - current `performance` and `tradebot` JSON use `ticks`
  - no `bars` key leftovers in those payloads.
- Adversarial reviews:
  - v1 audit saved at `audits/07-03-sweep-account-simulator-audit-v1.md`
  - final closeout saved at `audits/07-03-sweep-account-simulator-audit-v2.md`

## proof not run

- No live Hyperliquid proof.
- No rejected-order or insufficient-balance proof.
- No `savedb=false` comparison after final PnL/account fixes.

## blockers

None known for the current sweep path.

## next action

Resume from latest `git log --oneline -3` and `git status --short`.
