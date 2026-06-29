---
title: sweepmanager design
created: 2026-06-29
updated: 2026-06-29
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

- sweep create/load/view/status.
- sweeprun task submission through Ray.
- sweep artifact DB creation.
- sweep DB file discovery.
- result collection and summary reads.

## does not own

- bot lifecycle commands.
- Bot Runtime loop.
- bot-local live feed internals.
- API route parsing beyond receiving validated inputs.
- CLI parsing or printing.

## interfaces

External functions:

- `create_sweep_via_file(path)`
- `create_sweep_via_template(template)`
- `run_sweep(sweep_id)`
- `stop_sweep(sweep_id)`
- `load_sweep(sweep_id)`
- `list_sweeps()`
- `view_sweep(sweep_id)`
- `status_sweep(sweep_id)`
- `list_sweepruns(sweep_id)`

## contracts

| Function | Input | Output | Contract |
| --- | --- | --- | --- |
| `create_sweep_via_file(path)` | Sweep template path. | Sweep id and DB path. | Loads file, then calls `create_sweep_via_template(template)`. |
| `create_sweep_via_template(template)` | Loaded sweep template. | Sweep id and DB path. | Validates through sweep/template code, allocates sequence, creates sweep DB, and writes sweep rows. |
| `run_sweep(sweep_id)` | Sweep id. | Ray task refs/status. | Submits stateless Ray tasks for generated sweepruns. |
| `stop_sweep(sweep_id)` | Running sweep id. | Stop accepted/result. | Stops/cancels outstanding sweep work where supported. |
| `load_sweep(sweep_id)` | Sweep id. | Sweep row plus DB path. | Reads the sweep DB. |
| `list_sweeps()` | None. | Sweep DB paths/rows. | Discovers `workspace/db/sweep_*.db`. |
| `view_sweep(sweep_id)` | Sweep id. | Operator view. | Reads sweep DB result data. |
| `status_sweep(sweep_id)` | Sweep id. | Sweep status. | Combines DB file existence and Ray task status where available. |
| `list_sweepruns(sweep_id)` | Sweep id. | Sweeprun rows. | Reads the sweep DB or sweeprun DB files. |

## notes

- Sweeps are separate from BotManager because sweep fanout and result handling
  are different from bot lifecycle.
- Backtest starts under BotManager unless it diverges enough to justify a
  BacktestManager later.
- First sweep target is a basic EMA-cross sweep used as the future sweep
  template.
- Sweep existence is the sweep DB file.
- Do not add central sweep/sweeprun catalog tables unless file discovery is
  measured and proven insufficient.
