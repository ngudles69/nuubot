---
title: cli object
created: 2026-06-24
updated: 2026-06-29
type: wiki
status: active
tags: [design, objects, cli, bot-manager]
---

# cli object

## purpose

CLI is a thin operator helper.

It parses user commands, calls the same Server/BotManager/SweepManager helper
functions used by API routes, and prints results.

Allowed connections:

- `Nuubot`
- Server/BotManager/SweepManager helper functions

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `create(config_path)`
- `delete(bot_id)`
- `clone(source_bot_id)`
- `start_bot(bot_id)`
- `stop_bot(bot_id)`
- `view(bot_id=None)`
- `ping(bot_id)`

Future command:

- `freeze(bot_id)` is intentionally deferred.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | CLI args/config. | Initialized CLI. | Parses command args. Does not start bots. |
| `start()` | Initialized CLI. | Ready CLI. | Calls `Nuubot.setup()` and prepares command execution. |
| `stop()` | Ready CLI. | Stopped CLI. | Closes CLI-owned resources. Does not stop running bots unless command asked for it. |
| `create(config_path)` | Bot config/template path. | Configured bot row. | Calls BotManager. |
| `delete(bot_id)` | Existing bot id. | Deleted bot row/config. | Calls BotManager. |
| `clone(source_bot_id)` | Existing bot id. | New configured bot row. | Calls BotManager. |
| `start_bot(bot_id)` | Existing bot id. | Running bot. | Calls BotManager. |
| `stop_bot(bot_id)` | Existing/running bot id. | Stop command. | Calls BotManager. |
| `view(bot_id=None)` | Optional bot id. | Bot row(s). | Calls BotManager. |
| `ping(bot_id)` | Bot id. | Liveness result. | Calls BotManager. |
| `freeze(bot_id)` | Existing bot id. | Deferred. | Commented/deferred until runtime key functionality is clean. |

## processing

Internal functions:

- parse CLI args.
- call Server/BotManager/SweepManager helper functions.
- fail loud on invalid status transitions.

Command shape:

```text
nuubot-cli create -f path/filename
nuubot-cli delete <bot_id>
nuubot-cli clone <source_bot_id>
nuubot-cli start <bot_id>
nuubot-cli stop <bot_id>
nuubot-cli view [bot_id]
nuubot-cli ping <bot_id>
```

`-f` / `--file` means bot config/template file path.

## notes

- CLI must not own datastore logic, bot creation logic, worker lifecycle logic,
  sweep execution logic, runtime logic, or API business behavior.
- CLI is not a giant collector of scripts.
- Runtime CommandServer manages commands inside one bot runtime.
- No freeze implementation until approved later.
- Keep command names boring and direct.
