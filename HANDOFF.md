# handoff

Last updated: 2026-06-21

## focus

Runtime design is paused. The unresolved issue is the correct live/paper vs
backtest loop shape.

## current status

- User stopped the session because the runtime discussion was going in circles.
- Do not continue coding until the runtime workflow is clarified.
- Current code has uncommitted runtime/backtest/signal changes.
- Current papertest state is ambiguous:
  - `wmic process where "CommandLine like '%ema-1h-papertest.toml%'"` did not
    show a `uv.exe` or `python.exe` bot process in the latest check.
  - `workspace/logs/runtime.log` still had recent websocket-looking lines.
  - On resume, verify process status before assuming papertest is running.

## key unresolved design question

Clarify the two workflows first, before more patches:

1. Live/paper:
   - Websocket receives market updates continuously.
   - Websocket/data object ingests those updates into buffers.
   - Clock waits on wall time.
   - Runtime loop reads latest buffered state.

2. Backtest:
   - Backtest has an upfront load/build phase.
   - It may build replay events/ticks from historical data.
   - Backtest loop advances replay clock from those prepared events.
   - Need decide whether replay event is a generic tick, a bar, or both.
   - Need decide exactly what method names mean. User specifically said
     "ingest" means a new bar/event arrived, not "select next replay bar".

Main pending decision:

- Keep one `Runtime` with two loop paths, or create separate live/backtest
  runtimes.
- User is not convinced current shape is correct.

## files changed

- `nuubot/core/runtime.py`
- `nuubot/core/dtypes.py`
- `nuubot/core/models/mconfig.py`
- `nuubot/executor/tradebot.py`
- `nuubot/signaler/emacross.py`
- `nuubot/signaler/startnow.py`
- `nuubot/core/telemetry.py`
- `workspace/templates/ema-1h-backtest.toml`
- `workspace/templates/ema-1h-papertest.toml`
- `ema-1h-backtest.cmd`
- `ema-1h-papertest.cmd`
- `wiki/design/runtime-flow-compare.html`

## proof run

- `uv run python -m py_compile ...` passed after changes.
- `uv run python -m nuubot.core.runtime -f workspace/templates/ema-1h-backtest.toml`
  ran and produced results.
- Backtest proof is not final because the design is disputed.

## proof not run

- No final papertest restart/5-minute validation after the latest design stop.
- No commit after the current changes.

## decisions made

- `SignalerConfig.partial` defaults to `False`.
- EMA 9/21 does not use partial bars by default.
- Seed should use closed bars only.
- Seed bars should not trigger trades later.
- Current naming around `BacktestData.ingest()` is probably wrong because it
  currently means selecting the next replay bar.

## next action

Do not patch first. Start by drawing the two workflows as named steps:

| Step | Live/paper | Backtest |
| --- | --- | --- |
| upfront load/build | none beyond config/start websocket | load/build replay events |
| clock driver | wall timer waits | replay event timestamp advances |
| data arrival | websocket ingests continuously | prepared event/tick is consumed |
| runtime evaluation | reads latest buffers | evaluates after replay event/time |

Then decide whether one `Runtime` remains clean enough or whether
`LiveRuntime`/`BacktestRuntime` is justified.
