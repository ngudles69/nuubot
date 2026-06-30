---
title: state design
created: 2026-06-20
updated: 2026-06-30
type: wiki
status: active
tags: [design, state, datastore]
---

# state design

## datastore model

SQLite is the datastore target.

DB files:

- one persistent server DB for seq numbers, server state, and exchange
  meta.
- one SQLite DB file per running bot instance.
- one SQLite DB file per sweep.
- sweepruns are rows inside their sweep DB.

Naming examples:

```text
workspace/db/server.db
workspace/db/mainnet_bot_1.db
workspace/db/testnet_bot_2.db
workspace/db/simnet_bot_3.db
workspace/db/backtest_bot_4.db
workspace/db/sweep_1.db
```

Reset rule:

- To reset one bot, delete that bot's DB file and create/start from
  config/template again. That is effectively a new bot instance.
- To clear one mode, delete that mode prefix, for example
  `workspace/db/simnet_bot_*.db`.
- To rerun a sweep, keep the sweep DB/config row and reset run-owned rows.
- To remove a sweep artifact, delete/drop that sweep DB file.
- Do not migrate old bot/sweep runtime state.
- Do not keep Postgres compatibility paths.

Existence rule:

```text
workspace/db/<exec_network>_bot_<id>.db exists => bot exists
workspace/db/sweep_<id>.db exists => sweep exists
```

Do not add central bot/sweep/sweeprun catalog tables unless file discovery is
measured and proven insufficient. The file is the existence record, which avoids
central catalog desync.

Nuubot setup owns `server.db`; see [Server DB](server-db.md).

Server DB access rule:

```text
open connection
read/write
close connection
```

Long-lived server DB sessions are not allowed.

## instance state

Persist these tables first:

- `bot`
- `account`
- `command`
- `event`
- `botstate`
- `position`
- `order`
- `fill`
- `simstate`

Server DB tables first:

- `seq`
- `state`
- `meta`

State ownership:

- `Position` writes to the position table.
- `Order` writes to the order table.
- `Fill` writes to the fill table.
- `Event` writes to the bot-local event table.
- `ExchangeMeta` writes to the server DB exchange meta table.
- `CommandServer` handles bot-local command table polling.
- `Bot` writes bot lifecycle/status/state rows to its bot DB.
- `Datastore` saves table rows only. It does not save domain objects or decide
  bot lifecycle, order state, fill state, or PnL meaning.

Persistence verbs:

```text
create(db)       # create DB file
drop(db)         # delete DB file
dbinit(db)       # create DB and missing tables
insert(db, row)  # insert only; fail if row exists unexpectedly
select(db, table, **where)
get(db, table, **where)
update(db, table, row)
delete(db, table, **where)
count(db, table, **where)
upsert(db, row)  # only where insert-on-conflict behavior is intended
```

Timestamp rule:

- All stored timestamps are UTC.
- Exchange timestamps are stored as received/normalized UTC values.
- Store one canonical timestamp value. Convert to local time only for logs,
  reports, notebooks, and UI display.

## entity map

```text
SERVER ||--o{ EXCHANGE_META
BOT ||--o{ ACCOUNT
ACCOUNT ||--o{ POSITION
POSITION ||--o{ ORDER
ORDER ||--o{ FILL
SWEEP ||--o{ SWEEPRUN
SWEEPRUN ||--o{ BOT_REF
EXCHANGE_META }o--|| VENUE
```

This is a logical relationship map only. Do not create database foreign keys.

Bot DB shape:

- One running bot runtime owns one bot SQLite DB.
- That DB has one logical `bot` row.
- Do not repeat `bot_id` on every per-bot table. The DB file is already the
  bot boundary.
- Do not repeat `network` on every per-bot table. Put execution-network data on
  the `bot` row or `account` row only when needed.
- `account.acct_id` keys accounts. A bot using two accounts has two
  `account` rows.
- `account.bot_id` is nullable. In a one-bot DB it may be blank because the DB
  file already owns the bot. In a sweep DB it can link the account to a
  generated bot.
- `position.bot_id` and `position.acct_id` link positions to a bot/account.
- `order.position_id` links orders to a position.
- `fill.order_id` links fills to an order.
- `bot.state_json` is the free-form runtime state field until a real query
  proves a separate state table is needed.
- `account.state_json` may hold account-local free-form state.
- Persist a redacted config snapshot with the bot row.
- Runtime start writes `runtime_id`, `run_token`, `started_at`, and
  `last_seen_at` where useful.
- Runtime heartbeat updates the local `bot` row using the current `run_token`.
- `stopped` and `error` are terminal states.
- Do not restart a terminal bot in place.
- If the user wants to continue, clone/create a new bot run from current market
  conditions.
- Track dirty state when cleanup fails.

Server seq shape:

```text
seq(name primary key, value)
```

Initial seq names:

```text
mainnet_bot
testnet_bot
simnet_bot
backtest_bot
sweep
sweeprun
```

Allocation rule:

```sql
BEGIN IMMEDIATE;
INSERT INTO seq (name, value)
  VALUES (:name, 0)
  ON CONFLICT(name) DO NOTHING;
UPDATE seq
  SET value = value + 1
  WHERE name = :name
  RETURNING value;
COMMIT;
```

If allocation, server infra check, or DB setup fails, startup fails loud. The
operator restarts. Do not add fallback IDs or a custom seq recovery layer.

Command state:

- Bot-local command DB writes are the command path in managed mode.
- Manual/notebook mode also polls the bot-local `command` table.
- `command`, `event`, and `botstate` are local bot DB tables.
- There is no shared command table.
- No Redis and no aiohttp.

## exchange meta

Exchange meta is global exchange reference data.

Policy on bot start:

```text
if meta has rows for venue fetched within the last 24 hours:
  use stored meta
else:
  fetch all exchange meta from the exchange
  upsert all meta rows
load requested symbol from meta
if symbol is missing:
  fail loud
```

Rules:

- Fetch all meta, not one symbol.
- Do not keep fetching within the 24 hour freshness window.
- Use `upsert` for `meta`; it is reference data, not trading evidence.
- No background refresh.
- Server DB owns exchange meta.
- If server DB setup fails, startup fails loud.
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
- Ledger/datastore owns the local accounting truth.
- Exchange accounting truth overrides local ledger/datastore truth during
  reconciliation.
- Do not add a third persistent in-memory accounting truth.
- In-memory lists/objects are temporary processing state after reading from the
  datastore.

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

Frontend is a separate scope from bot runtime. It discovers DB files and reads
per-instance SQLite read models. Commands go through bot-local command tables.

Frontend server responsibilities later:

- List configured, running, and terminal bots.
- Show bot status, run token, and heartbeat freshness.
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

These routes read SQLite state only. They do not execute strategy logic.
