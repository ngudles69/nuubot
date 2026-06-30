---
title: executor object
created: 2026-06-23
updated: 2026-06-23
type: wiki
status: active
tags: [design, objects, executor, strategy]
---

# executor object

## purpose

Executor is the strategy execution logic.

It receives runtime triggers such as BBO/candle bars and signal results. It
places outgoing orders through Account.

Code layout target:

```text
nuubot/bots/
  runtime.py
  executors/
  ghbot/
    ghbot.py
    grid.py
    hedge.py
  tradebot/
    tradebot.py
  dcabot/
    dcabot.py
```

Do not add deeper folders until a real executor needs them.

Allowed connections:

- `Account` for order/account actions.
- `Datastore` for strategy result/state writes only.
- `Signaler` output through Runtime.

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `loop_once(market, signal)`
- `exit()`
- `result()`
- `telemetry()`

Executor receives:

- config.
- market trigger from Runtime.
- signal output from Runtime.
- account object.
- optional datastore object.

Executor outputs:

- order intent to Account.
- strategy telemetry.
- strategy result.
- optional strategy state/result writes.
- exit request.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Config, Account, optional Datastore. | Initialized Executor. | Validates strategy config and required object connections. Does not submit orders. |
| `start()` | Initialized Executor. | Running Executor. | Prepares strategy-local state. Does not change runtime flow. |
| `stop()` | Running Executor. | Stopped Executor. | Finalizes open strategy state according to executor rules. |
| `loop_once(market, signal)` | Market trigger and standardized Signal. | Strategy action. | Decides hold/entry/exit, builds order intent, and calls Account. Does not inspect indicators. |
| `exit()` | Strategy state. | Boolean. | Returns whether Executor requests runtime stop. |
| `result()` | Strategy state. | Strategy result. | Returns final PnL/trade/diagnostic summary. |
| `telemetry()` | Strategy state. | JSON-safe telemetry. | Returns current strategy telemetry without side effects. |

## processing

Internal functions:

- validate executor params.
- decide entry/exit/hold.
- size orders.
- build order intent.
- call Account submit/cancel/reconcile.
- record strategy result/state when allowed.
- process Account submit/cancel results.
- update strategy-local state.
- build final result summary.

## key helpers

- grid planner.
- hedge planner.
- order intent builder.
- result summarizer.
- position intent builder.
- sizing calculator.
- exit condition checker.
- telemetry builder.

## notes

- Executor does not reach into simulator, ledger internals, indicators, or raw
  SQL.
- If Executor needs another object connection, update this file first and ask
  the user to allow it.
- Executor receives signal output, not indicator output.
- Executor should be readable as the strategy decision body.
