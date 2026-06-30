---
title: process pool design
created: 2026-06-30
updated: 2026-06-30
type: wiki
status: active
tags: [design, processpool, sweeps]
---

# process pool design

## purpose

`ProcessPoolExecutor` is the current sweep worker layer.

- Sweeps run as stateless process-pool tasks.
- SQLite owns persisted state and progress.
- Server does not start a separate worker service during startup.
- Each sweep owns its own process pool.
- Workers are not global; the user chooses worker count per sweep.
- SweepManager owns result threads and joins them during server shutdown.
- Sweep result threads close their sweep-local process pool.
- Sweep worker processes ignore Ctrl+C; the server process handles Ctrl+C and
  waits for result threads during shutdown.
- BotRuntime remains plain Python and must run without a process manager.

## dependencies

Use the Python standard library:

```python
from concurrent.futures import ProcessPoolExecutor
```

Do not add Ray, Redis, Celery, or another process manager until measured need.

## sweep tasks

Each sweep task receives:

```text
sweep_id
sweeprun_id
sweep_db_path
```

Each task:

```text
open sweep DB
set own sweeprun row running
load own botrun config
load historical OHLCV bars
seed EMA warmup bars
loop active OHLCV bars
write per-sweeprun log
write own sweeprun results/status
close sweep DB
```

Sweep execution defaults to 4 local worker processes and is capped at 8.

SQLite owns progress:

```text
sweep.status
sweep.results_json
sweeprun.status
sweeprun.results_json
```

## non-goals

- No Postgres process.
- No DB compatibility layer.
- No central long-lived DB session manager.
- No Ray.
- No Redis.
- No shared websocket server first.
