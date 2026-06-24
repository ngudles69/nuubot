---
title: ledger object
created: 2026-06-23
updated: 2026-06-23
type: wiki
status: active
tags: [design, objects, ledger, position, order, fill]
---

# ledger object

## purpose

Ledger is the collection of positions.

`Position` is a primitive object. A position owns orders. An order owns fills,
including partial and full fills.

Hierarchy:

```text
Ledger
  Position
    Order
      Fill
```

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `open_position(intent)`
- `upsert_position(position_evidence)`
- `apply_order(order_evidence)`
- `apply_fill(fill_evidence)`
- `close_position(position_id)`
- `active_positions()`
- `position(position_id)`
- `order(order_id)`
- `fills(order_id)`
- `summary()`

Ledger receives:

- order intent.
- order evidence.
- fill evidence.
- account position evidence.

Ledger outputs:

- position state.
- order state.
- fill state.
- realized/unrealized PnL.
- reconciliation summary.
- changed rows for persistence.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Config or empty state. | Initialized Ledger. | Prepares collections and accounting settings. |
| `start()` | Initialized Ledger. | Running Ledger. | Loads or prepares current accounting state if needed. |
| `stop()` | Running Ledger. | Stopped Ledger. | Finalizes in-memory accounting state. Does not persist by itself. |
| `open_position(intent)` | Valid position/order intent. | New Position. | Creates accounting intent before submit. Fails if duplicate active position is invalid for the strategy. |
| `upsert_position(position_evidence)` | Exchange/account position evidence. | Position state. | Applies external evidence without silently overwriting conflicting local state. |
| `apply_order(order_evidence)` | Order evidence. | Order state. | Attaches order to its position and rejects conflicting duplicate evidence. |
| `apply_fill(fill_evidence)` | Fill evidence. | Fill state and position update. | Attaches fill to its order, supports partial fills, and recalculates accounting. |
| `close_position(position_id)` | Existing position id. | Closed Position. | Marks terminal state only when accounting supports close. Fails on missing id. |
| `active_positions()` | None. | Active positions. | Returns current non-terminal positions. |
| `position(position_id)` | Position id. | Position or error. | Fails loud on missing position unless caller explicitly asks optional later. |
| `order(order_id)` | Order id. | Order or error. | Fails loud on missing order unless caller explicitly asks optional later. |
| `fills(order_id)` | Order id. | Fill list. | Returns fills attached to the order. |
| `summary()` | None. | Ledger summary. | Returns accounting totals and reconciliation counters. |

## processing

Internal functions:

- create/update positions.
- attach orders to positions.
- attach fills to orders.
- update size, average price, realized PnL, and status.
- reject silent overwrite of trading evidence.
- map exchange status to local status.
- keep partial fills attached to their order.
- mark terminal positions and orders.

## key helpers

- position lookup.
- order lookup.
- fill lookup.
- PnL calculation.
- status mapping.
- duplicate evidence detector.
- decimal math helpers.
- ledger summary builder.

## notes

- Use `nuutrader6` ledger contracts as reference, not as direct copy.
- Keep primitives small unless accounting rules force detail.
- Ledger owns accounting truth; Datastore only stores rows.
- Ledger primitives do not call Account, Runtime, Signaler, or Executor.
