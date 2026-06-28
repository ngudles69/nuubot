---
title: clock flow
created: 2026-06-26
updated: 2026-06-26
type: wiki
status: active
tags: [flow, clock, runtime]
---

# clock flow

## purpose

Clock owns loop triggering.

Runtime owns what each loop does.

Runtime exposes one step:

```text
Runtime.next(event optional)
```

Live clocks call it with timer events.

Replay clocks call it without timer events after replay data has been ingested.

## wall clock

Used by:

- `mainnet`
- `testnet`
- `simnet`

Flow:

```text
clock = Clock(mode, data, loop_seconds)

Clock.init()
  timer = Timer("runtime", loop_seconds)

Runtime.loop()
  await clock.run(Runtime.next)

Clock.run()
  while running:
    await sleep_until_timer_due(timer)
    now = wall time
    event = timer.event(now)
    await Runtime.next(event)

Runtime.next(event optional)
  now = Clock.now_ms()
  run runtime loop sequence
```

Rules:

- Wall Clock does not wait for new market data.
- Websocket data updates buffers separately.
- Runtime loop reads the latest data snapshot when the timer fires.
- Live timer events matter because mainnet/testnet/simnet are wall-time
  programs.
- The live timer is created by Clock init.

## replay clock

Used by:

- `backtest`

Flow:

```text
clock = Clock(mode, data, loop_seconds)

Clock.init()
  timer = None

Runtime.loop()
  await clock.run(Runtime.next)

Clock.run()
  for batch in FileData.replay_batches():
    Clock.set_time(batch.ts_ms)
    FileData.ingest_replay_batch(batch)
    await Runtime.next()

Runtime.next()
  now = Clock.now_ms()
  run runtime loop sequence
```

Rules:

- Replay Clock does not sleep.
- Replay Clock does not pull market data.
- FileData updates the snapshot before Clock dispatches Runtime.
- Same-timestamp replay events are ingested before Runtime sees the snapshot.
- Backtest has no timer. Replay batch timestamps are the trigger.
