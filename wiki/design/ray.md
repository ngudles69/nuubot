---
title: ray design
created: 2026-06-29
updated: 2026-06-29
type: wiki
status: active
tags: [design, ray, runtime, sweeps]
---

# ray design

## purpose

Ray is the optional worker/process layer used by Server.

- Bot runtime is plain Python and must run without Ray.
- Managed bots run as thin Ray actor wrappers around BotRuntime.
- Sweeps run as stateless Ray tasks.
- Ray owns worker placement, lifecycle, and parallel fanout.
- SQLite owns persisted state, not Ray object storage.
- Server is not a Ray actor in the first design.
- Bot websocket/feed clients are bot-local first.

## dependencies

- `ray` is a first-class project dependency.
- Add it to project dependencies, then install through `rtk uv sync`.
- Do not add a second process manager.

## bot actors

Each bot actor wraps one running bot runtime.

Core rule:

```text
BotRuntime = real bot logic, plain Python
Ray BotActor = thin wrapper around BotRuntime
```

Manual mode:

```text
runtime = BotRuntime(exec_network, bot_id)
runtime.init()
runtime.run()
```

Notebook coding/testing uses manual mode first. This keeps bot code testable
without Ray.

Ray mode:

```text
actor = BotActor.remote(exec_network, bot_id)
actor.run.remote()
```

Live managed runs use Server and Ray.

Hard rule:

```text
1 Ray actor = 1 process = 1 bot runtime = 1 bot SQLite DB
```

Actor launch:

```text
Server/BotManager has nuubot from nuubot_setup()
bot_id = server DB sequence for <exec_network>_bot
db_path = workspace/db/<exec_network>_bot_<bot_id>.db
start Ray actor with exec_network and bot_id
```

Actor init:

```text
receive exec_network and bot_id
runtime = BotRuntime(exec_network, bot_id)
runtime.init()
runtime.run()
```

The bot actor keeps runtime state in memory while running and writes durable
bot evidence to its own SQLite file. Server DB access is short open/read/close
or open/write/close for sequence, meta, and server state only.

`BotRuntime.init()`:

- checks server infra/meta once and fails loud if unavailable.
- creates the bot SQLite file and tables if missing.
- reads required server meta and snapshots it into the bot DB.
- loads the `bot` row, accounts, positions, orders, fills, and free-form
  state.
- composes signaler, risk, executor, bot-local data feeds, and clock.

Per-bot DB tables start with:

```text
bot
account
bot_command
bot_event
bot_state
exchange_meta_snapshot
position
order
fill
```

Do not add `bot_id` to every per-bot table. The SQLite file name and server
sequence identify the bot.

## control

Ray mode uses actor methods as the primary command path.

Manual mode has no actor handle, so it uses the bot-local DB:

```text
operator/CLI/API opens workspace/db/<exec_network>_bot_<bot_id>.db
insert bot_command
close

BotRuntime polls bot_command during its loop
BotRuntime writes bot_event, bot_state, and heartbeat
```

There is no shared command table and no Redis command bus.

## websockets

Live bots own their websocket/feed clients first.

For 5-10 live bots, this keeps start/stop/restart isolated and avoids hidden
shared infrastructure. A shared DataEngine is allowed later only after exchange
limits, bandwidth, CPU, or fanout prove per-bot feeds are not enough.

## sweep tasks

Each sweep task is stateless from Ray's point of view.

Task init:

```text
sweep_id or sweeprun_id = server DB sequence
db_path = workspace/db/sweep_<id>.db or workspace/db/sweeprun_<id>.db
create SQLite DB and tables if missing
load historical data
run the parameter set
write final result
```

For reruns, delete the sweep/sweeprun SQLite file and run again. Do not migrate
old sweep runtime state.

## server DB

The server DB is the only persistent shared DB.

It owns:

- `server_sequence`.
- `server_state`.
- exchange meta.

Access rule:

```text
open connection
read/write
close connection
```

Do not keep a long-lived server DB connection inside bot actors or sweep tasks.

## non-goals

- No Postgres process.
- No DB compatibility layer.
- No central long-lived DB session manager.
- No custom multiprocessing layer beside Ray.
- No Ray-owned Server process.
- No Redis.
- No shared websocket server first.
