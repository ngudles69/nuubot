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
- `port`

State ownership:

- `Position` writes to the position table.
- `Order` writes to the order table.
- `Fill` writes to the fill table.
- `Event` writes to the event table.
- `ExchangeMeta` writes to the exchange meta table.
- `CommandServer` writes to the port table.
- `Bot` writes bot lifecycle/status rows.
- `Datastore` does not save domain objects.

Persistence verbs:

```text
insert_state()  # insert only; fail if row exists unexpectedly
select_state()  # select/read
update_state()  # update only; fail if row is missing unexpectedly
delete_state()  # explicit delete only
```

Bot run state:

- Persist a redacted config snapshot with the bot run record.
- Do not persist heartbeat to datastore for the first implementation.
- `stopped` and `error` are terminal states.
- Do not restart a terminal bot in place.
- If the user wants to continue, clone/create a new bot run from current market
  conditions.
- Track dirty state when cleanup fails.

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
