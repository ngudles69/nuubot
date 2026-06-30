---
title: datastore object
created: 2026-06-23
updated: 2026-06-30
type: wiki
status: active
tags: [design, objects, datastore, sqlite, sqlalchemy]
---

# datastore object

## purpose

Datastore is the SQLite verb boundary.

It owns SQLite file creation, table creation, indexes, transactions, DB path
resolution, and DML mechanics.

It does not own the application server DB identity. `Nuubot` passes
`server.db` into datastore verbs like any other DB.

It does not fetch or normalize exchange metadata.

SQLite is canonical. Do not add Postgres, migration, or dual-engine paths.

There are two DB kinds:

- server DB: persistent shared DB created by `nuubot_setup()`.
- instance DB: local per-bot or per-sweep DB created by the runtime/task init.

## interfaces

External commands:

- `dbname(id, kind, network="")`
- `create(db)`
- `drop(db)`
- `dbinit(db)`
- `insert(db, row)`
- `update(db, table, row)`
- `delete(db, table, **where)`
- `select(db, table, **where)`
- `get(db, table, **where)`
- `count(db, table, **where)`
- `upsert(db, row)`
- `tx(db)`
- `next_seq(db, name)`

Datastore receives:

- `db`: standardized DB name such as `sweep_25.db` or a concrete SQLite DB
  file at a process boundary.
- `table`: table row class when no row object is available.
- `row`: table row object. `insert()` and `upsert()` derive the table from
  `type(row)`.

Datastore outputs:

- DML results.
- created SQLite files, tables, and indexes.
- table definitions.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `dbname(id, kind, network="")` | ID, kind, optional network. | DB filename. | Standardizes DB names. Valid kinds are `sweep` and `bot`; bot DB names require network. |
| `create(db)` | DB file. | Created DB file. | Creates the SQLite DB file. |
| `drop(db)` | DB file. | Removed DB file. | Deletes the DB file. Destructive callers must list/count targets first. |
| `dbinit(db)` | DB file. | Ready DB. | Creates the DB file if missing and creates missing tables by DB name. Fails loud on unknown DB type or schema errors. |
| `insert(db, row)` | DB file and row object. | Inserted row. | Opens DB, inserts row, flushes generated keys, commits, closes. |
| `update(db, table, row)` | DB file, table, row. | Updated row. | Opens DB, updates row, commits, closes. |
| `delete(db, table, **where)` | DB file, table, filters. | Deleted row count. | Opens DB, deletes matching rows, commits, closes. |
| `select(db, table, **where)` | DB file, table, filters. | Row list. | Opens DB, reads matching rows, closes. |
| `get(db, table, **where)` | DB file, table, filters. | One row. | Opens DB, reads matching rows, closes, and fails loud unless exactly one row matches. |
| `count(db, table, **where)` | DB file, table, filters. | Count. | Opens DB, counts matching rows, closes. |
| `upsert(db, row)` | DB file and row object. | None. | Opens DB, performs current conflict behavior for that row, commits, closes. |
| `tx(db)` | DB file. | Transaction object. | Caller explicitly calls `start()`, DML verbs, `commit()` or `rollback()`, and `close()`. |
| `next_seq(db, name)` | DB file and sequence name. | Next integer. | Uses one short SQLite write transaction with `BEGIN IMMEDIATE`. If allocation fails, caller startup fails. |

## processing

Internal functions:

- open SQLite connection/session for one file.
- create tables and indexes if missing.
- allocate server sequence numbers.
- close after read/write.
- fail loud on schema creation errors.

## key helpers

- DB path builder.
- transaction creation.

## notes

- Use SQLAlchemy Core/DDL for SQLite when it keeps table creation and writes
  simple.
- Do not use long-lived server DB sessions or ORM object graphs for server DB
  access.
- No foreign keys are required or allowed.
- Domain objects own the meaning of persisted data.
- Datastore owns storage mechanics only.
- Datastore may save row objects, but it does not decide what those rows mean.
- Datastore does not decide bot lifecycle, order state, fill state, or PnL.
- Server DB writes use open connection, read/write, close.
- Actor/task DB writes use datastore verbs. Multi-step writes may keep an
  explicit datastore transaction open until commit/rollback.
- Per-bot DB tables do not repeat `bot_id`.
- Account, position, order, and fill rows follow the parent chain:
  account -> position -> order -> fill.
