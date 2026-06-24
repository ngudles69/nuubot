# AGENTS.md

Rules for files under `wiki/design/**`.

## Purpose

- `wiki/design/**` holds durable bot runtime design.
- Read `overview.md` first.
- Use the topic files for detail.
- Do not treat `.project/**` or `.research/**` as design truth.

## Files

1. `overview.md`: goals, decisions, object map, non-goals.
2. `objects/AGENTS.md`: object design map.
3. `objects/runtime.md`: master composer, runtime loop, modes, clock/replay,
   command server, telemetry, simulator binding.
4. `state.md`: datastore, exchange meta, positions/orders/fills, events,
   frontend read model.
5. `strategy.md`: risk, signalers, executors.
6. `sweeps.md`: sweep, sweeprun, botrun, parameters.
