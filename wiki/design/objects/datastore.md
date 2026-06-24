---
title: datastore object
created: 2026-06-23
updated: 2026-06-23
type: wiki
status: active
tags: [design, objects, datastore, sqlalchemy]
---

# datastore object

## purpose

Datastore is the SQLAlchemy boundary.

It owns the DB connection, SQLAlchemy models, database creation, tables, and
indexes.

Current runnable prototype uses a local SQLite file under `workspace/db`.
PostgreSQL can replace the engine later without changing caller ownership.

## interfaces

External commands:

- `init(config)`
- `start()`
- `stop()`
- `connect()`
- `disconnect()`
- `create_database()`
- `create_tables()`
- `create_indexes()`
- `session()`
- `transaction()`

Datastore receives:

- database config.
- SQLAlchemy model definitions.

Datastore outputs:

- engine/session access.
- created database/tables/indexes.
- SQLAlchemy models.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init(config)` | Database config. | Initialized Datastore. | Stores DB config and model registry. Does not connect yet. |
| `start()` | Initialized Datastore. | Ready Datastore. | Connects and ensures database, tables, and indexes. |
| `stop()` | Ready Datastore. | Stopped Datastore. | Closes DB resources. |
| `connect()` | Database config. | Connected Datastore. | Opens SQLAlchemy engine/session path. Fails loud on connection errors. |
| `disconnect()` | Connected Datastore. | Closed resources. | Closes owned DB resources. |
| `create_database()` | Database config. | Existing database. | Creates missing development database. Does not migrate old incompatible state. |
| `create_tables()` | Model registry. | Existing tables. | Creates SQLAlchemy tables without foreign keys. |
| `create_indexes()` | Model/index registry. | Existing indexes. | Creates required indexes. Fails loud on invalid model/index definition. |
| `session()` | Connected Datastore. | SQLAlchemy session. | Caller uses SQLAlchemy standard syntax. No raw SQL by default. |
| `transaction()` | Connected Datastore. | Transaction scope. | Commits on success, rolls back on error, and re-raises the error. |

## processing

Internal functions:

- connect to the configured SQLAlchemy engine.
- create database if missing.
- create tables if missing.
- create indexes if missing.
- expose SQLAlchemy sessions.
- configure SQLAlchemy engine/session behavior.
- fail loud on schema creation errors.

## key helpers

- SQLAlchemy model registry.
- session creation.
- transaction context.
- database existence check.
- table creation.
- index creation.

## notes

- Code should use SQLAlchemy standard syntax, not raw SQL by default.
- No foreign keys are required or allowed.
- Domain objects own the meaning of persisted data.
- Datastore owns infrastructure only.
- Datastore does not decide bot lifecycle, order state, fill state, or PnL.
- SQLite is current prototype storage. PostgreSQL remains the intended later
  production engine.
