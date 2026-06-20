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
  - `architecture.md`: architecture notes.
  - `repomap.md`: repo map.
2. Design:
  - `design/AGENTS.md`: design map.
  - `design/overview.md`: goals, decisions, first-class objects, non-goals.
  - `design/runtime.md`: standard bot loop, clock, command server, telemetry.
  - `design/state.md`: datastore, botrun state, exchange meta, reconciliation.
  - `design/strategy.md`: risk, signalers, executors.
  - `design/backtest-simulator.md`: live/paper/backtest and simulator.
  - `design/frontend.md`: datastore viewer and command boundary.
  - `design/sweeps.md`: sweep, sweeprun, botrun, parameters.
  - `design/design.html`: database ER diagram.
  - `design/process.html`: high-level component and contract map.
3. Coding:
  - `coding/rules.md`: coding rules.
  - `coding/samples/scaffold.md`: new-file scaffold samples.
  - `coding/samples/objects.md`: composing and primitive object samples.
  - `coding/samples/bots.md`: bot samples.
  - `coding/samples/sweeps.md`: sweep samples.
  - `coding/samples/helpers.md`: helper samples.
