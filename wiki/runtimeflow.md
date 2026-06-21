---
title: runtime flow
created: 2026-06-21
updated: 2026-06-21
type: wiki
status: draft
tags: [runtime, clock, backtest, live, paper]
---

# Runtime Flow

Objective: compare live/paper vs backtest row by row before changing code.

Core rule:

```text
Data engine updates market snapshot.
Clock dispatches Runtime.loop_once().
Runtime.loop_once() reads snapshot and runs bot logic.
```

## Concept Compare

| Concept | Live / Paper | Backtest |
| --- | --- | --- |
| Who drives whom | `Runtime.loop()` starts `Clock.run()`; wall time wakes `Clock`; `Clock` dispatches `loop_once()`. | `Runtime.loop()` starts replay loop; replay loop pulls data batch; batch advances `ReplayClock`; `ReplayClock` dispatches `loop_once()`. |
| Driver source | Wall time through asyncio event loop. | Prepared replay data through a plain loop. |
| Wait behavior | `asyncio.sleep(...)` waits for real time. | No wait; consume next replay batch. |
| Data arrival | Websocket messages arrive independently of the bot loop. | Replay loop pulls timestamp batches. |
| Data effect | Updates market buffers only. | Updates market buffers and advances replay time. |
| Time advance | Clock samples wall time after sleep. | Replay clock jumps to batch timestamp. |
| Same timestamp | Many messages can collapse into latest snapshot before one timer loop. | Many replay events collapse into one timestamp batch. |
| Loop trigger | Due clock timer dispatches `loop_once()`. | Batch ingest completes, then due replay timer dispatches `loop_once()`. |
| Signaler fire | On new usable bar in snapshot. | On new usable bar in fully ingested batch snapshot. |

## Code Execution Compare

| Step | Live / Paper | Backtest |
| --- | --- | --- |
| 1. Build runtime | Create config, `Clock`, `WsDataEngine`, signalers, risk, executor. | Create config, `ReplayClock`, `FileDataEngine`, signalers, risk, executor. |
| 2. Data init | Validate config/history access. Wait for two stable BBO samples to avoid starting on a spike. | Load trusted historical data. Prepare replay events and timestamp batches. No stable-BBO gate. |
| 3. Signaler init/seed | Load required bars plus 10 extra rows. Calculate initial indicator state, for example EMA. | Load run data. Calculate/prep indicator state or replay signals, for example EMA. |
| 4. Start, pre-main-loop | Start websocket, subscribe to streams, register runtime timer. | Verify replay batches ready, set replay start time, register runtime timer. |
| 5. Enter main loop | `Runtime.loop()` calls `Clock.run()`. | `Runtime.loop()` calls replay loop. |
| 6. Main loop | See steps `6a` to `6f`. | See steps `6a` to `6f`. |
| 6a. Pull work | No data batch is pulled. Live waits for next due timer. | `time_batch = next(replay_batches)`. |
| 6b. Wait | `await asyncio.sleep(...)` until timer is due. | No wait. The plain loop continues if a batch exists. |
| 6c. Advance time | Sample wall time and advance `Clock`. | Set `ReplayClock` to `time_batch.ts_ms`. |
| 6d. Update snapshot | No loop-owned update. Websocket task already updated buffers as messages arrived. | Ingest every event in `time_batch` into snapshot. |
| 6e. Same-time handling | Latest buffers win before timer fires. | All same-timestamp events are ingested before one loop dispatch. |
| 6f. Trigger bot loop | Clock dispatches due runtime timer. | Replay clock dispatches due runtime timer after batch ingest. |
| 7. `loop_once()` | Read snapshot. Process exit/risk/signaler/executor. | Same, but snapshot is fully replay-batch updated. |

## Same Timestamp Example

```text
05:00:00  1m replay event
05:00:00  1h completed bar event
```

Backtest treats this as:

```text
one timestamp batch
one replay clock advance to 05:00:00
one full snapshot update
one Runtime.loop_once() dispatch
```

Not:

```text
two clock advances
two Runtime.loop_once() calls
```
