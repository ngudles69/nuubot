---
title: datastore boundary execplan
created: 2026-06-30
type: plan
status: implemented
---

# Datastore Boundary ExecPlan

## Objective

Move SQLite session/engine mechanics behind `Datastore` so callers say what DB
and table work they want, not how SQLAlchemy should do it.

## Current Problem

`Datastore` creates SQLite engines and sessions, but callers still manage
`Session`, `commit`, `delete`, `select`, and sometimes `create_engine`
directly.

Observed leak points:

- `nuubot/server/sweepmgr.py`
- `nuubot/sweeps/sweep.py`
- `nuubot/sweeps/sweeprun.py`
- `nuubot/bots/executors/tradebot/tradebot.py`
- `nuubot/datastore/models.py`

## Target Shape

Public datastore verbs:

```python
create(db)
drop(db)
dbinit(db)
insert(db, row)
update(db, table, row)
delete(db, table, **where)
select(db, table, **where)
get(db, table, **where)
count(db, table, **where)
upsert(db, row)
tx(db)
next_seq(db, name)
```

## Call Taxonomy

Normalize every current DB call into these boundary calls:

| Current shape | Current files | Boundary call |
| --- | --- | --- |
| DB file creation | `datastore.py` | `datastore.create(db)` |
| DB file deletion | future reset paths | `datastore.drop(db)` |
| DB and table initialization | `datastore.py`, manager setup | `datastore.dbinit(db)` |
| `session.add(row); commit()` | `server/sweepmgr.py`, `sweeps/sweep.py`, `tradebot.py`, `datastore/models.py` | `datastore.insert(db, row)` or `tx.insert(row)` |
| `session.get(RowClass, key)` | `server/sweepmgr.py`, `sweeps/sweep.py`, `sweeps/sweeprun.py`, `tradebot.py` | `datastore.get(db, table, key=key)` or `tx.get(table, key=key)` |
| `session.query(RowClass).filter_by(...).one_or_none()` | `sweeps/sweeprun.py` | `datastore.get(db, table, **where)` or `tx.get(table, **where)` when exactly one row must exist |
| `session.query(RowClass).filter_by(...)` loop | `sweeps/sweep.py`, `sweeps/sweeprun.py` | `datastore.select(db, table, **where)` or `tx.select(table, **where)` |
| mutate loaded row, then `commit()` | `server/sweepmgr.py`, `sweeps/sweep.py`, `sweeps/sweeprun.py`, `tradebot.py` | explicit `tx.start()`, row mutation, `tx.commit()` |
| `session.execute(delete(RowClass))` | `server/sweepmgr.py`, `sweeps/sweep.py` | `datastore.delete(db, table, **where)` or `tx.delete(table, **where)` |
| `select(func.count()).where(...)` | `server/sweepmgr.py`, `sweeps/sweep.py` | `datastore.count(db, table, **where)` |
| SQLite `insert(...).on_conflict...` | `tradebot.py`, `datastore.py` | `datastore.upsert(db, row)` or `tx.upsert(row)` |
| direct `create_engine()` / `Session(engine)` | `sweeps/sweep.py`, `sweeps/sweeprun.py`, `tradebot.py` | private `Datastore._engine()` and public verbs only |

`tx(db)` is not a general escape hatch. It exposes the same verbs without
per-call commits so reset/create/finalize operations can stay atomic.

Rules:

- `db` means the concrete SQLite DB file, even though it is implemented as a
  `Path` or string.
- `table` means the table row class, for example `SweepRow`.
- `row` means a row object or plain row data for that table.
- `create(db)` creates the DB file.
- `drop(db)` deletes the DB file.
- `dbinit(db)` creates the DB if missing and creates missing tables by DB name.
- Single DB actions use one datastore verb.
- Multi-step atomic changes use explicit transaction lifecycle:

```python
tx = datastore.tx(db)
tx.start()
try:
    tx.insert(row)
    tx.commit()
except Exception:
    tx.rollback()
    raise
finally:
    tx.close()
```

- `tx(db)` only exposes the same DML verbs without per-call commits.
- `insert()` and `tx.insert()` derive the table from `type(row)` and return the inserted row so generated keys are
  available after flush.
- `select()` returns a list.
- `get()` returns exactly one row and fails loud if zero or many rows match.
- `upsert()` preserves current conflict behavior where needed. Current account
  row behavior is insert-if-missing with no update.
- No `Session`, `create_engine`, or `commit()` outside `datastore.py` for
  project DB row work.
- `Datastore` owns DB root/path resolution, not app config or the `server.db`
  identity.
