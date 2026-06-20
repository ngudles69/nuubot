# AGENTS.md

Rules for files under `wiki/design/**`.

## Purpose

- `wiki/design/**` holds durable bot runtime design.
- Read `overview.md` first.
- Use the topic files for detail.
- Do not treat `.project/**` or `.research/**` as design truth.

## Files

1. `overview.md`: design overview, goals, decisions, first-class objects.
2. `runtime.md`: standard bot loop, clock, command server, telemetry.
3. `state.md`: datastore, botrun state, exchange meta, reconciliation.
4. `strategy.md`: risk, signalers, executors.
5. `backtest-simulator.md`: live/paper/backtest and simulator.
6. `frontend.md`: datastore viewer and command boundary.
7. `sweeps.md`: sweep, sweeprun, botrun, parameters.
8. `design.html`: database ER diagram.
9. `process.html`: high-level component and contract map.
