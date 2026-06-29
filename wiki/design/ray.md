---
title: ray design
created: 2026-06-29
updated: 2026-06-29
type: wiki
status: active
tags: [design, ray, runtime, sweeps]
---

# ray design

## purpose

Ray is the worker/process layer owned by Server.

- Bot runtime is plain Python and must run without Ray.
- Managed bots run as thin Ray actor wrappers around BotRuntime.
- Sweeps run as stateless Ray tasks.
- Ray owns worker placement, lifecycle, and parallel fanout.
- SQLite owns persisted state, not Ray object storage.
- Server starts Ray during startup and stops Ray during shutdown.
- Bot websocket/feed clients are bot-local first.

## dependencies

- `ray` is a first-class project dependency.
- Do not add a second process manager.

Server uses:

```python
ray.init(
    num_cpus=8,
    include_dashboard=False,
)
```

Set `RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO=0` before `ray.init()` to suppress
Ray's accelerator warning.

Ray startup can take a few seconds, especially on Windows, because Ray starts a
local runtime: GCS, raylet, object store, workers, temp session/log dirs, and
support processes.

## bot actors

Each bot actor wraps one running bot runtime.

Core rule:

```text
BotRuntime = real bot logic, plain Python
Ray BotActor = thin wrapper around BotRuntime
```

Manual mode:

```text
runtime = BotRuntime(exec_network, bot_id)
runtime.init()
runtime.run()
```

Notebook coding/testing uses manual mode first. This keeps bot code testable
without Ray.

Ray mode:

```text
actor = BotActor.remote(exec_network, bot_id)
actor.run.remote()
```

Live managed runs use Server and Ray.

Hard rule:

```text
1 Ray actor = 1 process = 1 bot runtime = 1 bot SQLite DB
```

## sweep tasks

Each sweep task is stateless from Ray's point of view.

Current first sweep task target:

```text
sweep_id + sweeprun_id + sweep_db_path
open sweep_<sweep_id>.db
update own sweeprun row
load OHLCV data
seed EMA warmup bars
loop bars and log OHLCV/EMA values
write results_json and status
close DB
```

Ray execution is capped at 8 local CPUs for sweep tasks first.

SQLite owns progress:

```text
sweep.status
sweep.results_json
sweeprun.status
sweeprun.results_json
```

For reruns, SweepManager resets run-owned rows inside the sweep DB but keeps
the sweep row. Do not migrate old sweep runtime state.

## non-goals

- No Postgres process.
- No DB compatibility layer.
- No central long-lived DB session manager.
- No custom multiprocessing layer beside Ray.
- No Ray-owned Server process.
- No Redis.
- No shared websocket server first.