- `Nuubot` owns `server_db = "server.db"` and passes it into datastore verbs.
- Server DB operations remain short open/read-write/close operations.
- Bot/sweep DB operations also go through datastore; a transaction may stay
  open for related multi-row work.
- Do not add `SweepStore`, `BotStore`, repositories, factories, or compatibility
  adapters.

## Implementation Plan

1. Add `Datastore` lifecycle/DML verbs and a tiny transaction handle in
   `nuubot/datastore/datastore.py`.
2. Convert `sweepmgr.py` to use `insert/select/delete/count/tx`.
3. Convert `sweeps/sweep.py` and `sweeps/sweeprun.py` to use datastore verbs
   instead of direct engines/sessions.
4. Convert trade sweep ledger writes to use datastore transactions. Convert
   `Position`, `Order`, and `Fill` helpers to produce row objects instead of
   saving into a session.
5. Remove public session exposure if no callers remain.
6. Update datastore design docs to the new boundary.
7. Run compile and sweep-focused proof.

## Proof

Run:

```bash
uv run python -m compileall -q nuubot tests
uv run python -m tests.test_datastore_dbname
uv run python -m tests.test_datastore_boundary
uv run python -m tests.test_sweep_results_failure
uv run python -m tests.test_sweep_run_guards
```

Results:

- `uv run python -m compileall -q nuubot tests`: passed.
- SweepManager process-pool proof reran sweep 25 to completion:
  `status=complete`, `complete_count=4`, `failed_count=0`, `progress=4/4`.
- DB verification after sweep 25:
  `sweep complete 4`, `sweeprun=4`, `positions=288`, `orders=576`,
  `fills=576`, `botrun=288`.
- Sweep result timing persisted under `results_json.timing`:
  `bars=8640`, `worker_count=4`, `total_ms=6409`.
- `uv run python -m tests.test_datastore_dbname`: passed.
- `uv run python -m tests.test_datastore_boundary`: passed.
- `uv run python -m tests.test_sweep_results_failure`: passed.
- `uv run python -m tests.test_sweep_run_guards`: passed, including invalid
  workers, update-vs-run locking, and launch-failure persistence.
- `uv run python -m tests.test_runtime_flow`: passed.
- Notebook code-cell compile check for `emacross.ipynb`,
  `emacross_ghbot.ipynb`, and `ghbot.ipynb`: passed.
- Widened stale-reference grep for old command-wrapper references, old core
  sweep commands, old datastore session/config calls, old logical DB names, and
  old SweepManager method names: passed.

## Audit

Run read-only adversarial plan review before edits.
Run read-only implementation review after proof.

Plan audit disposition:

- Accepted: `insert()` must return the flushed row so generated IDs are usable.
- Accepted: `select()` returns a list and callers validate cardinality.
- Accepted: current account conflict behavior is insert-if-missing/no-update.
- Accepted: sweep proof is mandatory.
- Rejected: remove public `create/drop`. User explicitly chose
  `create(db)`, `drop(db)`, and `dbinit(db)` as the lifecycle boundary.

Implementation audit V1:

- FAIL. Report saved at `audits/06-30-datastore-sweep-audit-v1.md`.
- Accepted and fixed: DB path boundary, failure-path exact row reads,
  result-thread iteration snapshots, stale process-pool docs, stale datastore
  docs, missing sweep timing, SweepManager DB root usage, no-op
  `Datastore.stop`, and unused imports.

Implementation audit V2:

- FAIL. Report saved at `audits/06-30-datastore-sweep-audit-v2.md`.
- Accepted and fixed: locked run-start path, DML missing-DB guard, exchange
  meta moved out of datastore, overview/processpool doc drift, and
  result-thread naming.

Implementation audit V3:

- FAIL. Report saved at `audits/06-30-datastore-sweep-audit-v3.md`.
- Accepted and fixed: validate workers before resetting sweep rows, protect
  update active-check/delete/write with the run lock, hardcut the old
  `nuubot.core.sweep` runnable path, and correct rerun/reset docs.

Implementation audit V4:

- FAIL. Report saved at `audits/06-30-datastore-sweep-audit-v4.md`.
- Accepted and fixed: removed stale logical DB names from `AppConfig`,
  tracked config, and runtime-flow fixture; updated stale runtime-flow tests to
  current app-network and Signaler ownership.

Implementation audit V5:

- FAIL. Report saved at `audits/06-30-datastore-sweep-audit-v5.md`.
- Accepted and fixed: deleted stale sweep command wrappers, converted stale
  notebook datastore/session cells to datastore verbs and standardized DB
  names, and widened stale scans to include notebooks and root command files.
