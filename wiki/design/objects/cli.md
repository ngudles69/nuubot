---
title: cli object
created: 2026-06-24
updated: 2026-06-24
type: wiki
status: active
tags: [design, objects, cli, bot-manager]
---

# cli object

## purpose

CLI is the bot manager program.

It manages configured bot rows, starts/stops bot runtimes, writes command rows,
and shows bot state.

Allowed connections:

- `Nuubot`
- `Datastore` through `Nuubot`
- runtime process launcher
- command table

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
| `create(config_path)` | Bot config/template path. | Configured bot row. | Inserts a new bot row with config and resets runtime fields. Status becomes `configured`. |
| `delete(bot_id)` | Existing bot id. | Deleted bot row/config. | Allowed only when bot status is `configured`. Fails loud otherwise. |
| `clone(source_bot_id)` | Existing bot id. | New configured bot row. | Copies source config into a new bot row and sets status to `configured`. Runtime fields are reset. |
| `start_bot(bot_id)` | Existing bot id. | Running bot. | Starts runtime for a configured/stopped bot and records runtime identity/port when available. |
| `stop_bot(bot_id)` | Existing/running bot id. | Stop command row. | Inserts a stop command for the runtime to claim. Fails loud if the bot is not commandable. |
| `view(bot_id=None)` | Optional bot id. | Bot row(s). | Shows bot config/status/runtime fields. Does not mutate state. |
| `ping(bot_id)` | Bot id. | Liveness result. | Reads bot row, heartbeat freshness, and PID evidence. Does not send an HTTP request. |
| `freeze(bot_id)` | Existing bot id. | Deferred. | Commented/deferred until runtime key functionality is clean. |

## processing

Internal functions:

- parse CLI args.
- initialize Nuubot infra.
- load bot config through `Config`.
- insert/delete/clone bot rows through SQLAlchemy sessions.
- spawn runtime process.
- insert command rows for runtime commands.
- check bot PID/heartbeat evidence for ping/status.
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

## key helpers

- bot status validator.
- config loader.
- bot row resetter.
- command row writer.
- runtime process launcher.
- bot row formatter.
- pid/heartbeat checker.

## notes

- CLI owns bot catalog operations. Runtime does not.
- CLI can manage many bots. Runtime CommandServer manages command rows for one
  running bot.
- `create`, `delete`, and `clone` must reset runtime-only fields.
- `delete` is allowed only for `configured` bots.
- No freeze implementation until approved later.
- Keep command names boring and direct.
