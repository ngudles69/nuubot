---
title: backtest runtime flow
created: 2026-06-26
updated: 2026-06-29
type: wiki
status: active
tags: [flow, runtime, backtest]
---

# backtest runtime flow

## binding

```text
backtest = FileData + simulator execution + Clock(timer=None)
```

FileData loads historical bars from disk.

Executor sends order intent through Account.

Account uses Simulator for execution.

Clock advances to historical event timestamps. It does not sleep and does not
create timer events.

## setup

```text
Notebook/manual coding path may instantiate BotRuntime directly.
Managed backtest path uses Server/BotManager when lifecycle code exists.
bot_id = server DB seq for backtest_bot
bot_db = workspace/db/backtest_bot_<bot_id>.db
start BotRuntime directly with exec_network, bot_id
bot = bot_setup(exec_network=simnet, bot_id=bot_id)

data = FileData(bot.config)
clock = Clock(mode=backtest, data=data, loop_seconds=loop_seconds)
account = Account(nuubot, acct_id, exec_network=simulator)
executor = Executor(nuubot, bot_id, account)
signaler = Signaler(bot.config)
command = CommandServer(nuubot, bot_id, callbacks)
```

## init

```text
command.init()
data.init()
account.init()
signaler.init()
executor.init()
```

FileData init:

```text
bars = load historical data
derived_bars = derive required intervals
events = build replay events
batches = group events by timestamp
```

## start

```text
command.start()
data.start()
account.start()
signaler.start(data)
executor.start()

clock.init()
```

## clock trigger

```text
Runtime.loop()
  await clock.run(Runtime.next)

Clock.run()
  for batch in FileData.replay_batches():
    Clock.set_time(batch.ts_ms)
    FileData.ingest_replay_batch(batch)
    await Runtime.next()
```

Backtest Clock does not pull data. FileData updates the snapshot first, then
Clock calls Runtime. Same-timestamp replay events are visible together to
`Runtime.next()`.

## next

```text
now = Clock.now_ms()

command = CommandServer.next_command()

if command is kill:
  exit("kill")
  end_loop()
  return

market = FileData.snapshot(now)

# Must happen before every non-kill operation.
executor_state = Executor.reconcile(market)

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

  if Risk.exit() or Signaler.exit() or Executor.exit():
    Executor.request_terminal_stop()

  if Executor.is_closing():
    Executor.handle_order_exits(market)
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
    Executor.enter(decision)
  end_loop()
  return

risk_state = Risk.score()
Executor.handle_order_exits(market)

if Executor.can_submit_orders():
  Executor.submit_orders(market, signaler_state, risk_state)

end_loop:
  CommandServer.heartbeat()
  owning objects write SQLite status/events
  log telemetry
```

Direct notebook/manual mode owns the BotRuntime process. Sweep-generated
backtests run as process-pool tasks in the sweep flow.

## stop semantics

- `kill`: exits runtime. Does not cancel orders or close positions. Bot remains
  restartable.
- `stop`: graceful terminal close. Executor closes the bot, then marks terminal
  stopped. Terminal stopped/error cannot be restarted.
- Fresh start and restart both reconcile first. Fresh start should reconcile to
  flat/no-op.
