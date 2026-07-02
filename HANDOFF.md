# handoff

Last updated: 2026-07-02

## focus

Sweep manager/function-boundary cleanup in `D:\rust\nuubot`.

## current status

- Working tree has uncommitted changes.
- `wiki/coding/rules.md` now documents function naming/splitting rules:
  functionality first, names by caller intent, no one-line indirection, no
  helper per field, no properties unless the user requests them.
- `SweepManager` was hardcut to one inspection surface:
  `metrics(sweep_id, archived=False)`.
- Old sweep inspection manager methods/routes were removed:
  `status()`, `results()`, `telemetry()`, `archived()`, `template()`,
  `archive_dir()`.
- Current sweep manager public operations are:
  `create`, `list`, `list_archives`, `load`, `update`, `clone`, `delete`,
  `metrics`, `run`, `parse_template`, `archive`, `unarchive`.
- WebGUI/API now use `/metrics`.
- `sweep.py` and `sweeprun.py` were cleaned for intent names and fake helper
  removal.
- Partial `ProcessPoolExecutor.submit()` launch failure is now covered by a
  regression test and waits/cancels before marking launch failure.

## active server

- Server is running on `127.0.0.1:5001`.
- Recheck PID before stopping or restarting.

## active agents

None.

## blockers

None known.

## files changed

- `nuubot/server/api.py`
- `nuubot/server/sweepmgr.py`
- `nuubot/sweeps/sweep.py`
- `nuubot/sweeps/sweeprun.py`
- `nuubot/webgui/sweeps/list.py`
- `tests/test_archive.py`
- `tests/test_sweep_metrics.py`
- `tests/test_sweep_results_failure.py`
- `tests/test_sweep_run_guards.py`
- `wiki/coding/rules.md`
- `wiki/design/overview.md`
- `wiki/design/server-api.md`
- `wiki/design/sweepmanager.md`
- `wiki/design/webgui.md`
- `wiki/testing.md`
- `HANDOFF.md`

## proof run

- `python -m compileall -q nuubot tests`
- All `tests/test_*.py` modules passed.
- Server restarted via `./server.sh`; `/status` returned OK after the documented
  delayed readiness check.
- Sweep `26` rerun on final patched server code:
  - `status=complete`
  - `progress=36/36`
  - `failed=0`
  - `win_loss=17/36 (47.2%)`
  - `profit_factor=0.73`
  - `ev=-3.65%`
  - `total_ms=4404`
  - `worker_count=4`
- Old hardcut routes return `404`:
  `/api/sweeps/26/status`, `/api/sweeps/26/results`,
  `/api/sweeps/26/telemetry`.
- `/api/sweeps/26/metrics` returns OK.
- `git diff --check` reports only CRLF warnings.
- Adversarial re-audit returned no findings.

## proof not run

- Playwright/WebGUI screenshot check was not run.

## decisions made

- Use `metrics` as the single sweep inspection/readout surface.
- Do not keep compatibility wrappers for old sweep inspection routes.
- Keep `clone` and `delete` as real manager operations.
- Helpers are allowed only when they reduce real complexity, are reused, or are
  needed for custom non-standard logic.

## next action

Review the uncommitted diff, then commit if acceptable.
