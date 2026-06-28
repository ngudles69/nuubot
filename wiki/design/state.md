---
title: state design
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [design, state, datastore]
---

# state design

## datastore

Persist these tables first:

- `bot`
- `exchange_meta`
- `position`
- `order`
- `fill`
- `event`
- `command`

State ownership:

- `Position` writes to the position table.
- `Order` writes to the order table.
- `Fill` writes to the fill table.
- `Event` writes to the event table.
- `ExchangeMeta` writes to the exchange meta table.
- `CommandServer` writes bot runtime ownership and command rows.
- `Bot` writes bot lifecycle/status rows.
- `Datastore` does not save domain objects.

Persistence verbs:

```text
insert_state()  # insert only; fail if row exists unexpectedly
select_state()  # select/read
update_state()  # update only; fail if row is missing unexpectedly
delete_state()  # explicit delete only
```

Timestamp rule:

- All stored timestamps are UTC.
- Datastore sessions force the Postgres timezone to UTC.
- Exchange timestamps are stored as received/normalized UTC values.
- Store one canonical timestamp value. Convert to local time only for logs,
  reports, notebooks, and UI display.

## entity map

```text
BOTRUN ||--o{ POSITION
BOTRUN ||--o{ ORDER
BOTRUN ||--o{ FILL
BOTRUN ||--o{ EVENT
BOTRUN ||--o{ COMMAND
POSITION ||--o{ ORDER
ORDER ||--o{ FILL
SWEEP ||--o{ SWEEPRUN
SWEEPRUN ||--o{ BOTRUN_REF
EXCHANGE_META }o--|| VENUE
```

This is a logical relationship map only. Do not create database foreign keys.

Bot run state:

- Persist a redacted config snapshot with the bot run record.
- Runtime start writes `pid`, `run_token`, `started_at`, and `last_seen_at`.
- Runtime heartbeat updates `last_seen_at` using `bot_id` and `run_token`.
- `stopped` and `error` are terminal states.
- Do not restart a terminal bot in place.
- If the user wants to continue, clone/create a new bot run from current market
  conditions.
- Track dirty state when cleanup fails.

Command state:

- CLI inserts command rows.
- Runtime polls command rows for its bot.
- Runtime claims pending commands before executing them.
- Runtime writes command result or error.
- No Redis and no aiohttp until DB polling is proven too slow.

## exchange meta

Exchange meta is global exchange reference data.

Policy on bot start:

```text
if exchange_meta has rows for venue fetched within the last 24 hours:
  use stored meta
else:
  fetch all exchange meta from the exchange
  upsert all exchange_meta rows
load requested symbol from exchange_meta
if symbol is missing:
  fail loud
```

Rules:

- Fetch all meta, not one symbol.
- Do not keep fetching within the 24 hour freshness window.
- Use `upsert` for `exchange_meta`; it is reference data, not trading evidence.
- No background refresh.
- No central meta server.
- `ExchangeMeta` must be usable without datastore.
- If datastore is unavailable, fetch and use meta without storing it.
- Missing datastore must not change the meta object behavior.
- Precision and minimum-order checks use exchange meta.
- If refresh is required and exchange fetch fails, fail startup.
- `ExchangeAccount` and executors use the stored meta row loaded after the
  freshness check.

Suggested table:

```text
venue
symbol
asset_id
price_decimals
size_decimals
raw_json
fetched_at
```

Unique key:

```text
venue, symbol
```

## positions orders fills

- Create `Position` before submit as intent.
- `Position` owns related `Order` and `Fill` objects.
- `Order` can be intent and exchange evidence.
- `Fill` is exchange evidence.
- Position accounting owns clear PnL.
- Do not silently overwrite trading evidence.

## reconciliation

Keep reconciliation closer to BlackBot simplicity than `nuutrader6` breadth.

Loop shape:

```text
pull needed open orders, order history, fill history, and positions from exchange
normalize exchange rows into standard local shape
find rows relevant to this bot/run/cloid
update Position, Order, and Fill objects
decide whether more orders are needed
persist changed state
```

Rules:

- Reconcile only what the bot needs.
- Do not reconcile the entire exchange account before every decision.
- Persist positions, orders, and fills as the evidence changes.
- Use `cloid` for bot-owned order identity.

## events

Events are for user/frontend observability.

First event shape can be simple:

```text
timestamp
bot_id
level/type
message
optional JSON data
```

Examples:

- bot started
- bot stopped
- bot error
- bot entered risky zone
- position opened
- position closed
- hedge loss

## frontend read model

Frontend is a separate scope from bot runtime. It reads datastore state and may
insert command rows through the same command path used by CLI later.

Frontend server responsibilities later:

- List configured, running, and terminal bots.
- Show bot status, PID evidence, run token, and heartbeat freshness.
- Show latest risk score and signal state.
- Show open/closed positions, orders, fills, and events.
- Show dirty state when cleanup failed.
- Show the redacted config snapshot used by a bot run.

Minimum frontend server API routes later:

```text
GET /bots
GET /bots/{bot_id}
GET /bots/{bot_id}/positions
GET /bots/{bot_id}/orders
GET /bots/{bot_id}/fills
GET /bots/{bot_id}/events
```

These routes read datastore only. They do not execute strategy logic.
