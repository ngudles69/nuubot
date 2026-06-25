---
title: nuubot object
created: 2026-06-24
updated: 2026-06-24
type: wiki
status: active
tags: [design, objects, infra]
---

# nuubot object

## purpose

Nuubot owns shared infrastructure for programs that need workspace services.

It keeps config/datastore setup out of Runtime so Runtime can focus on the bot
loop.

Allowed composed objects:

- `Config`
- `Datastore`

## interfaces

External commands:

- `Nuubot.setup(path="workspace/config/config.toml")`
- `nuubot_setup(path="workspace/config/config.toml")`
- `stop()`

Nuubot outputs:

- `nuubot.config`
- `nuubot.datastore`

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `setup(path)` | Workspace config path. | Ready Nuubot. | Loads Config, initializes Datastore, and returns the infra owner. Fails loud if either step fails. |
| `nuubot_setup(path)` | Workspace config path. | Ready Nuubot. | Thin module-level call to `Nuubot.setup()` for simple program entrypoints. |
| `stop()` | Ready Nuubot. | Stopped infra. | Stops owned infrastructure resources. |

## processing

Internal functions:

- load workspace config.
- initialize datastore.
- expose infra handles.
- stop infra handles.

## key helpers

- none.

## notes

- Nuubot is not the trading runtime.
- Runtime may use `nuubot.config` and `nuubot.datastore`, but the loop stays in
  Runtime.
- Do not add service registries or generic dependency containers.
