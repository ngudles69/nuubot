---
title: sweeps design
created: 2026-06-20
updated: 2026-06-21
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
good sweeprun -> extract botrun config -> run backtest/simnet/mainnet.
```

Config hierarchy:

```text
SweepConfig
  sweep settings
  params/ranges
  generates SweeprunConfig

SweeprunConfig
  period/window settings
  botrun: BotrunConfig

BotrunConfig
  runtime
  market
  backtest
  exchange
  signalers
  executor
  risk
```

Botrun runtime fields:

```toml
[runtime]
mode = "backtest"
```

Sweep-generated botruns use `runtime.mode = "backtest"` by default. The derived
properties are `data_network = "filedata"` and `exec_network = "simulator"`.
`sweep.mode` still controls how the sweep is executed, not where data or
execution goes.

Sweep does not use the bot runtime log naming. Bot modes use
`bot_<mode>_<bot_id>.log`; sweep uses its own sweep log format.

Backtest file data lives under `[backtest]`:

```toml
[backtest]
start = "2025-01-01"
stop = "2025-03-31T23:59:59"
data_dir = "workspace/data/binance/raw/spot/monthly/klines"
```

## modes

`standard` is the default sweep mode.

```toml
[sweep]
mode = "standard"  # or "fast"
```

`sweep.mode` controls the execution shell:

- DB writes.
- logging detail.
- account detail persistence.
- indicator build path.

`sweep.mode` does not control strategy:

- executor choice.
- signaler choice.
- risk logic.
- strategy config.
- result shape.

Mode rule:

```text
mode = how the run is executed
executor = what strategy logic is executed
```

Fast mode and standard mode should use the same executor unless the config
explicitly selects a different executor.

Fast executors are not special. They are normal named executors:

```toml
[sweep]
mode = "fast"

[executor]
name = "grid_fast"
```

Never silently swap `grid` to `grid_fast` because `mode = "fast"`.

Persistence rule:

- fast sweep: write only after each sweeprun is done.
- standard sweep: write only after each sweeprun is done.
- mainnet/testnet/simnet: full DB persistence.
- one-off backtest: full DB persistence by default.

## objective

Fast development and fast testing come first.

Without a working profitable strategy, the rest of the runtime has no value.
Sweeps exist to find strategy candidates quickly, then prove winners through
the normal runtime.

## execution shells

Build two small proofs before building the full sweep system.

1. Fast sweep mode:

```text
uv run python -m nuubot.core.sweep -f workspace/templates/ema-1h-fast.toml
```

Purpose:

- Load bars once.
- Build EMA signals once per config.
- Run `ExecutorTrade` over shared bars.
- Collect final result only.
- Print best results.

Skip:

- DB.
- command server.
- websocket.
- runtime lifecycle ceremony.
- per-loop file writes.

2. Standard sweep mode:

```text
uv run python -m nuubot.core.sweep -f workspace/templates/ema-1h-standard.toml
```

Purpose:

- Generate normal backtest configs.
- Run each config through `Runtime(config)`.
- Prove generated sweepruns can use the canonical backtest loop.

Skip:

- workers.
- DB.
- full result schema.
- mainnet/testnet/simnet mode.

Proof commands live in `wiki/testing.md`.

## result shape

Minimum result:

- config id.
- pnl.
- win count.
- loss count.
- trade count.
- max drawdown.
- speed timing.

Speed timing:

- data load ms.
- indicator build ms.
- strategy run ms.
- total ms.
- bars processed.
- bars per second.
- configs per second.
- worker count.

Speed timing is mandatory for every sweep proof. It measures how fast the sweep
runs, not market time. A one-year 1m run should show:

- how long data loading took.
- how long indicator preparation took.
- how long strategy execution took.
- total wall-clock time.
- throughput in bars per second and configs per second.

## component reuse

Reuse strategy primitives first:

- market data loader.
- indicator functions.
- signaler logic.
- risk scoring.
- executor math.
- result summary.

Fast sweeps may skip runtime ceremony.

Fast sweeps must not change trading logic.

Runtime sweeps exist to validate that the same config works through the normal
backtest loop.

## executor comparison

Compare executors by running normal sweepruns.

Example:

```text
sweeprun A:
  mode = "standard"
  executor = "grid"

sweeprun B:
  mode = "fast"
  executor = "grid_fast"
```

Compare:

- pnl.
- trade count.
- win count.
- loss count.
- max drawdown.
- entry timestamp differences.
- exit timestamp differences.
- entry price differences.
- exit price differences.
- missed trades.
- extra trades.

If an optimized executor reduces checks, expect subtle differences. Record the
similarity and the differences before using it for large data sets.

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
