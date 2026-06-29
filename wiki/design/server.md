---
title: server design
created: 2026-06-29
updated: 2026-06-29
type: wiki
status: active
tags: [design, server, managers, ray, data]
---

# server design

## purpose

Server is the admin/API/control process.

It owns API routes, managers, server DB setup, and operator-facing
coordination. It uses Ray to run managed bot actors and sweep tasks.

Ray is not the Server. Ray is the worker/process substrate under Server.

## shape

```text
Server process
  API routes
  BotManager
  SweepManager
  Nuubot shared setup
  Ray client/use

Ray runtime
  bot actors wrapping BotRuntime
  sweep tasks

CLI
  thin operator helper

Notebook/manual mode
  BotRuntime directly
```

## ownership

Server owns:

- API route registration and request validation.
- `nuubot_setup()` and shared setup/control-plane initialization.
- `server.db`; see [Server DB](server-db.md).
- `BotManager`.
- `SweepManager`.
- Server lifecycle: start, stop, status, health.
- Ray initialization/use from the control side.

Server does not own bot trading logic or bot websocket feeds.

BotManager owns:

- see [BotManager](botmanager.md).

SweepManager owns:

- see [SweepManager](sweepmanager.md).

Runtime owns:

- one bot loop in plain Python.
- bot setup sequence after manual start or Ray actor start.
- signaler/risk/executor/account/data/clock composition for that bot.
- bot-local websocket/feed clients for live modes.

CLI owns only:

- parsing operator commands.
- calling Server/BotManager/SweepManager helper functions.
- printing results.

CLI must not own datastore logic, Ray lifecycle, bot creation logic, sweep
execution logic, runtime logic, websocket infra, or API business behavior.

## API rule

See [Server API](server-api.md).

API/routes are thin adapters:

```text
route validates input
route calls one manager/helper function
route returns the result
```

Do not let route files become display builders, business logic collectors, or
script dumps.

## Ray rule

Ray owns bot and sweep workers only.

```text
Server -> BotManager -> Ray bot actor
Server -> SweepManager -> Ray sweep task
```

Do not make Server a Ray actor first.

BotRuntime must also run without Ray for notebook coding/testing.

Live managed runs use Server and Ray.

## websocket rule

Live bots own their own websocket/feed clients first.

Do not build a shared websocket server first. Do not use Redis for feed or
command fanout. Add shared DataEngines only after per-bot feeds fail against a
measured exchange limit, bandwidth, CPU, or fanout problem.

## nuutrader6 lesson

Keep the useful shape from `nuutrader6`:

```text
Server owns BotManager, SweepManager, and DataEngine.
```

Improve it here:

- replace subprocess bot spawning with Ray actors.
- replace Redis command nudges with Ray actor calls.
- keep API routes thin.
- keep bot-local state in one bot SQLite DB.
- keep bot-local websocket/feed clients first.
- keep CLI as a helper, not a giant script collector.
