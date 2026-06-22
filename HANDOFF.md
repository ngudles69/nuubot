# handoff

Last updated: 2026-06-22

## focus

Runtime flow, mode vocabulary, and bot log naming are implemented but not
committed.

## current status

- Last commit: `33340fa Simplify runtime replay data flow`.
- Worktree is dirty with mode/logging/docs/template changes after that commit.
- Runtime still stays one shared `Runtime`.
- Bot runtime modes are now first-class through `runtime.mode`.
- `data_network` and `exec_network` are derived properties, not authored config
  fields.
- Sweep is not a bot runtime mode and does not use `bot_<mode>_<bot_id>.log`.

## active agents

None.

## blockers

None known.

## decisions made

- `Mode` enum lives in `nuubot/core/dtypes.py`.
- `DataNetwork` enum lives in `nuubot/core/dtypes.py`.
- `ExecNetwork` enum lives in `nuubot/core/dtypes.py`.
- `MODE_NETWORKS` maps:
  - `mainnet -> wsdata + mainnet`
  - `testnet -> wsdata + testnet`
  - `simnet -> wsdata + simulator`
  - `backtest -> filedata + simulator`
- Authored botrun config uses only `runtime.mode`.
- `wsdata = WsDataEngine`.
- `filedata = FileDataEngine`.
- First four bot modes log to `workspace/logs/bot_<mode>_<bot_id>.log`.
- Sweep has its own later log format.
- Current old template filenames still contain `papertest`, but their config
  mode is now `simnet`.

## files changed

- `nuubot/core/dtypes.py`
- `nuubot/core/logger.py`
- `nuubot/core/market_data.py`
- `nuubot/core/models/mconfig.py`
- `nuubot/core/runtime.py`
- `nuubot/core/sweep.py`
- `nuubot/executor/tradebot.py`
- `tests/test_runtime_flow.py`
- `wiki/**` runtime/mode/logging docs
- `workspace/templates/*backtest.toml`
- `workspace/templates/*papertest.toml`

## proof run

- Compile passed:
  `rtk uv run python -m py_compile nuubot/core/dtypes.py nuubot/core/logger.py nuubot/core/config.py nuubot/core/models/mconfig.py nuubot/core/clock.py nuubot/core/market_data.py nuubot/core/runtime.py nuubot/core/sweep.py nuubot/core/risk.py nuubot/executor/tradebot.py nuubot/signaler/emacross.py nuubot/signaler/startnow.py`
- Minimal runtime check passed:
  `rtk uv run python -m tests.test_runtime_flow`
- Backtest smoke passed:
  `rtk uv run python -m nuubot.core.runtime -f workspace/templates/smoke-backtest.toml`
- Simnet smoke passed:
  `rtk uv run python -m nuubot.core.runtime -f workspace/templates/smoke-papertest.toml`
- Latest logs verified:
  - `workspace/logs/bot_backtest_11.log`
  - `workspace/logs/bot_simnet_12.log`

## proof not run

- No sweep smoke after the `runtime.mode` cutover.
- No commit after the current dirty changes.

## next action

Review the dirty diff, run a sweep smoke if desired, then commit. Optional
cleanup after commit: rename `*papertest.toml` templates to `*simnet.toml`.
