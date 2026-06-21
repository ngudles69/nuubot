---
title: runtime design
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [design, runtime, bot]
---

# runtime design

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

signal = await Signaler.process(market)
if Signaler.exit():
  stop runtime
  return

await Executor.loop_once(market, signal)
```

Runtime binding:

```text
live      = real ExchangeData + real ExchangeAccount + wall Clock
paper     = real ExchangeData + simulator ExchangeAccount + wall Clock
backtest  = historical ExchangeData + simulator ExchangeAccount + replay Clock
```

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
  Simulator when running paper/backtest later
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

Live/paper `tick()` waits for the configured loop cadence. It does not
wait for new BBO or bar data. `now_ms()` returns wall time.

Backtest does not use wall sleep and does not let the clock pull market data.
`Runtime.loop_backtest()` drives replay:

```text
batch = next(replay_batches)
ReplayClock.set_time(batch.ts_ms)
FileDataEngine.ingest_replay_batch(batch)
ReplayClock.dispatch_due(batch.ts_ms)
```

## command server

- Every bot has its own `aiohttp` command server.
- Bind to `127.0.0.1`.
- No auth token for now.
- No central command server.
- No DB command table for normal user commands.
- Commands should respond immediately.
- DB `running` status is not liveness proof.
- Running bot liveness comes from HTTP status/ping.
- Command port comes from a simple DB port table.

Port table:

```text
port_id
port
in_use
bot_id
updated_at
```

Port acquire belongs to `CommandServer` and uses the datastore connection.

Acquire flow:

```text
while:
  select first free port ordered by port_id
  if none:
    insert next port as in_use for this bot
    break
  update selected port to in_use where in_use is false
  if update changed one row:
    break
```

Release flow:

```text
update port table set in_use = false, bot_id = null where port_id = current
```

Do not build stale cleanup yet. If a stale lease becomes painful, add a tiny
operator cleanup later.

Minimum bot command routes:

```text
GET /ping
GET /status
POST /stop
```

## telemetry

Minimum runtime observability:

- HTTP `GET /ping` for process liveness.
- HTTP `GET /status` for current bot status.
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

- `GET /ping` proves the process responds.
- `GET /status` exposes runtime state and custom telemetry.
- Do not persist heartbeat to datastore for the first implementation.
