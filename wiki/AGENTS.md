# AGENTS.md

Rules for files under `wiki/**`.

## Purpose

- `wiki/**` is the living sum of durable project knowledge.
- Keep durable facts and decisions here:
  - coding
  - architecture
  - stack
  - project
  - vision
  - repo map
  - guidance.
- `.project/**` and `.research/**` can be out of date. Do not treat them as
  facts.
- This file is the wiki map. Lead from here.
- Do not overlook nested wiki files. Read the relevant listed file before
  changing that area.

## Files

1. Core:
  - `project.md`: vision, objective, and guidance.
  - `logging.md`: logging format and cascading error path.
  - `notebooks.md`: notebook workflow, extraction markers, charting rules.
  - `testing.md`: compile check and smoke test commands.
  - `repomap.md`: repo map.
2. Design:
  - `design/AGENTS.md`: design map.
  - `design/overview.md`: goals, decisions, object map, non-goals.
  - `design/objects/AGENTS.md`: object design map.
  - `design/objects/nuubot.md`: shared infra owner.
  - `design/objects/runtime.md`: master composer, runtime loop, modes,
    clock/replay, command server, telemetry, simulator binding.
  - `design/state.md`: datastore, exchange meta, positions/orders/fills,
    events, frontend read model.
  - `design/strategy.md`: risk, signalers, executors.
  - `design/sweeps.md`: sweep, sweeprun, botrun, parameters.
3. Flow:
  - `flow/AGENTS.md`: flow map.
  - `flow/clock.md`: wall clock and replay clock flow.
  - `flow/simnet.md`: simnet runtime flow.
  - `flow/live.md`: live runtime flow.
  - `flow/backtest.md`: backtest runtime flow.
  - `flow/sweep.md`: sweep flow.
4. Coding:
  - `coding/rules.md`: coding rules.
  - `coding/samples/scaffold.md`: new-file scaffold samples.
  - `coding/samples/objects.md`: composing and primitive object samples.
  - `coding/samples/bots.md`: bot samples.
  - `coding/samples/sweeps.md`: sweep samples.
  - `coding/samples/helpers.md`: helper samples.
