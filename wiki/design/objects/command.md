---
title: command server object
created: 2026-06-24
updated: 2026-06-24
type: wiki
status: active
tags: [design, objects, command, runtime]
---

# command server object

## purpose

CommandServer lives in `command.py`.

It is the runtime-side command owner. It writes runtime ownership evidence,
polls the command table, claims commands for its bot, executes runtime commands,
and writes command results.

It is not an aiohttp server.

Allowed connections:

- `Datastore`
- Runtime callbacks for `status()` and `exit(reason)`
- local process info for PID

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `heartbeat()`
- `poll()`
- `claim(command)`
- `execute(command)`

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Bot id, Datastore, runtime callbacks. | Initialized CommandServer. | Creates runtime `run_token`, records `pid`, and updates the bot row. If the DB update fails, runtime startup fails. |
| `start()` | Initialized CommandServer. | Running CommandServer. | Starts command polling/heartbeat state. Does not execute commands until Runtime enters normal flow. |
| `stop()` | Running CommandServer. | Stopped CommandServer. | Writes stopped/terminal ownership state where `bot_id` and `run_token` match. |
| `heartbeat()` | Current runtime ownership. | Updated bot row. | Updates `last_seen_at` only where `bot_id` and `run_token` match. |
| `poll()` | Bot id. | Pending command list. | Reads pending commands for this bot. No Redis and no aiohttp. |
| `claim(command)` | Pending command. | Claimed command. | Marks one command running only if it is still pending. |
| `execute(command)` | Claimed command. | Command result. | Executes supported runtime command and writes done/error result. |

Supported runtime commands first:

- `stop`
- `status`

Deferred:

- `freeze`

## processing

Internal functions:

- generate `run_token`.
- read `os.getpid()`.
- write runtime ownership to bot row.
- update heartbeat.
- poll pending command rows.
- claim command rows.
- dispatch command to runtime callback.
- write command result.

## key helpers

- ownership writer.
- heartbeat writer.
- command poller.
- command claimer.
- command result writer.
- command dispatcher.

## notes

- `run_token` protects the current run from stale process writes.
- Every runtime DB update must include `bot_id` and `run_token`.
- PID is evidence, not truth.
- CLI may validate PID liveness and heartbeat freshness for operator display.
- No Redis until DB polling is proven too slow.
- No aiohttp or port table for runtime commands.
