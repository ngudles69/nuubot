---
title: simnet runtime flow
created: 2026-06-26
updated: 2026-06-29
type: wiki
status: active
tags: [flow, runtime, simnet]
---

# simnet runtime flow

## binding

```text
simnet = WsData + simulator execution + wall Clock
```

WsData uses live websocket market data.

Executor sends order intent through Account.

Account uses Simulator for execution.

## setup

```text
Notebook/manual coding path may instantiate BotRuntime directly.
Managed simnet path uses Server/BotManager and Ray.
bot_id = server DB sequence for simnet_bot
bot_db = workspace/db/simnet_bot_<bot_id>.db
start BotRuntime directly or through Ray actor with exec_network, bot_id
bot = bot_setup(exec_network=simnet, bot_id=bot_id)

data = WsData(bot.config)
clock = Clock(mode=simnet, data=data, loop_seconds=loop_seconds)
account = Account(nuubot, account_id, exec_network=simulator)
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
  sleep until runtime timer is due
  dispatch Runtime.next(event)
```

Wall Clock does not wait for new market data. WsData updates BBO/candle buffers
from websocket messages. Runtime reads the latest snapshot when the timer
fires.

## next

```text
now = Clock.now_ms()

command = CommandServer.next_command()

if command is kill:
  exit("kill")
  end_loop()
  return

market = WsData.snapshot(now)

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

Direct notebook/manual mode owns the BotRuntime process. Managed simnet mode
uses Ray for actor lifecycle. BotRuntime owns `bot_db`.

## stop semantics

- `kill`: exits runtime. Does not cancel orders or close positions. Bot remains
  restartable.
- `stop`: graceful terminal close. Executor closes the bot, then marks terminal
  stopped. Terminal stopped/error cannot be restarted.
- Fresh start and restart both reconcile first. Fresh start should reconcile to
  flat/no-op.
