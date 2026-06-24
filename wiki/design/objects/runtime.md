---
title: runtime design
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [design, runtime, bot]
---

# runtime design

## purpose

Runtime is the master composer. It owns the visible bot sequence and calls only
the objects it composes.

Runtime should read close to `BlackBot.py`: direct setup, direct loop, direct
calls into owned objects. Every runtime line or connection should map to one
composed object.

Allowed composed objects:

- `Config`
- `Clock`
- `WsData` or `FileData`
- `Account`
- `Datastore`
- `Signaler`
- `Executor`
- `CommandServer`
- `Risk`

Runtime must not reach into grandchildren such as indicators, positions,
orders, fills, or simulator internals.

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `loop()`
- `loop_once(event)`
- `exit(reason)`
- `status()`

Runtime receives:

- config file path through the module entrypoint.
- timer events from `Clock`.
- market snapshots from `WsData` or `FileData`.

Runtime outputs:

- lifecycle state.
- runtime telemetry.
- stop/error state.
- calls into owned objects.
- command status.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Config path or loaded Config. | Initialized Runtime. | Initializes CommandServer first, then loads config and composes owned objects. If CommandServer cannot write runtime ownership to DB, startup fails. |
| `start()` | Initialized Runtime. | Running Runtime. | Starts owned objects in runtime order and registers the runtime timer. |
| `stop()` | Running or failed Runtime. | Stopped Runtime. | Stops owned objects and exposes dirty cleanup state if cleanup fails. |
| `loop()` | Running Runtime. | Completed run. | Uses wall clock for live modes and replay loop for backtest. Does not alter `loop_once` sequence. |
| `loop_once(event)` | Clock event. | One runtime unit of work. | Preserves approved main flow: max-loop check, market snapshot, signaler, risk, executor, telemetry/exit. |
| `exit(reason)` | Reason string. | Runtime stop requested. | Cancels runtime timer and records stop reason. |
| `status()` | Current runtime state. | JSON-safe status. | Returns liveness/status/telemetry for command server. |

## processing

Internal functions:

- load config.
- initialize command server.
- compose owned objects.
- initialize owned objects.
- start data/account/signaler/executor flow.
- dispatch each loop tick.
- stop and cleanup owned objects.

## key helpers

- object composer.
- runtime mode selector.
- bot log path builder.
- status builder.
- telemetry logger.
- max-loop guard.

## notes

- Do not change the main loop order without explicit user approval.
- Runtime can be the largest file because it owns the visible bot story.
- Runtime should call one composed object per meaningful line.
- Runtime must not load indicators, parse indicator config, or interpret
  indicator rows.
- Runtime must not reach into simulator, ledger, positions, orders, or fills.
- Validate data at external boundaries. Trust internal object state after a
  successful call.
- Do not write defensive internal guards like `if command: command.stop()`.
- Track successfully started components and stop them directly in reverse order
  during cleanup.

## bot runtime

`Bot` composes and glues the objects together.

The runtime loop is the design anchor. Keep it clear before filling components
with implementation detail.

Canonical loop:

```text
while running:
  await Clock.tick()
```

`Bot.loop_once(event)` is the bot unit of work:

```text
Bot.loop_count += 1

if max_loop reached:
  stop runtime
  return

market = await ExchangeData.snapshot(Clock.now_ms())
if no market:
  stop runtime
  return

if market bar is not new:
  return

risk_score = await Risk.score()
if Risk.exit():
  stop runtime
  return

signal = await Signaler.loop_once(market, at=Clock.now_ms())
if Signaler.exit():
  stop runtime
  return

await Executor.loop_once(market, signal)
```

Runtime binding:

```text
mainnet   = wsdata + mainnet execution + wall Clock
testnet   = wsdata + testnet execution + wall Clock
simnet    = wsdata + simulator execution + wall Clock
backtest  = filedata + simulator execution + replay Clock
```

`runtime.mode` is first-class and dominant. It is the configured value. The
data and execution networks are derived from it:

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

`bar` means candle.

`ExchangeData` owns websocket buffering:

- BBO buffer keeps only the latest BBO.
- Bar buffer keeps OHLCV bars.
- The loop processes only BBO/bar data newer than `last_bbo_ms` and
  `last_bar_ms`.
- If no newer market data exists, the bot skips trading work but remains
  command-responsive.

## intent story

Bot coding, bot sequence, and what is in or out of the `Bot` view must always
start from the intent angle first, then the implementation detail.

The `Bot` file must tell the bot's intent story. A reader should be able to see
what the bot intends to do at each step, what components exist to satisfy that
intent, how the components interact, what runs each loop, and whether any
expected component is missing.

Minimize hiding components from the `Bot` view. Hide only how each component
works inside the component that owns it.

Example:

```text
Bot intent: load config so config controls execution.
Visible in Bot: config is loaded.
Hidden in ConfigData: whether config came from TOML, JSON5, DB, or somewhere else.

Bot intent: load exchange meta because orders need exchange control data.
Visible in Bot: meta is loaded.
Hidden in ExchangeMeta: freshness check, fetch-all, upsert, symbol lookup.

Bot intent: initialize account because the bot must know the account exists and
the exchange accepts it.
Visible in Bot: account is initialized.
Hidden in ExchangeAccount: exchange calls, validation details, credential checks.
```

