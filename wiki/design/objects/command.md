---
title: command server object
created: 2026-06-24
updated: 2026-06-29
type: wiki
status: active
tags: [design, objects, command, runtime]
---

# command server object

## purpose

CommandServer lives in `command.py`.

It is the runtime-side command owner inside BotRuntime.

Ray mode uses Ray actor calls as the first command path. Manual/notebook mode
has no actor handle, so CommandServer polls the bot-local `bot_command` table.
Both modes write bot-local events, state, and heartbeat.

It is not an aiohttp server.

Allowed connections:

- `Nuubot`
- Runtime callbacks for `status()` and `exit(reason)`
- instance SQLite DB

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `heartbeat()`
- `next_command()`
- `execute(command)`

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Nuubot, bot id, runtime callbacks. | Initialized CommandServer. | Creates runtime `run_token`, records runtime identity when available, and writes startup status to the bot DB. If that write fails, runtime startup fails. |
| `start()` | Initialized CommandServer. | Running CommandServer. | Starts command/heartbeat state. Does not execute commands until Runtime enters normal flow. |
| `stop()` | Running CommandServer. | Stopped CommandServer. | Writes stopped/terminal ownership state where `bot_id` and `run_token` match. |
| `heartbeat()` | Current runtime ownership. | Updated bot row. | Updates `last_seen_at` only where `bot_id` and `run_token` match. |
| `next_command()` | Runtime command state. | Pending command or none. | In Ray mode, returns actor-delivered command. In manual mode, polls the bot-local `bot_command` table. |
| `execute(command)` | Runtime command. | Command result. | Executes supported runtime command and writes done/error audit when needed. |

Supported runtime commands first:

- `kill`
- `stop`
- `status`

Deferred:

- `freeze`

## processing

Internal functions:

- generate `run_token`.
- read runtime identity when available.
- write runtime ownership to bot row.
- update heartbeat.
- read actor-local or bot-local DB command state.
- dispatch command to runtime callback.
- write command result.

## key helpers

- ownership writer.
- heartbeat writer.
- actor command reader.
- command result writer.
- command dispatcher.

## notes

- Constructor/input order is `nuubot`, then object id, then qualifiers or
  callbacks.
- `kill` exits the runtime immediately and does not cancel orders or
  close positions. It is restartable because the bot is not terminal.
- `stop` requests graceful bot closure; runtime continues until Executor
  reports the bot is closed, then marks the bot terminal stopped.
- Terminal stopped/error bots cannot be restarted. Clone or create a new bot
  instead.
- `run_token` protects the current run from stale process writes.
- Every runtime DB update must include `bot_id` and `run_token`.
- Ray actor state plus heartbeat freshness are liveness evidence in managed
  mode.
- Manual mode liveness is bot-local heartbeat freshness.
- `bot_command`, `bot_event`, and `bot_state` are bot-local tables, never shared
  server DB tables.
- No Redis.
- No aiohttp or port table for runtime commands.
