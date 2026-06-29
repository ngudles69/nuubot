---
title: datastore object
created: 2026-06-23
updated: 2026-06-29
type: wiki
status: active
tags: [design, objects, datastore, sqlite, sqlalchemy]
---

# datastore object

## purpose

Datastore is the SQLite boundary.

It owns SQLite file creation, table creation, indexes, and short-lived
connections.

SQLite is canonical. Do not add Postgres, migration, or dual-engine paths.

There are two DB kinds:

- server DB: persistent shared DB created by `nuubot_setup()`.
- instance DB: local per-bot, per-sweep, or per-sweeprun DB created by the
  runtime/task init.

## interfaces

External commands:

- `init_server()`
- `init_bot(path)`
- `init_sweep(path)`
- `connect(path)`
- `next_seq(name)`

Datastore receives:

- SQLite file path.
- table definitions.

Datastore outputs:

- short-lived connection/session access.
- created SQLite files, tables, and indexes.
- table definitions.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init_server()` | Server DB path. | Ready server DB. | Creates `workspace/db/server.db` and server tables if missing. Fails loud on schema errors. |
| `init_bot(path)` | Bot DB path. | Ready bot DB. | Creates the bot SQLite file and `bot`, `account`, `command`, `event`, `botstate`, `position`, `order`, `fill`, and `simstate` tables if missing. Fails loud on schema errors. |
| `init_sweep(path)` | Sweep DB path. | Ready sweep DB. | Creates `sweep`, `sweeprun`, `botrun`, `account`, `event`, `position`, `order`, and `fill` tables if missing. Fails loud on schema errors. |
| `connect(path)` | SQLite file path. | Short-lived session/connection. | Open, read/write, close. No long-lived server DB connection. |
| `next_seq(name)` | Sequence name. | Next integer. | Uses one short SQLite write transaction with `BEGIN IMMEDIATE`. If allocation fails, caller startup fails. |

## processing

Internal functions:

- open SQLite connection/session for one file.
- create tables and indexes if missing.
- allocate server sequence numbers.
- close after read/write.
- fail loud on schema creation errors.

## key helpers

- DB path builder.
- session creation.

## notes

- Use SQLAlchemy Core/DDL for SQLite when it keeps table creation and writes
  simple.
- Do not use long-lived server DB sessions or ORM object graphs for server DB
  access.
- No foreign keys are required or allowed.
- Domain objects own the meaning of persisted data.
- Datastore owns infrastructure only.
- Datastore does not decide bot lifecycle, order state, fill state, or PnL.
- Server DB writes use open connection, read/write, close.
- Actor/task DB writes may use actor/task-owned local access while the
  instance is running.
- Per-bot DB tables do not repeat `bot_id`.
- Account, position, order, and fill rows follow the parent chain:
  account -> position -> order -> fill.
