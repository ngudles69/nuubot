---
title: backtest simulator design
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [design, backtest, simulator]
---

# backtest simulator design

## canonical modes

`runtime.mode` is first-class and dominant. It is the configured value. The
data and execution networks are derived from it:

Code owns these as enums in `nuubot/core/dtypes.py`:

- `Mode`: `mainnet`, `testnet`, `simnet`, `backtest`
- `DataNetwork`: `wsdata`, `filedata`
- `ExecNetwork`: `mainnet`, `testnet`, `simulator`

| Mode | Derived `data_network` | Derived `exec_network` | Meaning |
| --- | --- | --- | --- |
| `mainnet` | `wsdata` | `mainnet` | Websocket market data, real mainnet execution. |
| `testnet` | `wsdata` | `testnet` | Websocket market data, real testnet execution. |
| `simnet` | `wsdata` | `simulator` | Websocket market data, simulated execution. |
| `backtest` | `filedata` | `simulator` | Historical file data, simulated execution. |

`data_network` selects `WsDataEngine` or `FileDataEngine`. `exec_network`
describes where execution goes. They are derived properties, not authored
config fields. `mode` drives them and prevents invalid combinations.

Sweep is not a bot runtime mode. It is its own execution shell and uses its own
log format. Generated botruns may use backtest binding, but sweep itself does
not use `bot_<mode>_<bot_id>.log`.

## data and backtest

- First loop reads both BBO and candles.
- `WsDataEngine` is the live websocket data source.
- `Clock.tick()` waits on wall time for live network modes.
- `Clock.now_ms()` only returns current clock time.
- Mainnet, testnet, and simnet `Clock.tick()` wait for the configured loop
  cadence.
- Wall-time modes do not wait for a new BBO or bar.
- Backtest uses a plain replay loop. It pulls the next timestamp batch,
  advances `ReplayClock`, ingests the whole batch, then dispatches due runtime
  timers.
- Backtest should use the same runtime loop later by swapping:
  - `ExchangeData`
  - `ExchangeAccount`
  - `Clock`
- `workspace/data/**` holds historical data.
- Current historical data under `workspace/data` comes from Binance.
- Do not create separate mode-specific runtime classes
  until the loop truly diverges.

## simulator

Simulator is first-class for simnet and backtest work, but it stays a
standalone module. It should not make the live bot harder to read.

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

Simnet/backtest runtime should treat simulator output like exchange data and
exchange account responses where practical.

Bot rule:

- Mainnet/testnet bot uses real `ExchangeData` and real `ExchangeAccount`.
- Simnet/backtest bot can use simulator-backed account/execution objects.
- Simulator internals stay inside the simulator module.
