# handoff

Last updated: 2026-06-30

## focus

`D:\rust\nuubot` Server/WebGUI sweep runtime now uses SQLite plus a
server-owned `ProcessPoolExecutor`. Ray was removed from the active path.

## current status

- Server starts with `./server.sh` / `uv run python -m nuubot.server`.
- Server owns one sweep process pool:
  `ProcessPoolExecutor(max_workers=8, initializer=init_sweep_worker)`.
- Sweep worker processes ignore Ctrl+C; the parent server handles Ctrl+C and
  runs Uvicorn shutdown.
- `SweepManager` submits sweepruns to the server-owned pool.
- `SweepManager` owns finalizer threads and joins them during shutdown.
- SQLite is current datastore direction:
  - `workspace/db/server.db`
  - `workspace/db/sweep_<id>.db`
  - future bot DBs like `workspace/db/simnet_bot_<id>.db`.
- Ray dependency and `wiki/design/ray.md` were removed.
- `wiki/design/processpool.md` is the durable worker-process design page.
- Latest commit pushed:
  `7b3dcb6 Replace Ray sweeps with process pool`.

## active agents

None.

## blockers

- `.venv` may still contain old Ray transitive packages if old Python/Jupyter
  kernels are holding `.pyd` files. `pyproject.toml` and `uv.lock` are clean.
  Stop kernels and run `uv sync` if physical venv pruning is needed.
- Do not execute DB-writing notebooks unless the user explicitly asks.
- If wording is ambiguous and action is destructive, ask first.

## files changed

- `nuubot/sweep.py`
- `nuubot/server/state.py`
- `nuubot/webgui/app.py`
- `pyproject.toml`
- `uv.lock`
- `.project/roadmap.md`
- `wiki/**` process/runtime direction pages.

## proof run

- `uv run python -m compileall -q nuubot`
- `uv lock --check`
- `rg -n "import ray|ray\.|ray\[|pywin32|daemon=True" pyproject.toml nuubot wiki`
  returned no matches.
- Server-owned pool proof script:
  `sweep_id 24 -> complete 4/4`.
- User manually confirmed `./server.sh` startup is much faster and cleaner.

## proof not run

- No full test suite.
- No Playwright screenshot check after the process-pool change.
- No fresh `./server.sh` Ctrl+C proof captured by agent after finalizer
  ownership change; user should retry foreground Ctrl+C after a completed
  sweep.

## decisions made

- Use stdlib `ProcessPoolExecutor` for sweeps instead of Ray.
- Server owns the sweep process pool.
- Worker children ignore Ctrl+C; server parent owns shutdown.
- SQLite remains truth for sweep progress/results.
- No background server / stop script yet.
- Keep WebGUI simple and avoid custom frontend complexity.

## next action

Run `./server.sh`, run a sweep from `/sweeps`, wait for completion, then press
Ctrl+C. Confirm there are no child worker `KeyboardInterrupt` tracebacks.
