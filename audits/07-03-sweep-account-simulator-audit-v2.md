PASS

## scope

Re-audit after fixing the sweep account, ledger, simulator, recon, stop-close,
and sweep report issues found in v1 and follow-up adversarial reviews.

## findings

No open correctness findings remain in the audited sweep path.

Resolved issues:

- `SwTradeBot.stop()` now runs explicit pre-close `account.recon()` before any manual market close.
- Manual close PnL now uses actual ledger fills and entry notional, not requested prices.
- TP/SL fills inside the recon throttle window are synced before stop cleanup, preventing duplicate close orders.
- Cumulative simulator fill history no longer double-counts already-recorded partial fills.
- `TradingAccount.balance()` no longer returns fake zero simulator balance.
- `TradeLedger.record_fills()` has one contract and returns changed positions plus recorded fill count.
- Missing ledger position lookup fails loud.
- `SwTradeBot` uses `TradingAccount.create_position()` / `TradingAccount.position()` for bot-facing position operations.
- Sweep result and report paths use `ticks` for synthetic replay ticks.
- Sweep account validation no longer has an `account_names=None` bypass.
- Docs no longer say `Sweeprun` owns `executor.accounts` ingest/recon.

## proof checked

- `$env:PYTHONPATH='.'; Get-ChildItem tests\test_*.py | Sort-Object Name | ForEach-Object { python $_.FullName }`
- `python -m compileall nuubot tests`
- `git diff --check` clean except existing LF/CRLF warnings.
- `curl.exe -fsS http://127.0.0.1:5001/status`
- Real server sweep `53` from `workspace/templates/sweeps/emacross-tradebot-2025-halves.toml`:
  - status `complete`
  - progress `36/36`
  - failed `0`
  - positions `4784`
  - orders `14373`
  - fills `9568`
  - signals `6544`
  - total_ms `48130`
  - ticks `37843200`
- `python -m nuubot.sweep 53`
- Raw SQLite check on `workspace/db/sweep_53.db`: `performance` and `tradebot` JSON contain `ticks`, no `bars` key leftovers.

## proof gaps

- No live Hyperliquid proof.
- No rejected-order or insufficient-balance proof.
- No savedb=false comparison after final PnL/account fixes.

## assumptions

- The sweep-local simulator remains full-liquidity and full-fill by design.
- Commission/slippage are intentionally included in reported bot PnL through ledger fills.

Bloat check: no fake runner, fake simulator balance, unused duplicate fill helper, hidden account validation bypass, old `bars_per_second` path, or unapproved compatibility path found in the current audited sweep slice. Remaining known optimization is recon scope: it still pulls cumulative fills and filters locally.
