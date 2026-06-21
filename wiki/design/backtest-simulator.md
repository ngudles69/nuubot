---
title: backtest simulator design
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [design, backtest, simulator]
---

# backtest simulator design

## data and backtest

- First loop reads both BBO and candles.
- `ExchangeWsData` is the live websocket data source.
- `Clock.tick()` waits on wall time for live/paper.
- `Clock.now_ms()` only returns current clock time.
- Live/paper `Clock.tick()` waits for the configured loop cadence.
- Live/paper `Clock.tick()` does not wait for a new BBO or bar.
- Backtest uses a plain replay loop. It pulls the next timestamp batch,
  advances `ReplayClock`, ingests the whole batch, then dispatches due runtime
  timers.
- Backtest should use the same runtime loop later by swapping:
  - `ExchangeData`
  - `ExchangeAccount`
  - `Clock`
- `workspace/data/**` holds historical data.
- Current historical data under `workspace/data` comes from Binance.
- Do not create separate `LiveRuntime`, `PaperRuntime`, and `BacktestRuntime`
  until the loop truly diverges.

## simulator

Simulator is first-class for paper/backtest work, but it stays a standalone
module. It should not make the live bot harder to read.

Likely source:

- Review the working `nuutrader6` simulator first.
- Reuse the shape if it stays simple enough.
- Do not clone simulator complexity into the bot.

Useful hooks:

- Ingest BBO/candles into the simulator.
- Trigger fills from simulated market data.
- Evaluate simulated open orders against latest market data.
- Emit simulated order, fill, account, and position updates.
- Update/send events in a websocket-like stream.
- Optionally own its own websocket if that keeps live and simulated data paths
  simpler.

Backtest/paper runtime should treat simulator output like exchange data and
exchange account responses where practical.

Bot rule:

- Live bot uses real `ExchangeData` and `ExchangeAccount`.
- Paper/backtest bot can use simulator-backed data/account objects.
- Simulator internals stay inside the simulator module.
