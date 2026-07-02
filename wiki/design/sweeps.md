---
title: sweeps design
created: 2026-06-20
updated: 2026-07-02
type: wiki
status: active
tags: [design, sweeps]
---

# sweeps design

## definitions

- `bot`: one runtime instance lifecycle: init, start, loop, stop.
- `sweeprun`: one generated parameter set over one market/window period.
- `botrun`: one actual bot start/stop instance inside a sweeprun.
- `sweep`: hyperparameter definition that permutates into sweepruns.
- `ProcessPoolExecutor` runs sweeps as stateless tasks.

## hard rule

```text
sweep output includes a full normal bot config.
bot config contains no sweep-only fields.
good sweeprun -> extract bot config -> run backtest/simnet/mainnet.
```

Config hierarchy:

```text
GroupSweepConfig
  sweep settings
  data.* sets
  signalers.* sets
  executors.* sets
  risk values
  generates concrete SweeprunConfig rows

SweeprunConfig
  meta
  runtime
  backtest
  signalers
  executor
  risk
```

Bot runtime fields:

```toml
[runtime]
mode = "sweep"
```

Sweep-generated bot configs use `runtime.mode = "sweep"` by default.
`RuntimeConfig` sets `data_network = "filenet"` and `exec_network = "sweep"`
from that mode.
`sweep.mode` still controls fast vs standard execution.

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

- SQLite writes.
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

- fast sweep: process-pool task writes final result to the sweep SQLite DB.
- standard sweep: process-pool task writes final result to the sweep SQLite DB.
- mainnet/testnet/simnet: bot runtime writes full persistence to its own SQLite
  DB.
- one-off backtest bot: bot runtime writes full persistence to
  `backtest_bot_<id>.db`.
- sweep-generated backtest/sweeprun: process-pool task writes final result to
  the sweep DB.
- rerun/reset: keep the sweep DB/config row, delete run-owned child rows, and
  write a fresh result.
- artifact removal: drop/delete the sweep DB file.

## objective

Fast development and fast testing come first.

Without a working profitable strategy, the rest of the runtime has no value.
Sweeps exist to find strategy candidates quickly, then prove winners through
the normal runtime.

## execution shells

Build two small proofs before building the full sweep system.

1. Fast sweep mode:

Target proof runs through the SweepManager process-pool task path.

Purpose:

- Load bars once.
- Build EMA signals once per config.
- Run `ExecutorTrade` over shared bars.
- Collect final result only.
- Print best results.

Skip:

- per-loop DB writes.
- command server.
- websocket.
- runtime lifecycle ceremony.
- per-loop file writes.

Current code note:

- Fast mode loads bars with `load_binance_bars(configs[0])`, then reuses that
  list for every generated config.
- `load_binance_bars()` currently filters by `backtest.stop` but not by
  `backtest.start`. If the data folder contains earlier bars, fast mode can
  process pre-start bars.
- Fix this before trusting fast-vs-standard result parity.

2. Standard sweep mode:

Target proof runs through the SweepManager process-pool task path.

Purpose:

- Generate normal backtest configs.
- Run each config through a process-pool task using the canonical backtest loop.
- Prove generated sweepruns can use the canonical backtest loop.

Skip:

- full result schema.
- mainnet/testnet/simnet mode.

Proof commands live in `wiki/testing.md`.

## result shape

Sweep persistence:

- `SweepRow.config_json` is the loaded sweep config.
- `SweepRow.results_json` is the whole sweep result summary.
- The sweep DB owns generated sweeprun config summary and final result
  summary.
- Sweep existence is the sweep DB file.
- Sweeprun existence is a `sweeprun` row inside the sweep DB.
- Botrun existence is a `botrun` row inside the sweep DB.
- Queue setup creates sweeprun rows only.
- A botrun row is created only when a sweeprun is executing, a signaler signals
  a bot start, and executor/runtime/risk checks agree that a bot can start.
- If a sweeprun never starts a bot, it has no botrun rows.
- Timing belongs under `results_json.timing`.
- Do not add separate sweeprun timing columns such as `elapsed_ms`,
  `load_ms`, `indicator_ms`, or `execution_ms`.

Minimum result:

- config id.
- pnl.
- win count.
- loss count.
- trade count.
- max drawdown.
- speed timing.

Speed timing:

- total ms.
- bars processed.
- bars per second.
- worker count.

Speed timing is mandatory for every sweep proof. It measures total sweep wall
time and throughput, not market time.

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
get sweep id from server DB sequence
create sweep SQLite DB
record sweep started_at
generate permutations
insert sweeprun rows with generated configs
submit process-pool tasks
create botrun rows only when bot instances actually start
store each sweeprun result summary in the sweep DB
store sweep timing in sweep.results_json
mark sweep complete/error
```

## current context shape

This may still change, but the current shape is better than passing loose IDs
through every child.

- `IdCtx` is a small dataclass for internal sweep child objects.
- `IdCtx` carries only IDs and bot config needed by children:
  `sweep_id`, `sweeprun_id`, `bot_id`, `account_id`, and `bot_config`.
- `datastore` means the `Datastore` verb boundary used to write rows.
- The sweep DB name/path is passed separately from `IdCtx`.
- `Position`, `Order`, and `Fill` receive `IdCtx` and use fields directly.
- Internal sweep code does not revalidate `IdCtx`; missing fields should fail
  loud.
- External config/templates are validated at the boundary with Pydantic.
- DB primary keys and references use explicit `<thing>_id` names.

## template shape

Current author-facing sweep template rules live in `wiki/templates-sweeps.md`.

Rules:

- `data.*` defines grouped data sets.
- `signalers.*` defines grouped signaler sets.
- `executors.*` defines grouped executor sets.
- Values inside one set expand internally.
- Expanded data sets cross with expanded signaler sets, executor sets, and
  expanded risk values.
- Generated sweepruns are concrete scalar configs and are validated before
  records are created.
