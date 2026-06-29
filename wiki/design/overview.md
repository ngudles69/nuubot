---
title: design overview
created: 2026-06-20
updated: 2026-06-29
type: wiki
status: active
tags: [design, overview]
---

# design overview

## files

1. [Objects](objects/AGENTS.md): object boundaries and contracts.
2. [Runtime](objects/runtime.md): master composer, loop, clock, command path,
   telemetry.
3. [State](state.md): SQLite state, bot state, exchange meta,
   reconciliation.
4. [Server](server.md): Server, WebGUI, managers, CLI helper, Ray ownership.
5. [Server DB](server-db.md): Server DB ownership and access rules.
6. [BotManager](botmanager.md): bot control-plane ownership.
7. [SweepManager](sweepmanager.md): sweep control-plane ownership.
8. [Server API](server-api.md): route rules and route-list reference.
9. [WebGUI](webgui.md): FastHTML operator UI.
10. [DataEngines](dataengines.md): optional shared websocket/feed engines.
11. [Ray](ray.md): Ray actor/task process model.
12. [Strategy](strategy.md): risk, signalers, executors.
13. [Sweeps](sweeps.md): sweep, sweeprun, bot config, parameter shape.

## problem

Build a clean algo-trading bot runtime that can run a simple grid bot first,
without recreating the over-built shape of `nuutrader6`.

## goal

- Create capital-protective, profitable algo-trading bots.
- The top-level `Bot` file should read almost like BlackBot: clear sequence,
  obvious strategy flow, minimal ceremony.
- Complexity is allowed, but it must live inside the object that owns it.
- Keep risk first-class.
- Keep simulator first-class for simnet/backtest work.
- Keep executors free-form and simple.
- Keep datastore infrastructure separate from domain persistence operations.
- Keep each running bot/sweep/sweeprun as a standalone unit with its own SQLite
  file.
- Keep one persistent server SQLite DB for seq numbers, server state, and
  exchange meta.
- Keep Server as the admin/API/control process that owns managers.
- Keep FastHTML WebGUI inside Server as the operator display and command
  surface.
- Keep BotRuntime runnable directly from notebooks without Ray.
- Use Ray as the live managed process layer for bot actors and sweep tasks.
- Keep live bot websocket/feed clients bot-local first.

## decisions

- Use a Python package folder for real code.
- Code/test bots through notebooks using direct BotRuntime.
- Run live managed bots through Server/BotManager using Ray actor launch.
- Run a sweep through Server/SweepManager using Ray task launch.
- Start Server and WebGUI with `uv run python -m nuubot.server`.
- CLI is a thin operator helper over the same manager/helper functions used by
  API routes.
- Use FastHTML for the WebGUI. Keep it in `nuubot/webgui/**`, not as a peer
  package.
- Use TOML for `<paramfile>`.
- Treat credentials as part of config for now.
- Persist config snapshots with credentials redacted or omitted.
- Likely use `async_hyperliquid` for Hyperliquid exchange access.
- Use SQLAlchemy Core/DDL for SQLite when it keeps table creation and writes
  simple; do not keep long-lived server DB sessions or ORM object graphs.
- SQLite is the datastore target.
- Do not add Postgres, migration, dual-read/write, or compatibility paths.
- `nuubot_setup()` initializes only the persistent server SQLite DB and loads
  meta.
- `nuubot_setup()` refreshes exchange meta when the table is empty or the newest
  row is older than 24 hours.
- Server/control-plane setup calls `nuubot_setup()` once.
- Runtime setup checks server infra/meta once and calls `bot_setup(exec_network,
  bot_id)` once.
- `bot_setup()` creates/opens the per-bot SQLite DB and loads the bot row,
  accounts, positions, orders, fills, and free-form state.
- Each bot actor, sweep task, and sweeprun task initializes its own SQLite DB
  file and tables if missing.
- Per-bot DB tables do not repeat `bot_id`; the SQLite file is the bot
  boundary.
- Server DB access is open connection, read/write, close.
- Instance DB access is owned by the running actor/task.
- Ray is first-class:
  - BotRuntime is plain Python.
  - live managed bots are stateful Ray actor wrappers around BotRuntime.
  - sweeps are stateless Ray tasks.
  - add `ray` as a project dependency and install with `rtk uv sync`.
- Ray is not the Server. Server uses Ray.
- Shared DataEngines are deferred until per-bot feeds fail against a measured
  exchange limit, bandwidth, CPU, or fanout problem.
- API/routes validate input, call one manager/helper function, and return the
  result.
- Datastore operations belong to the domain objects that own the meaning.
- Use explicit persistence verbs:
  - `insert_state()`
  - `select_state()`
  - `update_state()`
  - `delete_state()`
- Do not use upsert for trading evidence.
- `blackbot.py` belongs in `.research/**` as reference/scaffold material, not
  as production runtime code.
- `workspace/data/**` holds historical data; current data is Binance historical
  data for backtesting.
