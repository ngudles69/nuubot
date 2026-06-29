---
title: nuubot object
created: 2026-06-24
updated: 2026-06-29
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
- server SQLite DB setup

## interfaces

External commands:

- `Nuubot.setup(path="workspace/config/config.toml")`
- `nuubot_setup(path="workspace/config/config.toml")`
- `stop()`

Nuubot outputs:

- `nuubot.config`
- server DB path/helper
- `nuubot.data_network`
- `nuubot.exec_network`

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `setup(path)` | Workspace config path. | Ready Nuubot. | Loads Config, creates/opens the server SQLite DB, refreshes exchange meta if missing or older than 24 hours, and returns the infra owner. Fails loud if setup fails. |
| `nuubot_setup(path)` | Workspace config path. | Ready Nuubot. | Thin module-level call to `Nuubot.setup()` for simple program entrypoints. |
| `data_network` | Ready Nuubot. | Data network value. | Derived from `nuubot.config.general.mode`. Not a config-file field. |
| `exec_network` | Ready Nuubot. | Execution network value. | Derived from `nuubot.config.general.mode`. Not a config-file field. |
| `stop()` | Ready Nuubot. | Stopped infra. | Stops owned infrastructure resources. |

## processing

Internal functions:

- load workspace config.
- create the persistent server SQLite DB if missing.
- create server tables if missing.
- if `exchange_meta` is missing or older than 24 hours, fetch all Hyperliquid
  meta using adapted `nuutrader6` logic and write it to the server DB.
- derive runtime-facing networks from config mode.
- expose infra handles.
- stop infra handles.

## key helpers

- none.

## notes

- Nuubot is not the trading runtime.
- Runtime may use `nuubot.config` and short server DB helpers, but the loop and
  local DB handle stay with the bot actor/task.
- Do not add service registries or generic dependency containers.
