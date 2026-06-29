---
title: roadmap
created: 2026-06-20
updated: 2026-06-20
type: project
status: active
tags: [roadmap]
---

# nuubot project plan

This file is the project plan.

## status markers

- `[ ]` not started
- `[o]` in progress
- `[x]` done this session only

## rules

- Keep tasks short.
- Put durable facts and decisions in `wiki/**`.
- Put proof notes in `.project/**` or `.research/**` while they are active.
- Treat this file as working state. It can be out of date.
- Remove old done items after they are no longer useful for current work.

## project plan

### [x] 1. Runtime direction

  - [x] 1.1 Lock SQLite-only datastore.
  - [x] 1.2 Lock one bot runtime to one bot SQLite DB.
  - [x] 1.3 Lock BotRuntime as plain Python runnable without Ray.
  - [x] 1.4 Lock Ray as optional live managed process layer.
  - [x] 1.5 Lock notebooks as the code/test path.
  - [x] 1.6 Lock Server + Ray as the live run path.
  - [x] 1.7 Lock bot-local websocket/feed clients first.
  - [x] 1.8 Lock no Redis and no shared websocket server first.

### [o] 2. Datastore schemas

  - [ ] 2.1 Create server tables: `server_sequence`, `server_state`,
    `exchange_meta`.
  - [ ] 2.2 Remove central bot/sweep/sweeprun catalog tables.
  - [ ] 2.3 Create bot tables: `bot`, `account`, `bot_command`, `bot_event`,
    `bot_state`, `exchange_meta_snapshot`, `position`, `order`, `fill`.
  - [ ] 2.4 Create sweep tables: `sweeps`, `sweepruns`.
  - [ ] 2.5 Remove redundant `bot_id` from per-bot position/order/fill tables.
  - [ ] 2.6 Add atomic server sequence allocation with `BEGIN IMMEDIATE`.
  - [ ] 2.7 Prove table creation and sequence allocation with a temp SQLite
    check.

### [o] 3. Datastore behavior

  - [ ] 3.1 Clean up datastore module boundaries around server DB, bot DB, and
    sweep DB.
  - [ ] 3.2 Keep server tables separate from bot tables in schema creation.
  - [ ] 3.3 Enforce short open/read-write/close access for `server.db`.
  - [ ] 3.4 Use DB file existence as bot/sweep/sweeprun existence truth.
  - [ ] 3.5 Add focused tests for server sequence, meta refresh, bot DB table
    creation, and file discovery.

### [o] 4. Nuubot setup

  - [ ] 4.1 Rejig `nuubot_setup()` into the single shared setup entrypoint.
  - [ ] 4.2 Make create-vs-load behavior explicit for server DB and meta.
  - [ ] 4.3 Keep exchange meta fetch/update inside setup when missing or older
    than 24 hours.
  - [ ] 4.4 Prove setup is idempotent for repeated process-local calls.

### [o] 5. Bot create/load/setup

  - [ ] 5.1 Add `create_botrow_via_file(path)`.
  - [ ] 5.2 Add `create_botrow_via_template(template)`.
  - [ ] 5.3 Make file and template creation share one implementation path.
  - [ ] 5.4 Add `bot_setup(exec_network, bot_id)`.
  - [ ] 5.5 Load bot row, bot state, accounts, positions, orders, and fills.
  - [ ] 5.6 Read required meta from `server.db`, fail loud if missing, and
    write a local bot DB meta snapshot.
  - [ ] 5.7 Prove notebooks can pass a loaded template directly and live/sim
    creation can pass a file path.

### [o] 6. Server, managers, Ray, and CLI

  - [ ] 6.1 Add Server as the parent/control process.
  - [ ] 6.2 Add BotManager for bot create/load/clone/delete/view/ping/status.
  - [ ] 6.3 Add SweepManager for sweep create/run/view/status.
  - [ ] 6.4 Add Server API routes as thin adapters.
  - [ ] 6.5 Add `ray` as a project dependency and install with `rtk uv sync`.
  - [ ] 6.6 Start live managed bot actors through BotManager using Ray.
  - [ ] 6.7 Submit sweep tasks through SweepManager using Ray.
  - [ ] 6.8 Keep API/routes tiny: validate input, call one manager/helper,
    return result.
  - [ ] 6.9 Keep CLI as a thin operator helper over the same manager/helper
    functions.
  - [ ] 6.10 Prove one local Ray bot actor creates one bot DB and returns status.

### [o] 7. Bot-local data feeds

  - [ ] 7.1 Make `WsData` own bot-local websocket/feed clients.
  - [ ] 7.2 Add lazy websocket connection on bot data start.
  - [ ] 7.3 Add reconnect/status handling inside the bot-local feed object.
  - [ ] 7.4 Expose latest BBO/candle snapshots to Runtime.
  - [ ] 7.5 Keep shared DataEngines deferred until measured need.

### [o] 8. Bot runtime and lifecycle

  - [ ] 8.1 Add plain Python `BotRuntime(exec_network, bot_id)`.
  - [ ] 8.2 Make notebooks run BotRuntime directly without Ray.
  - [ ] 8.3 Runtime setup checks server infra/meta once and fails loud if
    unavailable.
  - [ ] 8.4 Runtime setup calls `bot_setup()` once.
  - [ ] 8.5 Runtime composes signaler, risk, executor, data, and clock after
    bot state is loaded.
  - [ ] 8.6 Add bot-local `bot_command`, `bot_event`, and `bot_state` handling.
  - [ ] 8.7 Add lifecycle commands: start, stop, freeze/exit, status.
  - [ ] 8.8 Prove direct notebook runtime and Ray actor runtime share the same
    BotRuntime path.

### [o] 9. Sweep

  - [ ] 9.1 Implement a basic EMA-cross sweep.
  - [ ] 9.2 Use EMA-cross sweep as the template for future sweeps.
  - [ ] 9.3 Prove sweep runs through SweepManager and Ray task path.

## project / tooling
