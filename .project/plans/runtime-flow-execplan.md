---
title: runtime flow execplan
created: 2026-06-21
updated: 2026-06-21
type: plan
status: implemented
tags: [runtime, backtest, clock, data-engine]
---

# Runtime Flow ExecPlan

Objective: implement the runtime flow now documented in
`wiki/design/objects/runtime.md` without splitting `Runtime`: live/paper stays
wall-time driven, backtest becomes timestamp-batch data driven, and
`Runtime.loop_once()` stays shared.

Implementation result:

- `Runtime.loop_once()` no longer ingests data.
- `Runtime.loop_backtest()` is the tiny replay orchestrator:
  pull timestamp batch, set replay time, ingest full batch, dispatch due timer.
- `WsDataEngine` owns websocket snapshot updates and valid-BBO readiness.
- `FileDataEngine` owns historical load, derived intervals, replay events, and
  timestamp batches.
- Replay bar events are timestamped at candle close time.
- Runtime tracks new bars per interval.

## Ground Rules

- Do not create `LiveRuntime`, `PaperRuntime`, or `BacktestRuntime`.
- Do not let `Runtime.loop_once()` ingest data.
- Do not let same-timestamp replay events trigger duplicate bot loops.
- Backtest may precompute indicators/signals over the full trusted historical
  dataset for speed, but every precomputed value must be timestamp-indexed and
  decision timestamp `T` can read only values derived from bars closed at or
  before `T`.
- The signaler owns seed allowance. Runtime asks for `signaler.required_bars`;
  it does not add another `+10`.
- Live start waits for two valid BBO samples after websocket subscription, with
  a fail-loud timeout.

## Original Gaps

- `runtime.py` owns data engines, replay loop, file parsing, websocket parsing,
  factories, and bot loop.
- Backtest currently consumes one bar at a time and directly calls
  `loop_once()`.
- Snapshot shape is one `bar` plus optional `bbo`; it cannot represent bars by
  interval.
- Runtime tracks one `last_bar_ms`, not per-interval new-bar state.
- `process_market()` calls a no-op live `data.ingest(...)`, so runtime still
  owns fake ingest timing.
- Durable docs disagree: older runtime docs describe backtest clock jump as
  `min(next scheduled loop time, next historical BBO/bar time)`.
- Current config has one `market.interval`; multi-interval signalers need an
  explicit data source rule before implementation.

## Target Shape

```text
Runtime
  Clock | ReplayClock
  WsDataEngine | FileDataEngine
  Signaler list
  Risk
  Executor
```

Data engines own market snapshot population:

- `WsDataEngine`: websocket messages update latest BBO and bars by interval.
- `FileDataEngine`: historical data loads once, replay events are prepared,
  same-timestamp events are grouped into batches, and each batch updates the
  same snapshot shape.

Clock owns time and dispatch:

- `Clock.run()` waits on wall time with `asyncio.sleep(...)`.
- `ReplayClock` exposes replay-safe `set_time(...)` / `dispatch_due(...)`.
- Clock never ingests data and never owns data-engine callbacks.

Runtime owns shared bot logic:

```text
loop_once(event)
  snapshot = data.snapshot(clock.now_ms())
  apply exit/max-loop checks
  update only signalers with new usable bars for their intervals
  choose signal
  run risk/executor path
```

## Implementation Slices

### 1. Market Snapshot Types

- Add small dataclasses in `nuubot/core/dtypes.py`:
  - `ReplayEvent(ts_ms, priority, seq, kind, payload)`
  - `ReplayBatch(ts_ms, events)`
  - `MarketSnapshot(bbo, bars)`
- Keep `Bar` unchanged.
- Use `bars: dict[str, Bar]` keyed by interval.
- Track new bars in runtime with `last_bar_ms_by_interval`; do not add
  `updated_*` fields unless a real caller needs them.
- Avoid a base class/protocol unless code actually needs it.

### 2. Move Data Engines Out Of Runtime

- Add `nuubot/core/market_data.py`.
- Move file loading/parsing helpers there.
- Move websocket parsing/helpers there.
- Rename current data objects by role:
  - `PaperData` -> `WsDataEngine`
  - `BacktestData` -> `FileDataEngine`
- `WsDataEngine` API:
  - `init()`
  - `start()`
  - `stop()`
  - `history(interval, limit)`
  - `snapshot(now_ms) -> MarketSnapshot`
- `FileDataEngine` API:
  - `init()` loads historical data, seed history, prepared events, batches.
  - `start()` verifies ready; no file load here.
  - `replay_batches()`
  - `ingest_replay_batch(batch)`
  - `history(interval, limit)`
  - `snapshot(now_ms) -> MarketSnapshot`

Multi-interval rule:

- Live subscribes to BBO plus every distinct candle interval required by
  configured signalers.
- Backtest v1 loads the configured base interval from `market.interval` and
  derives larger signaler intervals from that base data.
- Fail fast if a signaler interval cannot be derived exactly from the base
  interval.

