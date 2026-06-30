# handoff

Last updated: 2026-06-30

## focus

Datastore boundary and sweep execution cleanup in `D:\rust\nuubot`.

## current status

- Datastore is now the common DB boundary: `create`, `drop`, `dbinit`,
  `insert`, `update`, `delete`, `select`, `get`, `count`, `upsert`, `tx`, and
  `next_seq(db, name)`.
- `Nuubot` owns the server DB name: `server.db`.
- DB naming is centralized in `nuubot/datastore/dbname.py`.
- Exchange metadata fetch/normalize code moved out of datastore into
  `nuubot/core/exchange_meta.py`.
- Sweep DBs keep sweep, sweeprun, botrun, ledger, account, and event rows.
  Rerun resets run-owned rows inside the existing sweep DB.
- SweepManager owns result threads and a shared run lock for run/update
  coordination.
- `nuubot/core/sweep.py` is no longer a runnable entrypoint; it only keeps the
  shared sweep helper functions used by `nuubot/sweeps/sweep.py`.
- Old sweep command wrappers were deleted.
- Sweep notebooks use datastore verbs and `dbname(...)` instead of the removed
  session/config database path.
- Old command-wrapper references were removed from repo agent/docs instructions.
- Stale logical DB names were removed from active config; DB filenames now come
  from `server.db` and `dbname(...)`.

## active agents

None. Read-only adversarial audits V1/V2/V3/V4/V5 are saved in `audits/`.

## blockers

None known.

## files changed

- Datastore: `nuubot/datastore/datastore.py`,
  `nuubot/datastore/dbname.py`, `nuubot/datastore/models.py`,
  `nuubot/datastore/__init__.py`.
- Config: `nuubot/config/models.py`, `workspace/config/config.toml`.
- App/meta: `nuubot/nuubot.py`, `nuubot/core/exchange_meta.py`.
- Sweep runtime: `nuubot/server/sweepmgr.py`, `nuubot/server/server.py`,
  `nuubot/sweeps/sweep.py`, `nuubot/sweeps/sweeprun.py`,
  `nuubot/core/sweep.py`.
- Trade ledger: `nuubot/bots/executors/tradebot/tradebot.py`.
- Proof/tests: `tests/test_datastore_dbname.py`,
  `tests/test_datastore_boundary.py`, `tests/test_sweep_results_failure.py`,
  `tests/test_sweep_run_guards.py`, `tests/test_runtime_flow.py`.
- Notebooks/wrappers: `notebooks/emacross.ipynb`,
  `notebooks/emacross_ghbot.ipynb`, `notebooks/ghbot.ipynb`, and deleted old
  root sweep command wrappers.
- Docs/plans/audits: `wiki/**`, `.project/plans/**`, `AGENTS.md`,
  `audits/06-30-datastore-sweep-audit-v*.md`.

## proof run

- `uv run python -m compileall -q nuubot tests`: passed.
- `uv run python -m tests.test_datastore_dbname`: passed.
- `uv run python -m tests.test_datastore_boundary`: passed.
- `uv run python -m tests.test_sweep_results_failure`: passed.
- `uv run python -m tests.test_sweep_run_guards`: passed, including invalid
  workers, update-vs-run locking, and launch-failure persistence.
- `uv run python -m tests.test_runtime_flow`: passed.
- Notebook code-cell compile check for `emacross.ipynb`,
  `emacross_ghbot.ipynb`, and `ghbot.ipynb`: passed.
- `git diff --check`: passed with only LF/CRLF warnings.
- Widened stale-reference grep for old command-wrapper references, old core
  sweep commands, old datastore session/config calls, old logical DB names, and
  old SweepManager method names: passed.
- Sweep 25 rerun through SweepManager: `status=complete`,
  `complete_count=4`, `failed_count=0`, `progress=4/4`.
- Sweep 25 DB check after rerun: `sweeprun=4`, `position=288`, `order=576`,
  `fill=576`, `botrun=288`, timing `bars=8640`, `worker_count=4`,
  `total_ms=6409`.

## proof not run

- No Playwright/WebGUI screenshot check.
- No foreground `uv run python -m nuubot.server` manual Ctrl+C shutdown proof.

## decisions made

- Datastore owns DB verbs and private SQLAlchemy mechanics.
- Callers pass a DB name and row/table intent; callers do not open sessions.
- Active config does not carry logical DB names.
- `create(db)` creates an empty DB file, `drop(db)` removes the DB file, and
  `dbinit(db)` creates the DB and tables if missing.
- DB filenames are standardized by `dbname(id, "sweep")` and
  `dbname(id, "bot", network)`.
- Old runnable sweep path was removed instead of keeping a parallel execution
  path outside SweepManager.

## next action

Commit this work, then use `git log -1 --oneline` as the restart anchor.
