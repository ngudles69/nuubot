---
title: account object
created: 2026-06-23
updated: 2026-06-23
type: wiki
status: active
tags: [design, objects, account, simulator, exchange]
---

# account object

## purpose

Account represents one connection to an exchange through one account.

Account owns exchange account behavior and composes simulator behavior for
simnet/backtest. Ledger may be composed by Account if that keeps exchange
evidence and accounting together.

Allowed composed objects:

- `Simulator`
- `Ledger`
- account-specific exchange client
- account-specific exchange meta helper when needed

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `balances()`
- `open_orders()`
- `positions()`
- `submit(order_intent)`
- `submit_batch(order_intents)`
- `cancel(order_id)`
- `cancel_batch(order_ids)`
- `reconcile()`
- `ledger()`

Account receives:

- config.
- exchange meta.
- order intent from `Executor`.
- mode-derived execution network.

Account outputs:

- balances.
- order submit/cancel results.
- exchange order/fill/position evidence.
- ledger updates.
- account telemetry.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Config, meta, execution network. | Initialized Account. | Builds real or simulator-backed account path. Fails loud on invalid credentials/config. |
| `start()` | Initialized Account. | Running Account. | Opens required live/sim resources. Does not submit orders. |
| `stop()` | Running Account. | Stopped Account. | Closes owned resources. Does not hide dirty state. |
| `balances()` | None. | Account balances. | Reads from real exchange or simulator. Fails loud if account path is unavailable. |
| `open_orders()` | None. | Open order evidence. | Returns account-owned open orders in normalized shape. |
| `positions()` | None. | Position evidence. | Returns account position evidence in normalized shape. |
| `submit(order_intent)` | One validated order intent. | Submit result. | Applies precision/min checks, routes to real/sim execution, and feeds accepted evidence to Ledger. |
| `submit_batch(order_intents)` | List of order intents. | Submit results. | Preserves result order and fails loud on invalid batch shape. |
| `cancel(order_id)` | Account/order id. | Cancel result. | Cancels through real/sim execution and records resulting evidence. |
| `cancel_batch(order_ids)` | List of ids. | Cancel results. | Preserves result order and fails loud on invalid batch shape. |
| `reconcile()` | None. | Reconciliation summary. | Pulls only needed account evidence, normalizes it, and updates Ledger. |
| `ledger()` | None. | Ledger object/state. | Exposes Account-owned accounting state without exposing simulator internals. |

## processing

Internal functions:

- initialize real or simulator-backed account client.
- validate credentials for live/test execution.
- route submit/cancel/read calls to real exchange or simulator.
- normalize exchange rows into local order/fill/position evidence.
- reconcile account evidence into `Ledger`.
- apply exchange precision and minimum-order checks before submit.
- pass simulator fills/orders through the same evidence path used by live
  exchange rows.

## key helpers

- submit shape builder.
- batch submit grouper.
- exchange row normalizer.
- simulator adapter.
- exchange precision/minimum checks.
- credential validator.
- account evidence mapper.

## notes

- Simnet/backtest must use simulator through Account, not through Runtime.
- Runtime should not know simulator internals.
- Ledger is allowed as Account child if we keep accounting coupled to account
  evidence.
- Executor sends order intent to Account. Executor does not write orders/fills
  directly into Ledger.
