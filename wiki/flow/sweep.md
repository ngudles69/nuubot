---
title: sweep flow
created: 2026-06-26
updated: 2026-06-29
type: wiki
status: active
tags: [flow, sweep, backtest]
---

# sweep flow

## purpose

Sweep generates many bot configs and runs them to compare results.

Sweep is a Ray task fanout for sweep-generated bot configs.

Generated bot configs usually use:

```text
runtime.mode = sweep
```

## load

```text
sweep_config = load sweep file
sweep_id = server DB sequence
sweep_db = workspace/db/sweep_<sweep_id>.db
create sweep DB and tables if missing
parameter_grid = expand params

for each parameter set:
  bot_config = copy base bot config
  set runtime.mode = sweep
  set parameter values
```

## fast sweep

Fast sweep skips runtime/clock ceremony for speed.

```text
bars = load_binance_bars(configs[0])

for config in configs:
  submit Ray task

Ray task:
  create sweeprun DB and tables if needed
  signaler = SignalerEmaCross(config)
  signals = signaler.ingest_many(bars)

    executor = ExecutorTrade(config)
    for bar, signal in zip(bars, signals):
        executor.loop_once(bar, signal)

    executor.stop(last_bar)
    collect result

print summary
print best results
```

Clock interaction:

```text
no Clock
no Runtime.next()
```

Fast sweep uses ordered bars directly. It should not change trading logic, but
it may skip runtime lifecycle, command server, per-loop DB writes, and per-loop
logs.

Current code caveat:

- Fast mode loads bars once with `load_binance_bars(configs[0])`.
- `load_binance_bars()` currently filters by `backtest.stop` but not by
  `backtest.start`.
- Fix that before trusting fast-vs-standard parity.

## standard sweep

Standard sweep proves generated bot configs through normal runtime backtest.

```text
for config in configs:
  submit Ray task

Ray task:
  create sweeprun DB and tables if needed
  runtime = Runtime(config)
  runtime.init()
  runtime.start()
    runtime.loop()
    runtime.stop()
    collect runtime.result

print summary
print best results
```

Clock interaction:

```text
Runtime.loop()
  await clock.run(Runtime.next)

Clock.run()
  for batch in FileData.replay_batches():
    Clock.set_time(batch.ts_ms)
    FileData.ingest_replay_batch(batch)
    await Runtime.next()
```

Standard sweep uses the same backtest clock path as one-off backtest.

Rerun/reset:

```text
delete sweep_<id>.db or sweeprun_<id>.db
submit Ray task again
```

## compare

Use fast sweep to search.

Use standard sweep to prove winners through the canonical runtime path.

Compare:

- pnl.
- trades.
- win/loss count.
- max drawdown.
- entry timestamps.
- exit timestamps.
- missed or extra trades.
