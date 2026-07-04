# handoff

Last updated: 2026-07-04

## focus

Sweep report CLI, first Textual TUI slice, and sweep trade sizing.

## current status

- Latest committed baseline: `6d464cc Fix sweep account audit issues`.
- Current worktree has uncommitted CLI/TUI/report changes.
- Report implementation moved under `nuubot/cli/**`.
- Canonical report command remains `uv run python -m nuubot.sweeps.report <sweep_id>`.
- Daily report shortcut is `./report.sh <sweep_id>`.
- First TUI slice lives under `nuubot/cli/tui/**`.
- Daily TUI shortcut is `./tui.sh`.
- `textual>=8.2.8` was added to `pyproject.toml` and `uv.lock`.
- Old root report module `nuubot/sweep.py` was deleted.
- Sweep templates now default to `investment_usdc = 10000`,
  `trade_use = "pct"`, `trade_amount = 100`, and `trade_pct = 2.0`.
- Sweep execution now sizes orders by configured USDC trade value instead of
  one whole coin.
- `Sweeprun` tracks `current_balance_usdc` across botruns and skips new trades
  when the configured trade size or 10 USDC minimum cannot be funded.
- Fresh proof sweep `54` completed `36/36` with `0` failed.

## active agents

None.

## files changed

- `AGENTS.md`
- `HANDOFF.md`
- `nuubot/cli/__main__.py`
- `nuubot/cli/cli.py`
- `nuubot/cli/sweeps/__init__.py`
- `nuubot/cli/sweeps/report.py`
- `nuubot/cli/tui/__init__.py`
- `nuubot/cli/tui/__main__.py`
- `nuubot/cli/tui/app.py`
- `nuubot/bots/executors/tradebot/tradebot.py`
- `nuubot/core/dtypes.py`
- `nuubot/sweeps/executors/executor.py`
- `nuubot/sweeps/executors/swtradebot.py`
- `nuubot/sweeps/models.py`
- `nuubot/sweeps/sweeprun.py`
- `nuubot/sweeps/template.py`
- `nuubot/sweeps/report.py`
- `nuubot/sweep.py` deleted
- `pyproject.toml`
- `uv.lock`
- `report.sh`
- `tui.sh`
- `wiki/design/sweeps.md`
- `wiki/templates-sweeps.md`
- `wiki/testing.md`
- `workspace/templates/sweeps/emacross-tradebot-2025-halves.toml`
- `tests/test_sweep_template.py`
- `tests/test_swtradebot.py`

## decisions made

- CLI/TUI program code lives under `nuubot/cli/**`.
- `nuubot.sweeps.report` stays as the canonical public report module and calls
  the CLI implementation.
- Keep one report command surface; do not add parallel result CLIs.
- TUI is Textual-based.
- First TUI slice is read-only except opening/refreshing views.
- Home menu starts with sweeps and bots.
- Sweeps screen supports digit-prefix jump by sweep id.
- Bots screen lists bot DB files if present; this workspace currently has no
  bot DBs.
- `trade_use = "pct"` is the default. `trade_amount` stays in config but only
  applies when `trade_use = "amount"`.
- PnL percent is now account return based on `investment_usdc`, not summed
  per-trade return against entry notional.

## proof run

- `uv run python -m compileall -q nuubot tests`
- `$env:PYTHONPATH='.';` all `tests\test_*.py`
- `git diff --check`
- Restarted server on port `5001` so current code was active.
- `curl.exe -X POST --data-binary @workspace/templates/sweeps/emacross-tradebot-2025-halves.toml http://127.0.0.1:5001/api/sweeps`
  - created sweep `54`
- `curl.exe -X POST http://127.0.0.1:5001/api/sweeps/54/run`
- `curl.exe http://127.0.0.1:5001/api/sweeps/54/metrics`
  - complete `36/36`
  - failed `0`
- `bash ./report.sh 54`
- DB spot check for sweep `54`, sweeprun `1`:
  - config `investment_usdc=10000`, `trade_use=pct`, `trade_pct=2.0`
  - `trade_usdc=200`
  - `ending_balance_usdc=9964.447849283122`
  - `net_pnl_usdc=-35.5521507168922`
  - `pnl_pct=-0.355521507168922`
  - average `entry_cash=199.99705882352941`
- `uv run python -m nuubot.sweeps.report 53`
- `uv run python -m nuubot.cli report 53`
- `bash ./report.sh 53`
- `bash -lc './report.sh 53 >/tmp/nuubot-report.out'`
- Textual test harness:
  - opened home
  - pressed `s`
  - listed real sweeps
  - digit-jumped to sweep `53`
  - opened details
  - returned home
  - opened bots
- `git diff --check`
  - clean except existing LF/CRLF warnings.

## proof not run

- Did not launch interactive `./tui.sh` directly because it owns the terminal.
- Did not retest live Hyperliquid.
- Did not launch interactive `./tui.sh` after the trade-sizing change.

## blockers

None known.

## next action

Review the uncommitted CLI/TUI/report/trade-sizing diff, then decide whether
to run `./tui.sh` manually or commit the current slice.
