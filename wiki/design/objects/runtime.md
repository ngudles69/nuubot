---
title: runtime design
created: 2026-06-20
updated: 2026-06-29
type: wiki
status: active
tags: [design, runtime, bot]
---

# runtime design

## purpose

Runtime is the master composer. It owns the visible bot sequence and calls only
the objects it composes.

Runtime is plain Python and must run without a process manager. Managed live
runs start the same Runtime path.

Runtime should read close to `BlackBot.py`: direct setup, direct loop, direct
calls into owned objects. Every runtime line or connection should map to one
composed object.

Allowed composed objects:

- `Nuubot`
- instance SQLite DB
- `Clock`
- `WsData` or `FileData`
- `Account`
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
- `next(event optional)`
- `exit(reason)`
- `status()`

Runtime receives:

- `exec_network` and `bot_id` from manual/notebook code or managed process
  entrypoint.
- server infra through short `server.db` reads when needed.
- bot state from `bot_setup(exec_network, bot_id)`.
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
| `init()` | `exec_network`, `bot_id`. | Initialized Runtime. | Checks server infra/meta once, calls `bot_setup(exec_network, bot_id)` once, initializes CommandServer, and composes owned runtime objects. If server check or bot DB setup fails, startup fails. |
| `start()` | Initialized Runtime. | Running Runtime. | Starts owned objects in runtime order and registers the runtime timer. |
| `stop()` | Running or failed Runtime. | Stopped Runtime. | Stops owned objects and exposes dirty cleanup state if cleanup fails. |
| `loop()` | Running Runtime. | Completed run. | Calls `clock.run(Runtime.next)`. Clock owns wall-time vs replay triggering. |
| `next(event optional)` | Optional Clock event. | One runtime unit of work. | Preserves approved main flow: command, market snapshot, mandatory reconcile, signaler/risk/executor, telemetry/status. |
| `exit(reason)` | Reason string. | Runtime stop requested. | Cancels runtime timer and records stop reason. |
| `status()` | Current runtime state. | JSON-safe status. | Returns liveness/status/telemetry for command server. |

## processing

Internal functions:

- receive exec network and bot id from notebook/manual code or BotManager.
- load/create bot state through `bot_setup`.
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

Runtime trigger:

```text
clock.run(Runtime.next)
```

`Runtime.next(event optional)` is the bot unit of work.

Runtime focuses on sequence:

- how loops are triggered.
- what inputs are gathered.
- what checks run.
- in what order checks run.
- what object receives each action.
- what status is written at the end.

Runtime does not own signaler internals, executor internals, account internals,
ledger internals, or datastore row meaning.

Canonical loop:

```text
next(event optional)
  now = Clock.now_ms()

  command = CommandServer.next_command()

  if command is kill:
    exit("kill")
    # Runtime exits. Bot state stays recoverable.
    end_loop()
    return

  market = Data.snapshot(now)
  executor_state = Executor.recon(market)

  Recon is a must-do step before any non-kill operation. Nothing trades,
  closes, stops, checks terminal state, or submits orders before recon.
  Fresh start should recon to flat/no-op state. Restart should recon
  to the current exchange/account/ledger state.

  if max_loop reached:
    exit("max_loop")
    end_loop()
    return

  if executor_state is terminal stopped or terminal error:
    exit("terminal")
    end_loop()
    return

  if command is stop:
    Executor.request_terminal_stop()

  signaler_state = Signaler.observe(market)

  if Executor.is_active():
    risk_state = Risk.score()
    if Risk.exit():
      Executor.request_terminal_stop()
    if Signaler.exit():
      Executor.request_terminal_stop()
    if Executor.exit():
      Executor.request_terminal_stop()
    if Executor.is_closing():
      await Executor.handle_order_exits(market)
      if Executor.is_closed():
        Executor.mark_terminal_stopped()
        exit("stopped")
      end_loop()
      return

  if Executor.is_flat():
    if signaler_state has no usable entry data:
      end_loop()
      return
    decision = Signaler.signal()
    if decision is entry:
      await Executor.enter(decision)
    end_loop()
    return

  risk_state = Risk.score()
  await Executor.handle_order_exits(market)
  if Executor.can_submit_orders():
    await Executor.submit_orders(market, signaler_state, risk_state)

  end_loop:
    CommandServer.heartbeat()
    Datastore writes status/events through owning objects
    log telemetry
```

Runtime command stop semantics:

- `kill`: immediate runtime exit. Do not cancel orders and do not close
  positions. The next runtime start must reconcile existing exchange/account
  state and continue from that state.
- `stop`: graceful bot close. Runtime keeps looping as long as needed while
  Executor cancels/settles orders and closes positions. Once Executor reports
  closed, the bot is marked terminal stopped and cannot be restarted.
- Terminal `stopped` and terminal `error` end the bot. They are not restartable
  states.
- Non-terminal runtime exit, including `kill`, is restartable. Restart uses the
  same loop as first start: reconcile current exchange/account/ledger state,
  then continue from that state.
- Fresh start also runs reconcile. The expected result is flat/no-op, not a
  special startup branch.
- Only `kill` can skip reconcile, because no trading/closing operation runs
  after it.

Current runnable implementation has not caught up to this target sequence.

Implementation gaps:

