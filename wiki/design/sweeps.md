---
title: sweeps design
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [design, sweeps]
---

# sweeps design

## definitions

- `botrun`: one bot lifecycle: init, start, loop, stop.
- `sweeprun`: one generated parameter set over one market/window period.
- `sweep`: hyperparameter definition that permutates into sweepruns.

## hard rule

```text
sweep output includes a full normal botrun config.
botrun config contains no sweep-only fields.
good sweeprun -> extract botrun config -> run backtest/paper/live.
```

## flow

```text
record sweep started_at
generate permutations
insert sweeprun rows with sweeprun config and botrun config
run N workers
store each botrun result and duration
mark sweep complete/error
```

## parameter shape

```toml
[params]
stop_loss = { start = 1.0, stop = 3.0, step = 0.5 }
take_profit = [1.0, 1.2, 1.7, 2.3, 5.0]
period = [
  { start = 2024-01-01, stop = 2024-12-31 },
  { start = 2025-01-01, stop = 2025-12-31 },
]
```

Rules:

- `{ start, stop, step }` means range.
- `[...]` means exact values.
- A parameter must use exactly one form.
- `period` uses exact start/stop date tables.
