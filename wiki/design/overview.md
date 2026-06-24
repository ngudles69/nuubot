---
title: design overview
created: 2026-06-20
updated: 2026-06-21
type: wiki
status: active
tags: [design, overview]
---

# design overview

## files

1. [Objects](objects/AGENTS.md): object boundaries and contracts.
2. [Runtime](objects/runtime.md): master composer, loop, clock, command table,
   telemetry.
3. [State](state.md): datastore, botrun state, exchange meta, reconciliation.
4. [Strategy](strategy.md): risk, signalers, executors.
5. [Sweeps](sweeps.md): sweep, sweeprun, botrun, parameter shape.

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
- Keep each bot as a standalone unit with its own local command surface.

## decisions

- Use a Python package folder for real code.
- Run a bot as `uv run python -m nuubot.core.runtime -f <paramfile>`.
- Run a sweep as `uv run python -m nuubot.core.sweep -f <paramfile>`.
- Use TOML for `<paramfile>`.
- Treat credentials as part of config for now.
- Persist config snapshots with credentials redacted or omitted.
- Likely use `async_hyperliquid` for Hyperliquid exchange access.
- Use SQLAlchemy for datastore access.
- Current CLI/datastore prototype uses local SQLite under `workspace/db`.
- PostgreSQL remains the intended later production engine.
- `datastore.py` only owns database infrastructure:
  - connect
  - disconnect
  - create database if missing
  - create all tables if missing
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
| `Runtime` | [objects/runtime.md](objects/runtime.md) | Master composer. |
| `Config` | [objects/config.md](objects/config.md) | Simple validated config holder. |
| `Account` | [objects/account.md](objects/account.md) | Exchange account composer, simulator, ledger. |
| `Ledger` | [objects/ledger.md](objects/ledger.md) | Position, order, fill collection. |
| `Datastore` | [objects/datastore.md](objects/datastore.md) | PostgreSQL and SQLAlchemy boundary. |
| `WsData` / `FileData` | [objects/data.md](objects/data.md) | Live websocket data and historical file data. |
| `Signaler` | [objects/signaler.md](objects/signaler.md) | Indicators and signal consensus. |
| `Executor` | [objects/executor.md](objects/executor.md) | Strategy execution logic. |
| `Cli` | [objects/cli.md](objects/cli.md) | Bot manager program. |
| `CommandServer` | [objects/command.md](objects/command.md) | Runtime command-table owner. |

## component map

```text
Sweep -> Sweeprun -> Botrun config -> Runtime/Bot
Cli -> Datastore -> bot rows
Cli -> Runtime process
Cli -> command table
Runtime/Bot -> Clock -> ExchangeData snapshot
Runtime/Bot -> CommandServer -> command table
Runtime/Bot -> Risk -> Signaler -> Executor
Executor -> Account -> Ledger -> Position -> Order -> Fill
Runtime/Domain objects -> Datastore
Frontend later -> Datastore + per-bot CommandServer
```

## connection rule

Objects are independent except for their defined child objects and allowed
connections. If code needs a new connection, ask the user and update the object
design file before using it.

## non-goals first

- No central server.
- No frontend implementation.
- No runtime-forced risk exit yet.
- No executor action-request framework.
- No protocol/base class hierarchy unless real code needs it.
- No Alembic/migration layer yet.
- No multiple runtime classes for mainnet/testnet/simnet/backtest yet.
- No freeze command yet.
- No full telemetry framework yet.
- No simulator implementation yet.
- No live trading implementation yet.

## proof needs

- `uv run python -m nuubot.core.runtime -f <paramfile>` starts a runnable bot
  scaffold.
- DB tables are created if missing.
- Bot row is written.
- Redacted config snapshot is stored with the bot row.
- Runtime writes PID, run token, status, and heartbeat to the bot row.
- Runtime polls the command table for commands.
- Port is released on terminal stop/error.
- Dirty state is visible if cleanup fails.
- `Risk.score()` exists and returns a score.
- A simple executor can call risk, signaler, exchange account, and position
  state methods without framework plumbing.