- rename `loop_once` to `next`.
- route live and backtest through `clock.run(Runtime.next)`.
- move backtest replay driving into Clock.
- wire bot-local DB command polling into CommandServer.
- add mandatory reconcile before every non-kill operation.
- add started/flat/closing state handling through Executor.
- add order-exit handling, new-order submission, and DB status writes through
  owning objects.

Runtime binding:

```text
mainnet   = mainnet data + mainnet execution + wall Clock
testnet   = testnet data + testnet execution + wall Clock
simnet    = mainnet data + simnet execution + wall Clock
backtest  = filenet data + simnet execution + replay Clock
sweep     = filenet data + sweep execution + replay Clock
```

`runtime.mode` is first-class and dominant. It is the configured value. The
data and execution networks are derived from it:

| Mode | Derived `data_network` | Derived `exec_network` | Meaning |
| --- | --- | --- | --- |
| `mainnet` | `mainnet` | `mainnet` | Mainnet market data, real mainnet execution. |
| `testnet` | `testnet` | `testnet` | Testnet market data, real testnet execution. |
| `simnet` | `mainnet` | `simnet` | Mainnet market data, simulated execution. |
| `backtest` | `filenet` | `simnet` | Historical file data, simulated execution. |
| `sweep` | `filenet` | `sweep` | Historical file data, sweep execution. |

`data_network` selects `WsDataEngine` or `FileDataEngine`. `exec_network`
describes where execution goes. They are derived properties, not authored
config fields. `mode` drives them and prevents invalid combinations.

Sweep is a bot runtime mode for sweep-generated bot configs. Fast sweep runs as
process-pool tasks and may still use its own tight execution shell for speed.

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
Hidden in TradingAccount: exchange calls, validation details, credential checks.
```

```text
Bot
  ConfigData
  Instance SQLite DB
  CommandServer
  Clock
  ExchangeMeta
  ExchangeData / ExchangeWsData
  TradingAccount
  Risk
  Signaler
  Executor
  Simulator when running simnet/backtest later
```

Interaction rule:

```text
Bot coordinates.
Executor decides.
TradingAccount executes.
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
await clock.run(Runtime.next)
now_ms = clock.now_ms()
```

Clock init decides whether this mode uses timer events:

```text
Clock(mode, data, loop_seconds)
  if mode is backtest:
    timer = None
  else:
    timer = Timer("runtime", loop_seconds)
```

`now_ms()` only returns current clock time.

Timer shape for live modes:

```text
Clock
  TimeEvent
  Timer
```

Live modes:

```text
Clock.run(Runtime.next)
  while running:
    await sleep_until_timer_due(timer)
    event = timer.event(now_ms)
    await Runtime.next(event)
```

Mainnet/testnet/simnet wait for the configured loop cadence. The Clock does not
wait for new BBO or bar data. `now_ms()` returns wall time.

Backtest:

```text
Clock.run(Runtime.next)
  for batch in FileData.replay_batches():
    Clock.set_time(batch.ts_ms)
    FileData.ingest_replay_batch(batch)
    await Runtime.next()
```

Backtest has no timer. Replay batch timestamps are the trigger.

Core replay rule:

```text
Data engine updates market snapshot.
Clock calls Runtime.next().
Runtime.next() reads snapshot and runs bot logic.
```

| Concept | Mainnet / Testnet / Simnet | Backtest |
| --- | --- | --- |
| Driver | Wall time through asyncio. | Prepared replay data through a plain loop. |
| Wait | `asyncio.sleep(...)` waits for real time. | No wait; consume next replay batch. |
| Data arrival | Websocket messages update market buffers. | Replay loop ingests timestamp batches. |
| Time advance | Clock samples wall time after sleep. | Clock jumps to batch timestamp. |
| Loop trigger | Timer event calls `next(event)`. | Batch ingest completes, then Clock calls `next()`. |
| Snapshot shape | Latest BBO/price plus bars by interval. | Same shape after batch ingest. |

Same-timestamp backtest events collapse into one timestamp batch:

```text
05:00:00  1m replay event
05:00:00  1h completed bar event
```

`next()` sees both only after they are closed and ingested.

## data engines

- Bot-local `WsData` is the live websocket source first.
- `WsData` is the bot-facing live snapshot reader.
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

- Mainnet/testnet bot uses real `ExchangeData` and real `TradingAccount`.
- Simnet/backtest bot can use simulator-backed account/execution objects.
- Simulator internals stay inside the simulator module.

## command server

`CommandServer` lives in `command.py`.

It is runtime-local. Managed and manual modes poll the bot-local `command`
table.
Command rows are bot DB audit/control rows, not a process manager.
It is not aiohttp and it does not own a port.

Runtime startup:

```text
command = CommandServer(nuubot, bot_id, runtime_callbacks)
command.init()
```

`CommandServer.init()` writes:

```text
status = running
runtime_id = runtime identity
run_token = new uuid
started_at = now
last_seen_at = now
```

If bot DB setup or required status write fails, runtime startup fails.

Runtime updates the local `bot` row only with matching ownership:

```text
where run_token = current run token
```

This prevents stale runtime processes from overwriting newer runs.

Optional command audit table:

```text
command
command_id
command
payload_json
status
result_json
created_at
received_at
completed_at
error
```

Bot-local state/event tables:

```text
botstate
event
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

- Bot row `runtime_id`, `run_token`, `status`, and `last_seen_at`.
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
- BotManager checks heartbeat freshness for managed runs.
- Manual runs expose status through bot-local `botstate`, `event`, and
  heartbeat freshness.
