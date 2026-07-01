# handoff

Last updated: 2026-07-02

## focus

Server startup handling in `D:\rust\nuubot`.

## current status

- Last known committed baseline before this handoff: `41160e3 Implement sweep templates and archive controls`.
- `server.sh` now starts `uv run python -m nuubot.server` in the background,
  redirects server stdout/stderr to `workspace/logs/server-start.*.log`, and
  polls `/status` before reporting readiness.
- `AGENTS.md` now records the manual server-start rule for agents:
  run `./server.sh`, wait 2 seconds, test `/status`, then retry every 1 second
  up to 10 seconds before diagnosing startup failure.
- The agent command backend is PowerShell. Invoking Git Bash from the backend is
  a non-interactive subprocess, not the user's live Git Bash terminal.
- Scratch scripts used during diagnosis were removed.

## active server

- Last known listener: `127.0.0.1:5001`, PID `22548`.
- Recheck the PID before stopping or restarting.

## active agents

None.

## blockers

None known.

## files changed

- `AGENTS.md`
- `HANDOFF.md`
- `server.sh`

## proof run

- `./server.sh` was used to start the server.
- After waiting, `/status` returned:
  `{"status":"ok","response":{"type":"server_status","data":{"status":"running"}}}`.
- Port check showed `127.0.0.1:5001` listening with PID `22548`.

## proof not run

- Full test suite was not rerun for this startup/docs-only follow-up.
- Live interactive Git Bash output cannot be observed from the agent's
  PowerShell-backed command tool.

## decisions made

- Keep `server.sh` as the operator entry point for starting the server.
- Agents must not immediately spam `/status` after starting the server.
- If startup is not detected within 10 seconds, inspect logs and process state.

## next action

Continue from the server startup commit.