```text
Bot
  ConfigData
  Datastore
  CommandServer
  Clock
  ExchangeMeta
  ExchangeData / ExchangeWsData
  ExchangeAccount
  Risk
  Signaler list
  Executor list
  Simulator when running simnet/backtest later
```

Interaction rule:

```text
Bot coordinates.
Executor decides.
ExchangeAccount executes.
Position, Order, and Fill record.
Risk scores.
Signaler signals.
```

The visible intent flow should answer:

- What components exist.
- How each component is used.
- How components interact.
- Whether an expected component is missing.
- What data is checked each loop.
- What risk checks exist.
- How risk affects size, hold, or exit behavior.
- What signals are checked.
- What exit conditions exist.
- What executor ran.
- What state was inserted or updated.

## clock

All code after initialization uses the same clock API:

```text
await clock.tick()
now_ms = clock.now_ms()
```

`Clock.tick()` waits on wall time, builds due `TimeEvent` items, and calls each
timer's callback. `ReplayClock` does not pull data. Backtest replay code sets
replay time and dispatches due timers after ingesting a timestamp batch.
`now_ms()` only returns current clock time.

Timer shape:

```text
Clock
  TimeEvent
  Timer
```

Runtime registers one timer first:

```text
clock.set_timer("runtime", loop_seconds, Bot.loop_once)
```

Mainnet/testnet/simnet `tick()` waits for the configured loop cadence. It does
not wait for new BBO or bar data. `now_ms()` returns wall time.

Backtest does not use wall sleep and does not let the clock pull market data.
`Runtime.loop_backtest()` drives replay:

```text
batch = next(replay_batches)
ReplayClock.set_time(batch.ts_ms)
FileDataEngine.ingest_replay_batch(batch)
ReplayClock.dispatch_due(batch.ts_ms)
```

Core replay rule:

```text
Data engine updates market snapshot.
Clock/replay driver dispatches Runtime.loop_once().
Runtime.loop_once() reads snapshot and runs bot logic.
```

| Concept | Mainnet / Testnet / Simnet | Backtest |
| --- | --- | --- |
| Driver | Wall time through asyncio. | Prepared replay data through a plain loop. |
| Wait | `asyncio.sleep(...)` waits for real time. | No wait; consume next replay batch. |
| Data arrival | Websocket messages update market buffers. | Replay loop ingests timestamp batches. |
| Time advance | Clock samples wall time after sleep. | Replay clock jumps to batch timestamp. |
| Loop trigger | Due timer dispatches `loop_once()`. | Batch ingest completes, then due timer dispatches once for that timestamp. |
| Snapshot shape | Latest BBO/price plus bars by interval. | Same shape after batch ingest. |

Same-timestamp backtest events collapse into one timestamp batch:

```text
05:00:00  1m replay event
05:00:00  1h completed bar event
```

`loop_once()` sees both only after they are closed and ingested.

## data engines

- `WsDataEngine` is the live websocket data source.
- `FileDataEngine` is the historical file data source.
- `workspace/data/**` holds historical data.
- Current historical data under `workspace/data` comes from Binance.
- Wall-time modes do not wait for a new BBO or bar.
- Backtest snapshot must only expose data available at the replay timestamp.
- Do not create separate mode-specific runtime classes until the loop truly
  diverges.

## simulator

Simulator is first-class for simnet and backtest work, but it stays a
standalone module. It should not make the live bot harder to read.

Useful hooks:

- Ingest BBO/candles into the simulator.
- Trigger fills from simulated market data.
- Evaluate simulated open orders against latest market data.
- Emit simulated order, fill, account, and position updates.
- Update/send events in a websocket-like stream.

Bot rule:

- Mainnet/testnet bot uses real `ExchangeData` and real `ExchangeAccount`.
- Simnet/backtest bot can use simulator-backed account/execution objects.
- Simulator internals stay inside the simulator module.

## command server

`CommandServer` lives in `command.py`.

It is DB-backed and uses the command table. It is not aiohttp and it does not
own a port.

Runtime startup:

```text
command = CommandServer(bot_id, datastore, runtime_callbacks)
command.init()
```

`CommandServer.init()` writes:

```text
status = running
pid = os.getpid()
run_token = new uuid
started_at = now
last_seen_at = now
```

If that DB update fails, runtime startup fails.

Runtime updates bot rows only with matching ownership:

```text
where bot_id = current bot
  and run_token = current run token
```

This prevents stale runtime processes from overwriting newer runs.

Command table:

```text
command_id
bot_id
command
payload_json
status
result_json
created_at
claimed_at
completed_at
error
```

Supported commands first:

```text
stop
status
```

Deferred:

```text
freeze
```

## telemetry

Minimum runtime observability:

- Bot row `pid`, `run_token`, `status`, and `last_seen_at`.
- Loop count.
- Last loop timestamp.
- Last BBO processed timestamp.
- Last bar processed timestamp.
- BBO received count.
- Candle received count.
- Positions opened count.
- Positions closed count.
- Positions canceled count.
- Active positions count.
- Latest risk score.
- Custom telemetry JSON per bot/executor.

Telemetry is for quick validation, not a large metrics system.

Status is in memory for the running process:

- Runtime writes heartbeat through `CommandServer`.
- CLI may check heartbeat freshness and PID liveness for operator display.
