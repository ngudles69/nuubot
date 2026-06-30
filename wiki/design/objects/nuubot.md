---
title: nuubot object
created: 2026-06-24
updated: 2026-06-30
type: wiki
status: active
tags: [design, objects, infra]
---

# nuubot object

## purpose

Nuubot owns shared setup for programs that need workspace services.

It keeps server DB and meta setup out of Runtime so Runtime can focus on the
bot loop.

Allowed composed objects:

- `Config`
- `Datastore`
- server DB name

## interfaces

External commands:

- `Nuubot.setup(path="workspace/config/config.toml")`
- `nuubot_setup(path="workspace/config/config.toml")`
- `stop()`

Nuubot outputs:

- `nuubot.config`
- `nuubot.datastore`
- `nuubot.server_db`

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `setup(path)` | Workspace config path. | Ready Nuubot. | Loads Config, creates the datastore with the configured DB root, creates `server.db` tables, refreshes exchange meta if missing or older than 24 hours, and returns the infra owner. Fails loud if setup fails. |
| `nuubot_setup(path)` | Workspace config path. | Ready Nuubot. | Thin module-level call to `Nuubot.setup()` for simple program entrypoints. |
| `stop()` | Ready Nuubot. | Stopped infra. | Stops owned infrastructure resources. |

## processing

Internal functions:

- load workspace config.
- create `Datastore` with `workspace/db` as the DB root.
- create the persistent server SQLite DB if missing.
- create server tables if missing.
- if `meta` is missing or older than 24 hours, fetch all Hyperliquid
  meta and write it to the server DB.
- expose infra handles.
- stop infra handles.

## key helpers

- none.

## notes

- Nuubot is not the trading runtime.
- Runtime may use `nuubot.config` and datastore verbs, but the loop and
  local DB handle stay with the bot actor/task.
- Do not add service registries or generic dependency containers.