### 3. Backtest Replay Batches

- For v1, create replay events from historical bars already available in
  `workspace/data/**`.
- Group events by `ts_ms`.
- Sort same-timestamp events by `(priority, seq)`.
- Use explicit priorities:
  - price/BBO-like replay update before completed bars
  - smaller completed bars before larger completed bars
- If only one bar stream exists, still emit one-event batches so the runtime
  path is the same.
- Runtime loop dispatch is at most once per timestamp batch. If replay time
  jumps over multiple runtime timer intervals, those intervals collapse into
  the one dispatch after the batch is ingested.
- No current/future leakage:
  - `history()` returns only bars before replay start for seeding.
  - batch `T` exposes only events in that batch and earlier.
  - derived higher-interval bars are emitted only when their close timestamp is
    reached.

### 4. Clock Changes

- Keep `Clock.run()` and `Clock.tick()` for live/paper.
- Add replay-safe methods to `ReplayClock`:
  - `set_time(now_ms)`
  - `dispatch_due(now_ms)`
- `dispatch_due(now_ms)` dispatches each due timer at most once for the current
  timestamp batch after the data engine has ingested the full batch.
- Preserve monotonic time checks.
- Do not use `asyncio.sleep(...)` in replay.

### 5. Runtime Cleanup

- `Runtime.__init__()` wires objects only.
- `Runtime.init()` calls `data.init()`, initializes risk/executor/signaler
  objects, and seeds signalers from `data.history(...)`.
- `Runtime.start()` sets `running`, registers runtime timer, starts data, risk,
  and executor.
- `Runtime.loop()`:
  - live/paper: `await clock.run()`
  - backtest: `await self.loop_backtest()`
- Keep `Runtime.loop_backtest()` as the tiny replay orchestrator:
  - pull `batch = next(replay_batches)`
  - `replay_clock.set_time(batch.ts_ms)`
  - `await data.ingest_replay_batch(batch)`
  - `await replay_clock.dispatch_due(batch.ts_ms)`
- Delete `process_market()` ingest behavior. Runtime only snapshots.
- Replace `last_bar_ms` with `last_bar_ms_by_interval`.
- `process_signalers(snapshot)` selects each signaler's configured interval and
  only updates on a new usable bar.

### 6. Backtest Indicator Fast Path

- Keep canonical signaler behavior available through `loop_once(bar)` for live.
- Backtest may use timestamp-indexed precomputed indicator/signal arrays.
- Contract: at decision timestamp `T`, a signaler can only return a value whose
  source bars are closed at or before `T`.
- `SignalerEmaCross.ingest_many(bars)` remains valid for sweeps if its output
  is indexed by the source bar timestamp.
- Add proof that precomputed values at `T` do not see `T+1`.

### 7. Live Stable BBO Gate

- In `WsDataEngine.start()` or a dedicated readiness call after subscription,
  wait until two valid BBO samples are observed.
- Keep the first implementation simple:
  - require two BBO messages with valid bid/ask shape
  - require `bid < ask`
  - require nonzero positive prices
  - require a timeout that raises if readiness is not reached
- Call this a valid-BBO readiness gate, not a full spike detector. Do not add
  configurable spike thresholds yet unless actual data proves the simple gate
  is insufficient.

### 8. Docs

- Runtime flow, mode binding, replay behavior, and simulator binding are now
  consolidated in `wiki/design/objects/runtime.md`.

## Proof Completed

- Compile:
  `rtk uv run python -m py_compile nuubot/core/config.py nuubot/core/models/mconfig.py nuubot/core/clock.py nuubot/core/market_data.py nuubot/core/runtime.py nuubot/core/sweep.py nuubot/core/risk.py nuubot/executor/tradebot.py nuubot/signaler/emacross.py nuubot/signaler/startnow.py`
- Runtime flow check:
  `rtk uv run python -m tests.test_runtime_flow`
- Backtest smoke:
  `rtk uv run python -m nuubot.core.runtime -f workspace/templates/smoke-backtest.toml`
- Papertest smoke:
  `rtk uv run python -m nuubot.core.runtime -f workspace/templates/smoke-papertest.toml`

## Proof Still Worth Adding

- Negative timeout check for live valid-BBO readiness.
- Explicit precomputed-indicator no-future-leak check if a backtest fast path is
  added.
- Multi-interval end-to-end smoke config, for example 1m base data plus 5m or
  1h signaler interval.

## Open Risks

- Multiple signalers with different intervals require deterministic signal
  selection if more than one fires at the same timestamp.
- Current sweeps import `load_binance_bars` from `runtime.py`; moving data
  helpers must update sweep imports.
- Deriving higher intervals from base data must fail loud when intervals do not
  divide exactly.

## Stop Point

Implementation is done only when:

- live/paper remains wall-time driven;
- backtest is timestamp-batch data driven;
- `Runtime.loop_once()` has no data ingest;
- same-timestamp replay events dispatch one bot loop;
- docs and smoke tests agree with the new behavior.
