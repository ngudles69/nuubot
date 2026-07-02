---
title: sweepmanager design
created: 2026-06-29
updated: 2026-07-02
type: wiki
status: active
tags: [design, server, sweepmanager, sweeps]
---

# sweepmanager design

## purpose

SweepManager owns sweep control-plane operations.

Server owns SweepManager. API routes and CLI helpers call SweepManager; they do
not implement sweep behavior themselves.

## owns

- sweep create/load/list/metrics.
- sweeprun task submission through `ProcessPoolExecutor`.
- sweep artifact DB creation.
- sweep DB file discovery.
- sweep archive/unarchive by DB file move.
- result collection and summary reads.

## does not own

- bot lifecycle commands.
- Bot Runtime loop.
- bot-local live feed internals.
- API route parsing beyond receiving validated inputs.
- CLI parsing or printing.

## interfaces

External functions:

- `create(template)`
- `update(sweep_id, template)`
- `run(sweep_id)`
- `load(sweep_id)`
- `list()`
- `list_archives()`
- `metrics(sweep_id, archived=False)`
- `clone(sweep_id)`
- `delete(sweep_id)`
- `archive(sweep_id)`
- `unarchive(sweep_id)`

## contracts

| Function | Input | Output | Contract |
| --- | --- | --- | --- |
| `create(template)` | TOML/JSON text or parsed template. | Sweep id. | Validates through sweep/template code, allocates sequence, creates sweep DB, and writes the sweep row. |
| `update(sweep_id, template)` | Sweep id and TOML/JSON text or parsed template. | None. | Refuses active sweeps, resets run-owned rows, and replaces config on the existing sweep DB. |
| `run(sweep_id)` | Sweep id. | DB-backed status. | Validates the sweep DB/config/workers, resets previous run rows, creates sweeprun rows, marks the sweep running, and submits stateless process-pool tasks. |
| `load(sweep_id)` | Sweep id. | Sweep config. | Reads and validates the sweep config from the sweep DB. |
| `list()` | None. | Sweep DB paths/rows/status. | Discovers `workspace/db/sweep_*.db`. |
| `list_archives()` | None. | Archived sweep DB paths/rows/status. | Discovers `workspace/db/archived/sweep_*.db` and reports status as `archived`. |
| `metrics(sweep_id, archived=False)` | Sweep id and archive flag. | SQLite-backed sweep status, results, telemetry, and performance metrics. | Reads one sweep DB and returns the inspection payload. |
| `clone(sweep_id)` | Sweep id. | New sweep id. | Loads the source config and creates a new sweep with it. |
| `delete(sweep_id)` | Inactive sweep id. | None. | Refuses active sweeps and drops the sweep DB. |
| `archive(sweep_id)` | Inactive sweep id. | None. | Moves `workspace/db/sweep_<id>.db` to `workspace/db/archived/sweep_<id>.db`. Does not rewrite data. |
| `unarchive(sweep_id)` | Archived sweep id. | None. | Moves `workspace/db/archived/sweep_<id>.db` back to `workspace/db/sweep_<id>.db`. |

## notes

- Sweeps are separate from BotManager because sweep fanout and result handling
  are different from bot lifecycle.
- Backtest starts under BotManager unless it diverges enough to justify a
  BacktestManager later.
- First sweep target is a basic EMA-cross sweep used as the future sweep
  template.
- First run target is data/indicator proof only: load historical bars, seed
  EMA warmup bars, loop OHLCV, log bar/indicator values, and stop cleanly.
- No executor, risk, entries, exits, orders, or fills in the first run target.
- Sweep existence is the sweep DB file.
- Archived sweeps live under `workspace/db/archived/` so normal sweep listing
  does not scan or display them.
- Do not add central sweep/sweeprun catalog tables unless file discovery is
  measured and proven insufficient.
- Process pool is execution. SQLite is truth.

Run flow:

```text
run(sweep_id)
  open workspace/db/sweep_<sweep_id>.db
  load and validate sweep.config_json
  validate sweep.workers
  delete run-owned rows except sweep
  reset sweep.results_json
  create sweeprun rows
  set sweep.status = running
  create a sweep-local process pool
  submit sweeprun tasks to that pool
  write sweep results when all sweepruns finish
  join result threads during server shutdown
```

Each sweeprun task receives:

```text
sweep_id
sweeprun_id
sweep_db_path
```

Each sweeprun task:

```text
open sweep DB
set own sweeprun row running
load own sweeprun config
load historical OHLCV bars
seed EMA warmup bars
loop active OHLCV bars
create botrun rows only when a signal/executor/risk decision starts a bot
write per-sweeprun log
write own sweeprun results/status
close sweep DB
```

Per-sweeprun logs live in:

```text
workspace/logs/sweep_<sweep_id>_sweeprun_<sweeprun_id>.log
```

The filename must include both `sweep_id` and `sweeprun_id` so there is no
ambiguity about which sweep DB and row produced the log.

Progress:

```text
done = count(sweeprun.status in ["complete", "failed"])
total = count(sweeprun)
```
