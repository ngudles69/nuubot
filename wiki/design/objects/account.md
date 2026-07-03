---
title: account object
created: 2026-06-23
updated: 2026-07-03
type: wiki
status: active
tags: [design, objects, account, simulator, exchange]
---

# account object

## purpose

`TradingAccount` represents one Hyperliquid account.

`TradingAccount` owns exchange account behavior and one `Ledger`. During
`init()`, it either connects to mainnet/testnet with config credentials or
creates a simulator for simnet/backtest/sweep.

Allowed composed objects:

- `Simulator`
- `Ledger`
- account-specific exchange client
- account-specific exchange meta helper when needed

## interfaces

External commands:

- `init()`
- `close()`
- `create_position(symbol)`
- `position(position_id)`
- `ingest_bbo(tick)`
- `place_orders(orders, observed_at_ms)`
- `cancel_orders(cancels, observed_at_ms)`
- `close_positions(positions, price, observed_at_ms, reason)`
- `recon(observed_at_ms, reason)`
- `set_leverage(leverage)`
- `leverage()`
- `balance()`
- `summary()`
- `audit()`

`TradingAccount` receives:

- config.
- exchange meta.
- account name selected by the executor definition.
- order intent from `Executor`.
- mode-derived execution network.
- `acct_id` from the bot DB `account` row.

`TradingAccount` outputs:

- balance.
- leverage.
- order submit/cancel results.
- exchange order/fill/position evidence.
- ledger updates.
- account telemetry.
- account state persisted under that `acct_id`.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Config, meta, execution network. | Initialized TradingAccount. | Builds real or simulator-backed account. Fails loud on invalid credentials/config. |
| `close()` | Initialized TradingAccount. | Closed TradingAccount. | Closes owned exchange/simulator resources. Does not hide dirty state. |
| `create_position(symbol)` | Symbol. | New position. | Creates position intent in the owned Ledger before submit. |
| `position(position_id)` | Position id. | Position or error. | Reads the owned Ledger and fails loud on missing position. |
| `ingest_bbo(tick)` | Tick/BBO event. | Account update. | Live can mark/no-op. Simulator ingests the tick, matches open orders, creates fills, and updates internal state. |
| `place_orders(orders, observed_at_ms)` | Order intents. | Submit results. | Records intent, routes to real/sim execution, applies submit evidence, and runs `recon()` if immediately filled. |
| `cancel_orders(cancels, observed_at_ms)` | Cancel intents. | Cancel results. | Cancels through real/sim execution and records resulting evidence. |
| `close_positions(positions, price, observed_at_ms, reason)` | Positions, price, time, reason. | Submit results. | Cancels open exit orders, builds reduce-only cleanup orders from current position state, and submits them. |
| `recon(observed_at_ms, reason)` | Time and reason. | Recon summary. | Pulls only needed exchange/simulator evidence, normalizes it, and updates Ledger. |
| `set_leverage(leverage)` | Target leverage. | Exchange/sim result. | Sets account leverage or fails loud when unsupported. |
| `leverage()` | None. | Current leverage. | Reads current account leverage from exchange/simulator. |
| `balance()` | None. | Balance object. | Reads account balance or fails loud when the backing exchange/simulator does not support it yet. |
| `summary()` | None. | Account summary. | Returns account and ledger summary for telemetry/results. |
| `audit()` | None. | Account audit. | Reports dirty open state for cleanup/stop handling. |

## processing

Internal functions:

- initialize real or simulator-backed account client.
- validate credentials for live/test execution.
- ingest tick/BBO events for simulator/sweep matching.
- route submit/cancel/read calls to real exchange or simulator.
- normalize exchange rows into local order/fill/position evidence.
- reconcile account evidence into `Ledger`.
- apply exchange precision and minimum-order checks before submit.
- pass simulator fills/orders through the same evidence path used by live
  exchange rows.

## key helpers

Keep helper functions private and local until reused by real code. Do not add
separate account-name, credential, or simulator-state helpers for one call
site.

## notes

- Simnet/backtest/sweep must use simulator through `TradingAccount`, not
  through Runtime or Sweeprun.
- Runtime should not know simulator internals.
- Ledger is a `TradingAccount` child.
- Sweep executor account names must exist in loaded Hyperliquid credentials.
- Executor sends order intent to `TradingAccount`. Executor does not write
  orders/fills directly into Ledger.
- A bot using two exchange accounts has two `account` rows in the bot DB.
- Positions belong to an `acct_id`; orders belong to a `position_id`; fills
  belong to an `order_id`.
