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

1. [Runtime](runtime.md): standard bot loop, clock, command server, telemetry.
2. [State](state.md): datastore, botrun state, exchange meta, reconciliation.
3. [Strategy](strategy.md): risk, signalers, executors.
4. [Backtest and Simulator](backtest-simulator.md): live/paper/backtest binding,
   simulator hooks.
5. [Frontend](frontend.md): datastore viewer and command boundary.
6. [Sweeps](sweeps.md): sweep, sweeprun, botrun, parameter shape.
7. [ER Diagram](design.html): database design diagram.
8. [Component Map](process.html): high-level component and contract map.

## problem

Build a clean algo-trading bot runtime that can run a simple grid bot first,
without recreating the over-built shape of `nuutrader6`.

## goal

- Create capital-protective, profitable algo-trading bots.
- The top-level `Bot` file should read almost like BlackBot: clear sequence,
  obvious strategy flow, minimal ceremony.
- Complexity is allowed, but it must live inside the object that owns it.
- Keep risk first-class.
- Keep simulator first-class for paper/backtest work.
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
- Use PostgreSQL with SQLAlchemy.
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

## first-class objects

- `Bot`: runtime coordinator.
- `ConfigData`: TOML-loaded config, including credentials.
- `Datastore`: DB infrastructure only.
- `CommandServer`: per-bot `aiohttp` command surface.
- `Clock`: runtime time source.
- `ExchangeData` / `ExchangeWsData`: BBO and candle data source.
- `ExchangeMeta`: exchange reference metadata.
- `ExchangeAccount`: account, balances, orders, positions, exchange submits.
- `Risk`: first-class risk scorer.
- `Signaler`: signal source.
- `Executor`: free-form execution object.
- `Cloid`: client order id helper copied from `nuutrader6` first.
- `Position`: accounting parent object.
- `Order`: order intent/evidence object.
- `Fill`: fill evidence object.
- `Event`: notable bot event for user/frontend display.
- `Simulator`: first-class standalone module for paper/backtest behavior.

## non-goals first

- No central server.
- No DB command queue.
- No frontend implementation.
- No stale port cleanup CLI.
- No runtime-forced risk exit yet.
- No executor action-request framework.
- No protocol/base class hierarchy unless real code needs it.
- No Alembic/migration layer yet.
- No multiple runtime classes for live/paper/backtest yet.
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
- Command server binds a DB-assigned localhost port.
- Command server responds to `GET /ping`.
- Command server responds to `GET /status`.
- Port is released on terminal stop/error.
- Dirty state is visible if cleanup fails.
- `Risk.score()` exists and returns a score.
- A simple executor can call risk, signaler, exchange account, and position
  state methods without framework plumbing.
