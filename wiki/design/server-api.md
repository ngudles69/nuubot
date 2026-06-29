---
title: server api design
created: 2026-06-29
updated: 2026-06-29
type: wiki
status: active
tags: [design, server, api, routes]
---

# server api design

## purpose

Server API is the HTTP/operator boundary for Server.

Routes are adapters. They validate transport/input shape, call one
Server/BotManager/SweepManager helper function, and return the result.

## full route list

Target full route list will live in:

```text
nuubot/server/api.py
```

Reference implementation route list from `nuutrader6`:

```text
D:/rust/nuutrader6/src/nuubot/hcserver/api.py
```

Use `register_routes()` in that file as the route-list reference. Use it for
shape lessons, not for wholesale copying.

## route rules

- Keep route handlers tiny.
- Validate route params, query params, and JSON body shape at the route
  boundary.
- If the input is a full template, validate only that a template object exists;
  pass the template to BotManager/SweepManager specialist validation.
- Call one manager/helper function.
- Return manager/helper output as JSON.
- Map known validation/domain errors to clear API errors.

## route non-goals

Routes must not:

- create bot rows directly.
- allocate server sequences directly.
- create SQLite tables directly.
- start Ray actors or submit Ray tasks directly.
- parse bot templates deeply.
- build strategy/executor/account objects.
- contain display/report construction logic.
- become a collector of scripts.

## naming

Use boring resource/action names.

First route shape:

```text
GET  /ping
GET  /status
POST /stop

GET  /api/bots
POST /api/bots
GET  /api/bots/{bot_id}
POST /api/bots/{bot_id}/clone
POST /api/bots/{bot_id}/start
POST /api/bots/{bot_id}/stop
POST /api/bots/{bot_id}/freeze
GET  /api/bots/{bot_id}/ping
GET  /api/bots/{bot_id}/status

GET  /api/sweeps
POST /api/sweeps
GET  /api/sweeps/{sweep_id}
POST /api/sweeps/{sweep_id}/run
POST /api/sweeps/{sweep_id}/stop
GET  /api/sweeps/{sweep_id}/status
GET  /api/sweeps/{sweep_id}/sweepruns
```

Do not include network in every route by default. Bot DB identity and bot
config carry that context.

## example flow

```text
POST /api/bots
  route validates body has template or path
  route calls BotManager.create_botrow_via_template(template)
  route returns bot id and DB path
```

```text
POST /api/bots/{bot_id}/start
  route validates bot_id is int
  route calls BotManager.start_bot(bot_id)
  route returns accepted/status
```
