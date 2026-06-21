---
title: strategy design
created: 2026-06-20
updated: 2026-06-21
type: wiki
status: active
tags: [design, strategy, risk, executor]
---

# strategy design

## risk

Risk is first-class.

`Risk.score(context) -> int` is mandatory from the first implementation, even
if it returns a simple low-risk score at first.

Global risk score:

```text
1-30    full trade size
31-40   75% trade size
41-50   50% trade size
51-60   25% trade size
61-70   hold new entries; consider exiting some/all positions
71-100  recommend get out
```

Rules:

- Risk score is the source of truth.
- `Risk.score()` returns an integer `1..100`.
- Start with score `1` as the blank low-risk implementation.
- If executor wants mapped bands later, add `Risk.decision(score)` only when
  code calls it.
- Future runtime-level forced exit can use the same score if it becomes needed.
- Do not code runtime forced exit yet.

Example permanent hard-risk concept:

```text
if cycle_losses >= max_cycle_losses:
  score = 100 until reset/manual intervention/new cycle
```

## signalers

- Start with `SignalerStartNow`.
- Later signalers can include `SignalerEmaCrossover`.
- Signalers are inputs to executors.
- Do not build a signaler framework until multiple real signalers need shared
  structure.
- Botrun config owns a `signalers` list.
- Every signaler config item has:
  - `name`
  - `interval`
  - `params`
- Pydantic validates the generic signaler item shape.
- Each signaler object validates its own `params` at runtime.

Example:

```toml
[[signalers]]
name = "emacross"
interval = "1h"
params = { fast = 9, slow = 21 }

[[signalers]]
name = "regime"
interval = "4h"
params = { sma = 200 }
```

## executors

- Executors are free-form strategy code.
- Executors define strategy behavior.
- Runtime mode and sweep mode must not silently replace executors.
- Start with `ExecutorTrade`.
- `ExecutorTrade` can submit one entry batch:
  - entry only
  - entry + TP
  - entry + SL
  - entry + TP + SL
- `ExecutorGrid`, `ExecutorHedge`, and `ExecutorDCA` come later.
- Grid behavior should follow the useful `nuutrader6` grid logic, while the
  top-level bot code keeps BlackBot-style simplicity.
- Runtime owns a list of executors from the start.
- Executors call `Risk.score()` as needed.
- Executors call `Signaler` as needed.
- Executors call `ExchangeAccount` directly.
- Executors own normal strategy position lifecycle.

Optimized executors are separate named executors. A fast executor is not a
special engine feature.

Example:

```text
ExecutorGrid
ExecutorGridFast
ExecutorTrade
ExecutorDCA
```

Select optimized executors explicitly in config:

```toml
[executor]
name = "grid_fast"
```

If an optimized executor reduces checks, validate it against the canonical
executor with the same data and config. Compare result summary and trade trace
before using it for large data sets.

`ExchangeAccount` must support batch submit shapes needed by executor trade:

```text
entry
entry + take-profit
entry + stop-loss
entry + take-profit + stop-loss
```

Executor lifecycle is one-way:

```text
executor.init()
executor.start()
executor.loop_once()
executor.loop_once()
executor.stop()
```

Do not start an executor twice.
