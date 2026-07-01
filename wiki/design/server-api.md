---
title: server api design
created: 2026-06-29
updated: 2026-07-01
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
- Validate only transport-level input at the route boundary:
  - required path parts are present.
  - primitive path/query/body fields are the expected basic type.
  - required strings are not empty.
  - IDs parse as integers where the route requires integer IDs.
  - enums use accepted route values.
- If the input is a full template, validate only that the template value exists
  and is not empty; pass it to BotManager/SweepManager specialist validation.
- Call one manager/helper function.
- Own API return shape: HTTP status, JSON envelope, and API error shape.
- Return manager/helper output inside that API shape.
- Map known validation/domain errors to clear API errors.
- All future API routes must use the standard response envelope below.

API owns:

- route shape.
- primitive input checks.
- empty checks.
- security checks.
- auth/session/permission checks when they exist.
- request size limits when needed.
- content type expectations when needed.
- API JSON response shape.
- HTTP status code selection.

API does not own:

- template parsing.
- strategy validation.
- DB creation logic.
- seq allocation.
- bot/sweep business rules.
- HTML page shape, toast shape, or redirect behavior; WebGUI owns those.

Route validation examples:

```text
/bot/run/mainnet/1A       invalid: bot id is not an integer
/bot/run/mainnet/         invalid: bot id missing
/bot/run/unknown/1        invalid: network not accepted by that route
POST /api/sweeps <empty>  invalid: template missing
```

Specialist validation examples:

```text
SweepManager.create(template)
  parses TOML
  validates sweep template shape
  allocates seq
  creates sweep DB
  writes sweep row
```

## route non-goals

Routes must not:

- create bot rows directly.
- allocate server sequences directly.
- create SQLite tables directly.
- start worker processes directly.
- parse bot templates deeply.
- build strategy/executor/account objects.
- contain display/report construction logic.
- become a collector of scripts.

## naming

Use boring resource/action names.

## response envelope

All API routes return:

```json
{
  "status": "ok",
  "response": {
    "type": "sweep_results",
    "id": 27,
    "data": {}
  }
}
```

Errors return:

```json
{
  "status": "err",
  "response": {
    "type": "sweep_results",
    "id": 27,
    "data": {
      "error": {
        "code": "sweep_results_failed",
        "message": "sweep DB missing: sweep_27.db"
      }
    }
  }
}
```

Rules:

- `status` is `ok` or `err`.
- `response.type` is the API operation that was called.
- `response.id` is the resource id when the route has one.
- `response.data` is the payload.
- `response.data.error` carries boundary errors.
- Action/domain failures that are valid responses may use `status = "ok"` and
  put failure details inside `response.data`.

Current response types:

```text
GET  /ping                         -> ping
GET  /status                       -> server_status
GET  /api/sweeps                   -> sweeps_list
POST /api/sweeps                   -> sweep_create
GET  /api/sweeps/{sweep_id}        -> sweep_get
POST /api/sweeps/{sweep_id}/run    -> sweep_run
GET  /api/sweeps/{sweep_id}/status -> sweep_status
GET  /api/sweeps/{sweep_id}/results -> sweep_results
GET  /api/sweeps/{sweep_id}/telemetry -> sweep_telemetry
```

Examples:

Successful status response:

```json
{
  "status": "ok",
  "response": {
    "type": "sweep_status",
    "id": 27,
    "data": {
      "sweep_id": 27,
      "status": "complete",
      "progress": "36/36"
    }
  }
}
```

Successful action response:

```json
{
  "status": "ok",
  "response": {
    "type": "sweep_run",
    "id": 27,
    "data": {
      "sweep_id": 27,
      "status": "running",
      "progress": "0/36"
    }
  }
}
```

Valid request with domain failure:

```json
{
  "status": "ok",
  "response": {
    "type": "sweep_run",
    "id": 27,
    "data": {
      "sweep_id": 27,
      "status": "failed",
      "error": {
        "code": "validation_failed",
        "message": "sweep.workers must be <= 8: 16"
      }
    }
  }
}
```

Boundary error:

```json
{
  "status": "err",
  "response": {
    "type": "sweep_results",
    "id": 999999,
    "data": {
      "error": {
        "code": "sweep_results_failed",
        "message": "sweep DB missing: sweep_999999.db"
      }
    }
  }
}
```

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

```text
POST /api/sweeps
  route reads raw request body
  route rejects empty body
  route does not parse TOML
  route calls SweepManager.create(template)
  route returns type=sweep_create with data={ sweep_id }
```

```text
POST /api/sweeps/{sweep_id}/run
  route validates sweep_id is a positive int
  route calls SweepManager.run(sweep_id)
  route returns type=sweep_run with data=status
```

```text
GET /api/sweeps/{sweep_id}/status
  route validates sweep_id is a positive int
  route calls SweepManager.status(sweep_id)
  route returns type=sweep_status with data=status
```
