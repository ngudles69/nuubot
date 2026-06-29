---
title: server db design
created: 2026-06-29
updated: 2026-06-29
type: wiki
status: active
tags: [design, server, sqlite, datastore, meta]
---

# server db design

## purpose

`server.db` is the only persistent shared DB.

Server owns the server DB. Other components may use it only through short
operations.

## owns

Server DB owns:

- `seq`
- `state`
- `meta`

Server DB does not own bot/sweep/sweeprun catalogs.

## access rule

Every `server.db` access is:

```text
open connection
read/write one small operation
close connection
```

This applies to:

- Server managers.
- bot actors.
- sweep tasks.
- CLI helpers.

No bot actor, sweep task, CLI helper, or runtime component keeps a long-lived
server DB connection.

## exchange meta

Server setup owns exchange meta refresh.

```text
nuubot_setup()
  create server.db if missing
  create server tables if missing
  if meta missing or older than 24h:
    fetch all meta
    write meta
```

Bot setup reads meta once:

```text
bot_setup()
  open server.db
  read required meta
  close server.db
  write needed meta snapshot to bot.db
```

If required meta is missing or empty, bot startup fails loud.

Bot setup does not fetch exchange meta from the exchange.

## notes

- Central meta keeps one cached source of exchange truth.
- Bot DB keeps a local snapshot so the bot runtime is self-contained after
  setup.
- Per-bot DB access is separate: a bot actor may keep local bot DB access while
  it runs.
- Bot existence is `workspace/db/<exec_network>_bot_<id>.db`.
- Sweep existence is `workspace/db/sweep_<id>.db`.
- Sweeprun existence is `workspace/db/sweeprun_<id>.db`.
