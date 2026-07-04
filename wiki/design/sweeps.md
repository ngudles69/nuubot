---
title: sweeps design
created: 2026-06-20
updated: 2026-07-04
type: wiki
status: active
tags: [design, sweeps]
---

# sweeps design

## definitions

- `sweep`: hyperparameter definition that permutates into sweepruns.
- `sweeprun`: one generated parameter set over one market/window period.
- `sweeprun runner`: fixed-period server-run simulator for one sweeprun.
- `sweep signaler`: long-lived signal component owned by the sweeprun runner.
- `sweep bot`: active executor instance started by a sweeprun entry signal.
- `botrun`: one actual bot start/stop episode inside a sweeprun.
- `ProcessPoolExecutor` runs sweeps as stateless tasks.

Ownership:

```text
Sweep
  creates Sweeprun rows

Sweeprun
  owns replay feed
  owns sweep signaler
  owns active bot slot
  owns counters, timing, and final sweeprun result persistence

Sweep bot / Executor
  owns trade state
  receives event + signal + risk_score
  decides its own exit
  exposes status
```

`Sweeprun` is not a bot. It is the sweep equivalent of a server run over a
fixed historical period.

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
- executor account name.
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

- `[sweep].savedb = true` stores signal/account/botrun/position/order/fill
  detail rows; `false` stores only sweep and sweeprun status/result rows for
  speed comparison. Detail rows are buffered by the worker and written once
  when the sweeprun result is saved.
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
- Sweep trade sizing defaults to `investment_usdc = 10000`,
  `trade_use = "pct"`, `trade_amount = 100`, and `trade_pct = 2.0`.
- `trade_use = "pct"` uses `investment_usdc * trade_pct / 100` per trade.
  `trade_use = "amount"` uses `trade_amount` per trade.
- The runner tracks `current_balance_usdc` across botruns and does not start a
  new trade when the configured trade size or the `10` USDC minimum cannot be
  funded.

Minimum result metrics:

Result JSON may group metrics by category. Metric keys inside each group stay
flat. For example, store `risk.max_dd`; do not store or emit `risk_max_dd`.

Identity:

- sweep_id.
- sweeprun_id.
- symbol.
- start.
- stop.
- signaler.
- executor.
- params.

Activity:

- ticks.
- signals.
- positions.
- orders.
- fills.
- trades.

PnL:

- starting_balance.
- ending_balance.
- gross_win.
- gross_loss.
- net_pnl.
- net_pnl_pct.
- fees.
- slippage.

Trade quality:

- wins.
- losses.
- breakeven.
- win_rate.
- avg_win.
- avg_loss.
- largest_win.
- largest_loss.
- payoff_ratio.

Edge:

- profit_factor.
- ev.
- ev_pct.

Streaks:

- max_win_streak.
- max_loss_streak.

Risk:

- max_dd.
- max_dd_pct.
- dd_duration.

Return/risk:

- sharpe.
- sortino.
- calmar.
- recovery_factor.

Time:

- avg_trade_duration.
- exposure_pct.
- elapsed_ms.

Sweep report:

- canonical terminal command is
  `uv run python -m nuubot.sweeps.report <sweep_id>`.
- daily shell shortcut is `./report.sh <sweep_id>`.
- report implementation lives under `nuubot/cli/**`.
- keep one report command; do not add parallel sweep result CLIs.
- do not sum sweeprun return or PnL percentages.
- show per-sweeprun best and worst.
- show min, p25, median, mean, p75, and max for return and risk metrics.
- sum only counts and timing such as ticks, orders, fills, and wall time.

TUI:

- common command is `./tui.sh`.
- CLI command is `uv run python -m nuubot.cli tui`.
- module command is `uv run python -m nuubot.cli.tui`.
- TUI implementation lives under `nuubot/cli/tui/**`.
- Home menu starts with sweeps and bots.
- Sweeps screen lists sweep rows and supports digit-prefix jumping by sweep id.

Speed timing:

- total ms.
- ticks processed.
- ticks per second.
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

## signaler data contract

Sweep signalers are strategy signal modules. A signaler can use any number of
datasets: different symbols, different timeframes, and different indicator
families. The sweep does not know why a signaler needs each dataset.

The shared contract is:

- `SwData`: one loaded market dataset owned by one component.
- `SwSignal`: one standardized signal output.
- `SwSignaler`: lifecycle protocol for sweep signalers.

`SwData` is the loaded-data container. The signaler declares its own named
datasets during `init()`. Each `SwData` is complete at construction time; before
load, `frame` is an empty Polars dataframe. The generic data loader fills
`frame`. The signaler then uses the same object for calculation and checks.

