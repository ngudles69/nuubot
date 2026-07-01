# handoff

Last updated: 2026-07-01

## focus

Sweep template/runtime/WebGUI work in `D:\rust\nuubot`.

## current status

- New bot/sweep template layout and grouped sweep expansion are implemented.
- Sweep runs use the real server/API path and ProcessPoolExecutor workers.
- Runtime and sweeprun results include telemetry timing.
- Sweep list shows `Win/Lose`, `Profit Factor`, and `Expected Value`.
- Sweep actions are horizontal and right-justified.
- Sweep archive/unarchive moves DB files between:
  - `workspace/db/sweep_<id>.db`
  - `workspace/db/archived/sweep_<id>.db`
- Bot archive/unarchive uses the same file-move pattern for
  `<network>_bot_<id>.db`.
- Archive/unarchive does not rewrite DB rows or migrate data.

## active server

- Server was restarted normally during proof.
- Last known listener: `127.0.0.1:5001`.
- Recheck the PID before stopping or restarting.

## active agents

None.

## blockers

None known.

## proof run

- `python -m compileall -q nuubot tests`
- `python -m tests.test_archive`
- `python -m tests.test_sweep_metrics`
- `python -m tests.test_sweep_run_guards`
- Live WebGUI proof for `/sweeps` with Playwright screenshot:
  `workspace/results/webgui-sweeps-ev.png`

## next action

Continue sweep result analytics and chart/display work.
