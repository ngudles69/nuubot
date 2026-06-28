---
title: sweep flow
created: 2026-06-26
updated: 2026-06-26
type: wiki
status: active
tags: [flow, sweep, backtest]
---

# sweep flow

## purpose

Sweep generates many botrun configs and runs them to compare results.

Sweep is a runtime mode for sweep-generated botruns.

Generated botruns usually use:

```text
runtime.mode = sweep
```

## load

```text
sweep_config = load sweep file
parameter_grid = expand params

for each parameter set:
  botrun_config = copy base botrun config
  set runtime.mode = sweep
  set bot_id
  set parameter values
```

## fast sweep

Fast sweep skips runtime/clock ceremony for speed.

```text
bars = load_binance_bars(configs[0])

for config in configs:
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
it may skip runtime lifecycle, command server, DB writes, and per-loop logs.

Current code caveat:

- Fast mode loads bars once with `load_binance_bars(configs[0])`.
- `load_binance_bars()` currently filters by `backtest.stop` but not by
  `backtest.start`.
- Fix that before trusting fast-vs-standard parity.

## standard sweep

Standard sweep proves generated botruns through normal runtime backtest.

```text
for config in configs:
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
