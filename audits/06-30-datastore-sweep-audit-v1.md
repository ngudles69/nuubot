# Datastore/Sweep Audit V1

FAIL

Findings:

- High `nuubot/datastore/datastore.py:295`: `dbpath()` accepts any relative path with a parent and bypasses `dbroot`.
  Required fix: allow only bare DB names or absolute process-boundary paths; reject relative paths with parents.
- High `nuubot/sweeps/sweep.py:180` and `nuubot/sweeps/sweeprun.py:198`: failure paths still do local one-or-none handling with `tx.select(...); if rows: rows[0]`.
  Required fix: use `tx.get(SweeprunRow, sweeprun_id=...)` where the row must exist.
- Medium `nuubot/server/server.py:43`, `nuubot/sweeps/sweep.py:52`, `nuubot/sweeps/sweep.py:163`: finalizer/result threads mutate `finalizers` while shutdown iterates it.
  Required fix: iterate over `list(finalizers.values())` or use one lock-owned path.
- Medium `wiki/design/sweepmanager.md:90`, `wiki/design/server.md:30`, `wiki/design/server.md:33`: docs still describe a server-owned sweep pool, but current code and `wiki/design/processpool.md:19` say each sweep owns its own pool.
  Required fix: update stale docs to the current per-sweep pool model.
- Medium `wiki/design/sweeps.md:305`: docs say sweep `datastore` is a SQLAlchemy engine.
  Required fix: describe it as `Datastore` plus DB name/path.
- Medium `wiki/design/sweeps.md:199`, `wiki/design/sweeps.md:224`, `wiki/design/sweeps.md:293`: docs require timing in `results_json`, but current `sweep_results()` writes no timing.
  Required fix: either implement timing or update docs if timing is deferred.
- Low `nuubot/server/sweepmgr.py:43`: `list()` rebuilds DB root from config instead of using datastore's configured root.
  Required fix: derive the DB directory from the existing datastore path boundary.
- Low `nuubot/datastore/datastore.py:292`, `nuubot/nuubot.py:30`: `Datastore.stop()` is a no-op called by `Nuubot.stop()`.
  Required fix: remove the stub/call unless datastore starts owning real resources.
- Low `nuubot/bots/executors/tradebot/tradebot.py:12`: unused `FillRow` and `OrderRow` imports.
  Required fix: remove unused imports.

Disposition:

- Accepted and fixed all findings.
- `dbroot` is now resolved absolute at datastore construction.
- Worker failure rows now use `tx.get`.
- Shutdown iteration now snapshots finalizer/result thread values.
- Docs now describe sweep-local process pools and `Datastore` boundary.
- Sweep result summary now writes `results_json.timing`.
- SweepManager list uses datastore DB root.
- Removed `Datastore.stop`; `Nuubot.stop()` clears its datastore handle.
- Removed unused imports.

Bloat check: Found stale docs, one path-boundary escape, manual one-or-none row handling, a shutdown race, a no-op stub, and minor unused imports. No fake datastore or SQLAlchemy leak was found in the changed sweep/trade paths.