- Target package shape removes `nuubot/core`:
  - `nuubot/cli`
  - `nuubot/runtime`
  - `nuubot/command`
  - `nuubot/config`
  - `nuubot/account`
  - `nuubot/data`
  - `nuubot/datastore`
  - `nuubot/signaler`
  - `nuubot/executor`
  - `nuubot/sweep`
- Current implementation still uses `nuubot/core` until the package move is
  performed.

## object map

| Object | File | Role |
| --- | --- | --- |
| `Nuubot` | [objects/nuubot.md](objects/nuubot.md) | Shared infra owner. |
| `Runtime` | [objects/runtime.md](objects/runtime.md) | Master composer. |
| `Config` | [objects/config.md](objects/config.md) | Simple validated config holder. |
| `Account` | [objects/account.md](objects/account.md) | Exchange account composer, simulator, ledger. |
| `Ledger` | [objects/ledger.md](objects/ledger.md) | Position, order, fill collection. |
| `Datastore` | [objects/datastore.md](objects/datastore.md) | SQLite boundary. |
| `Server` | [server.md](server.md) | Parent/control process and infra owner. |
| `Server DB` | [server-db.md](server-db.md) | Shared SQLite seq/meta/server-state DB. |
| `BotManager` | [botmanager.md](botmanager.md) | Bot create/load/start/stop/status owner. |
| `SweepManager` | [sweepmanager.md](sweepmanager.md) | Sweep create/run/status owner. |
| `Server API` | [server-api.md](server-api.md) | Thin API route boundary. |
| `WebGUI` | [webgui.md](webgui.md) | FastHTML display and command-control UI. |
| `DataEngines` | [dataengines.md](dataengines.md) | Optional shared live feed services. |
| `Ray` | [ray.md](ray.md) | Actor/task process layer. |
| `WsData` / `FileData` | [objects/data.md](objects/data.md) | Live websocket data and historical file data. |
| `Signaler` | [objects/signaler.md](objects/signaler.md) | Indicators and signal consensus. |
| `Executor` | [objects/executor.md](objects/executor.md) | Strategy execution logic. |
| `Cli` | [objects/cli.md](objects/cli.md) | Thin operator helper. |
| `CommandServer` | [objects/command.md](objects/command.md) | Runtime command-table owner. |

## component map

```text
Sweep -> Sweeprun -> Bot config -> Runtime/Bot
Program entrypoint -> Nuubot -> Config + Server DB
Server/WebGUI entrypoint -> nuubot_setup -> BotManager -> Ray bot actor
Server -> SweepManager -> Ray sweep task
API route -> Manager/helper function -> result
Cli -> Manager/helper function -> result
Bot actor -> bot SQLite DB
Sweep task -> sweep/sweeprun SQLite DB
Notebook -> BotRuntime -> bot SQLite DB
Runtime/Bot actor -> short server DB check/meta read
Runtime/Bot actor -> bot_setup -> Bot row + Accounts + Positions + Orders + Fills + State
Runtime/Bot -> Clock -> ExchangeData snapshot
Runtime/Bot -> CommandServer -> Ray actor command or bot-local command
Runtime/Bot -> Risk -> Signaler -> Executor
Executor -> Account -> Ledger -> Position -> Order -> Fill
Runtime/Domain objects -> instance SQLite DB
WebGUI -> DB file discovery + per-instance SQLite read model
```

## connection rule

Objects are independent except for their defined child objects and allowed
connections. If code needs a new connection, ask the user and update the object
design file before using it.

## parameter order

When an object receives shared infra, identity, and qualifiers, pass them in
this order:

```text
nuubot
object id
qualifiers, callbacks, or options
```

Example:

```text
CommandServer(nuubot, bot_id, runtime_callbacks)
```

## non-goals first

- No separate frontend app or JS build system.
- No runtime-forced risk exit yet.
- No executor action-request framework.
- No protocol/base class hierarchy unless real code needs it.
- No Alembic/migration layer.
- No Postgres.
- No custom process manager beside Ray.
- No CLI-owned bot/sweep/datastore business logic.
- No shared websocket server first.
- No Redis.
- No multiple runtime classes for mainnet/testnet/simnet/backtest yet.
- No freeze command yet.
- No full telemetry framework yet.
- No simulator implementation yet.
- No live trading implementation yet.

## proof needs

- Notebook can start direct BotRuntime without Ray.
- CLI/Ray starts a runnable bot actor for managed live runs.
- Ray can start a bot actor.
- Ray can start sweep tasks.
- Server SQLite DB is created if missing by `nuubot_setup()`.
- Bot/sweep/sweeprun SQLite DB files are created if missing by actor/task init.
- Bot DB file existence proves the bot exists.
- Redacted config snapshot is stored with the bot row.
- Runtime writes status and heartbeat evidence to its bot DB.
- Dirty state is visible if cleanup fails.
- `Risk.score()` exists and returns a score.
- A simple executor can call risk, signaler, exchange account, and position
  state methods without framework plumbing.