```text
SwData
  name
  symbol
  timeframe
  warmup_bars
  max_age_ms
  start_ms
  stop_ms
  frame
```

Flow:

```text
signaler.init(config, symbol)
signaler.load(loader, start_ms, stop_ms)
signaler.calc()
signal = signaler.check(now_ms)
```

Rules:

- The loader is generic. It loads market data only.
- The loader is not owned by a signaler, a sweep, or an executor.
- The loader returns a Polars dataframe.
- Each signaler owns its named `SwData` fields.
- Sweeprun owns replay `SwData` for the event loop.
- Executors consume bars and signals; they do not declare signaler data.
- `SwData.frame` is the signaler's working data.
- Sweep code must not inspect signaler datasets.
- `load()` decides how much history each signaler dataset needs, sets the
  dataset load window, then loads it.
- `calc()` calculates the full loaded dataset, including warmup rows.
- `check()` picks the latest closed calculated row as of the requested time and
  returns that row's `SwSignal`.
- Sweeprun keeps calling `check()` for the full replay window.
- Sweeprun decides whether an entry signal can start a bot. That state is not
  signaler concern.
- `calc()` adds whatever columns the signaler needs to its frames.
- `check()` reads those custom columns and returns `SwSignal`.
- Indicator column names are private to each signaler.
- Voting rules are private to each signaler: any-one, two-of-three, all-of-three,
  regime filters, or other custom logic.
- Generic sweep code must not reference signaler calculation columns.

Lifecycle intent:

```text
init(config, symbol)
  validate config
  validate timeframe
  validate signaler parameters
  store signaler settings
  define named SwData fields with empty frames
  setup internal caches

load(loader, start_ms, stop_ms)
  determine each dataset's warmup bars
  determine each dataset's load start and stop
  load each owned dataset through the generic loader
  validate enough data was loaded

calc()
  calculate the full loaded dataset
  add signaler-private columns to each frame
  build any private lookup cache needed by check()

check(now_ms)
  select the latest closed calculated row as of now_ms
  fail loud if that row is too stale for the dataset
  return SwSignal only
```

`init()` is the config boundary. If it passes, the signaler has valid settings
and named dataset fields. `load()` is the data boundary. It is where the
signaler decides how much history each dataset needs. `calc()` is the indicator
boundary. It can use Polars, TA-Lib, NumPy, or helper functions, but it stores
the result back on its own frames. `check()` is the signal boundary. It does not
know or care whether a bot is running.

`SwSignal` is the only standardized output:

```text
enter_long
enter_short
exit_long
exit_short
reason
```

Supported authored timeframes are:

```text
1m, 5m, 15m, 1h, 4h, 1d
```

`SwEmacross` is the first reference implementation. It should stay simple, but
it must show the complete pattern: validate config, define named signaler data,
load frames, calculate columns, and check the latest complete calculated bar.

## executor comparison

Compare executors by running normal sweepruns.

Sweep executors use the sweep-local `SwExecutor` protocol:

```text
init()
start()
next(bar, signal, risk_score)
stop(last_event, ticks_processed) -> result
status
telemetry()
```

Sweeprun owns the replay loop, sweep signaler, active bot slot, timing, final
row status, and final sweeprun DB persistence. The active executor owns strategy
state, trade entry/exit behavior, strategy telemetry, and its own stopped
status. `SwTradeBot` is the reference sweep executor shape.

Current runner loop:

```text
for event in replay:
  signal = signaler.check(event.ts_ms)

  if active_bot is None and signal has entry:
    active_bot = create/start executor

  if active_bot is not None:
    active_bot.next(event, signal, risk_score)

  if active_bot is not None and active_bot.status == "stopped":
    active_bot = None
```

When replay data ends, `Sweeprun.stop()` stops any active bot gracefully before
saving the final sweeprun result.

Account detail now follows the `TradingAccount` boundary: one Hyperliquid
account owns exchange/simulator access plus one ledger. Sweeprun feeds replay
ticks to the active executor through `next()`. The active executor/bot owns
account `ingest_bbo()`, throttled `recon()`, strategy decisions, and order
intent submission through `place_orders()` / `cancel_orders()` /
`close_positions()`. The executor definition owns the selected account name,
and sweep create/run validates that name against loaded Hyperliquid
credentials. Ledger, position, order, fill, simulator, and recon details remain
under the active bot/executor side of the boundary, not in Sweeprun.

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
