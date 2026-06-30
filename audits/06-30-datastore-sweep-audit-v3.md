FAIL

Findings:

- High `nuubot/sweeps/sweep.py`: `Sweep.run()` reset the sweep DB and marked the sweep `running` before validating `sweep.workers`.
  - Required fix: validate workers before `_reset()`, then launch with that validated value.

- High `nuubot/server/sweepmgr.py`: `SweepManager.update()` did not use the same `run_lock` as run startup.
  - Required fix: protect update's active-check/delete/write path with `run_lock`.

- Medium `nuubot/core/sweep.py`: old runnable sweep path remained outside the current `SweepManager`/datastore result flow.
  - Required fix: hardcut the old runner or route it through the current `SweepManager` path; keep only shared helpers.

- Medium `wiki/design/sweeps.md`, `wiki/design/state.md`, `wiki/flow/sweep.md`: docs still said rerun/reset deletes the sweep DB.
  - Required fix: docs must say rerun resets child/result rows and keeps the sweep DB/config row; drop/delete DB is artifact removal.

Verified fixed from V1/V2:

- `dbpath()` rejects relative paths with parents.
- `tx()` and `next_seq()` reject missing DB files.
- exchange-meta fetch/normalize moved out of datastore.
- `Nuubot` owns `server_db = "server.db"`.
- duplicate run requests are locked.
- `result_threads` naming replaced finalizer/finalize in code and current docs.
- Local row-cardinality helpers, datastore indirection helpers, and old task
  function names are gone.
- changed sweep/trade paths do not import SQLAlchemy engine/session APIs directly.
- Old command-wrapper search returned no hits in `AGENTS.md`, `wiki`, `.project`, `audits`, `HANDOFF.md`, or `pyproject.toml`.

Proof checked:

- Static inspection of current working tree.
- Accepted provided V2 proof results; did not rerun tests because this was read-only.
- V1/V2 audit files exist at `audits/06-30-datastore-sweep-audit-v1.md` and `audits/06-30-datastore-sweep-audit-v2.md`.

Proof missing:

- No invalid `sweep.workers` proof showing DB state stays unchanged.
- No update-vs-run concurrency proof.
- No proof that `nuubot/core/sweep.py` is intentionally retained and safe.

Bloat check:

- No fake datastore, SQLAlchemy leak in changed sweep/trade paths, missing import, or dead `_one/_datastore` helper found.
