# handoff

Last updated: 2026-06-23

## focus

Runtime/object design contracts are being shaped before code moves. Design is
now aligned with the planned executable pseudocode stage.

## current status

- Last commit: `f43f128 Make runtime modes first-class`.
- Worktree is dirty with docs-only design consolidation and object-contract
  drafts.
- `progflow.pdf` is untracked and intentionally left alone for now.
- Runtime main flow is approved; do not change the runtime sequence.
- Next design proof should be a runnable executable pseudocode/spec that shows
  top-level object interaction and runtime sequence.

## active agents

None.

## blockers

None known.

## decisions made

- Stop adding deeper design detail once the object shape is good enough.
- Code implementation resumes after the design shape and executable pseudocode
  are reviewed.
- `wiki/design/objects/runtime.md` is the runtime object design; runtime can be
  the largest object file.
- Runtime is the master composer and should not own indicator loading,
  signaler internals, simulator internals, ledger internals, orders, or fills.
- Signaler owns an ensemble of indicators.
- Indicator contract is `init(config)`, `seed(data)`,
  `ingest(data, partial=False)`, `row(at=None, partial=False)`.
- Indicator rows expose `ts` and `data`.
- `row(..., partial=False)` defaults to the latest closed row.
- Live and backtest use the same indicator/signaler code path; backtest passes
  replay time through `at`.
- Signaler owns stale/missing-data policy because market, social, news, and
  economic data have different validity rules.
- Target package shape removes `nuubot/core` later, but code has not been moved.

## files changed

- `HANDOFF.md`
- `.project/plans/runtime-flow-execplan.md`
- `wiki/AGENTS.md`
- `wiki/design/AGENTS.md`
- `wiki/design/overview.md`
- `wiki/design/state.md`
- `wiki/design/strategy.md`
- `wiki/design/sweeps.md`
- `wiki/testing.md`
- `wiki/design/objects/**`
- Deleted stale spread-out design docs:
  - `wiki/architecture.md`
  - `wiki/runtimeflow.md`
  - `wiki/design/runtime.md`
  - `wiki/design/backtest-simulator.md`
  - `wiki/design/frontend.md`
  - `wiki/design/design.html`
  - `wiki/design/process.html`
  - `wiki/design/runtime-flow-compare.html`

## proof run

- Stale deleted-doc reference scan passed:
  `rtk rg -n "design/runtime\\.md|\\[Runtime\\]\\(runtime\\.md\\)|\`runtime\\.md\`|wiki/design/runtime\\.md|backtest-simulator|frontend\\.md|design\\.html|process\\.html|runtimeflow|architecture\\.md" wiki .project AGENTS.md`
- Whitespace check passed:
  `rtk git diff --check`

## proof not run

- No code tests run; this pass is docs-only.
- No executable pseudocode/spec created yet.
- No commit after the current docs changes.

## next action

Create the executable pseudocode/spec for runtime sequence review. Do not move
code or add implementation detail until the object design shape is approved.
