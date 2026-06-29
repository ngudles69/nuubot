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
4. `state.md`: SQLite datastore, exchange meta, positions/orders/fills,
   events, frontend read model.
5. `server.md`: Server ownership and process shape.
6. `server-db.md`: Server DB ownership and access rules.
7. `botmanager.md`: BotManager ownership and interfaces.
8. `sweepmanager.md`: SweepManager ownership and interfaces.
9. `server-api.md`: API route rules and route-list reference.
10. `webgui.md`: FastHTML WebGUI ownership and layout.
11. `dataengines.md`: optional shared websocket/feed engines.
12. `processpool.md`: ProcessPoolExecutor sweep worker model.
13. `strategy.md`: risk, signalers, executors.
14. `sweeps.md`: sweep, sweeprun, bot config, parameters.
