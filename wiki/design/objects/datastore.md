---
title: datastore object
created: 2026-06-23
updated: 2026-06-24
type: wiki
status: active
tags: [design, objects, datastore, sqlalchemy]
---

# datastore object

## purpose

Datastore is the SQLAlchemy boundary.

It owns the DB connection, SQLAlchemy models, database creation, tables, and
indexes.

Current runnable prototype uses local SQLite files under `workspace/db`, one
file per configured database name. PostgreSQL can replace the engine later
without changing caller ownership.

## interfaces

External commands:

- `init()`
- `stop()`
- `session()`

Datastore receives:

- validated app config.
- SQLAlchemy model definitions.

Datastore outputs:

- engine/session access.
- created databases, tables, and indexes.
- SQLAlchemy models.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Validated app config. | Initialized Datastore. | Opens SQLAlchemy engines for every configured database and runs SQLAlchemy metadata creation. Creates missing databases/tables/indexes. Fails loud on connection or schema errors. |
| `session(database="server")` | Initialized Datastore and database name. | SQLAlchemy session. | Caller uses SQLAlchemy standard syntax. No raw SQL by default. |
| `stop()` | Initialized Datastore. | Stopped Datastore. | Disposes owned SQLAlchemy engines. |

## processing

Internal functions:

- open configured SQLAlchemy engines.
- create every configured database if missing.
- create SQLAlchemy tables and metadata indexes if missing.
- expose SQLAlchemy sessions.
- fail loud on schema creation errors.

## key helpers

- session creation.
- database name list from config.

## notes

- Code should use SQLAlchemy standard syntax, not raw SQL by default.
- No foreign keys are required or allowed.
- Domain objects own the meaning of persisted data.
- Datastore owns infrastructure only.
- Datastore does not decide bot lifecycle, order state, fill state, or PnL.
- `create_databases()`, `create_tables()`, and `create_indexes()` are not public
  datastore commands. `init()` owns that setup.
