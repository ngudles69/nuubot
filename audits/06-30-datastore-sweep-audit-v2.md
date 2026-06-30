# Datastore/Sweep Audit V2

FAIL

Findings:

- High `nuubot/sweeps/sweep.py` / `nuubot/server/sweepmgr.py`: run start was not synchronized. Two concurrent run requests could reset the same sweep DB and launch duplicate pools.
  Required fix: make the run-start path locked or atomically transition the sweep row before worker launch.
- High `nuubot/datastore/datastore.py`: DML could open a missing SQLite DB path and let SQLite create an empty file.
  Required fix: only `create()` and `dbinit()` may create DB files; DML/transactions reject missing DB files. `SweepManager.run()` should validate the sweep DB exists.
- Medium `nuubot/datastore/datastore.py`: exchange-meta fetching/normalization lived in datastore.
  Required fix: move fetch/normalize orchestration out of datastore.
- Medium `wiki/design/overview.md` and `wiki/design/processpool.md`: stale durable docs still described old sweeprun DB init, old state verbs, and finalizer terminology.
  Required fix: update docs to current sweep DB row model, datastore verbs, and result-thread naming.

Disposition:

- Accepted and fixed all findings.
- `SweepManager` now owns `run_lock`; `Sweep.run()` serializes active-run check, reset, process-pool launch, and result-thread registration.
- `SweepManager.run()` validates sweep ID and sweep DB existence before constructing `Sweep`.
- `Datastore.tx()` and `next_seq()` now call `_require_db()` so DML refuses missing DB files.
- `Datastore.dbroot` resolves to an absolute path so process-pool workers receive absolute DB paths.
- Hyperliquid meta fetch/normalize/refresh orchestration moved to `nuubot/core/exchange_meta.py`; datastore is DB verbs/path/table mechanics.
- Code and docs now use `result_threads` instead of finalizer naming.
- Overview/processpool docs now match the sweep DB row model and current datastore verbs.

Bloat check: Found real race risk, datastore boundary bloat, stale durable docs, and a SQLite missing-file lifecycle bug. No fake datastore, SQLAlchemy leak in changed sweep/trade paths, old compatibility path, or dead `_one/_datastore` helper was found.
