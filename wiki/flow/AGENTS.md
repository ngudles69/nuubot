# AGENTS.md

Rules for files under `wiki/flow/**`.

## Purpose

- Flow files show runtime sequence in executable-style pseudocode.
- Keep object internals out unless the flow needs the interaction point.
- Make Clock interaction explicit in every runtime flow.

## Files

1. `clock.md`: wall clock and replay clock flow.
2. `simnet.md`: websocket data, simulator execution, wall Clock.
3. `live.md`: websocket data, real execution, wall Clock.
4. `backtest.md`: file data, simulator execution, replay Clock.
5. `sweep.md`: fast and standard sweep execution shells.
