# handoff

Last updated: 2026-06-28

## focus

Datastore/config cleanup for `D:\rust\nuubot`, with `ghbot.ipynb` aligned to
the current sweep schema.

## current status

- `nuubot/datastore/schemas.py` owns SQLAlchemy table schemas.
- `nuubot/datastore/models.py` is reserved for Pydantic models.
- `nuubot/datastore/datastore.py` creates configured Postgres DBs and tables
  explicitly, one database/table set at a time.
- `nuubot/config/config.py` is simplified:
  `load_config(path)` -> `read_config_data(path)` -> `create_config(data)`.
- `nuubot.config.data_network` and `nuubot.config.exec_network` are set from
  `nuubot.config.general.mode` in `set_networks(config)`.
- `RuntimeConfig` no longer sets network fields.
- `notebooks/ghbot.ipynb`, `notebooks/emacross.ipynb`, and
  `notebooks/emacross_ghbot.ipynb` were updated to current `SweepRow` /
  `SweeprunRow` fields.
- Current Postgres non-template DBs:
  `nuubot_backtest`, `nuubot_mainnet`, `nuubot_server`, `nuubot_simnet`,
  `nuubot_sweeps`, `nuubot_testnet`, `postgres`.
- User installed DBeaver and can see the `nuubot_*` databases.

## active agents

None.

## blockers

- Do not run DB-writing notebooks or destructive DB commands without explicit
  approval.
- If wording is ambiguous and action is destructive, ask first.

## files changed

- `nuubot/config/config.py`
- `nuubot/config/__init__.py`
- `nuubot/config/models.py`
- `nuubot/core/dtypes.py`
- `nuubot/core/models/mconfig.py`
- `nuubot/core/sweep.py`
- `nuubot/datastore/datastore.py`
- `nuubot/datastore/models.py`
- `nuubot/datastore/schemas.py`
- `nuubot/datastore/__init__.py`
- `nuubot/nuubot.py`
- `notebooks/ghbot.ipynb`
- `notebooks/emacross.ipynb`
- `notebooks/emacross_ghbot.ipynb`
- `wiki/coding/rules.md`
- `wiki/design/state.md`
- `wiki/design/sweeps.md`
- `wiki/logging.md`

## proof run

- `uv run python -m compileall -q nuubot`
- `Nuubot().setup()` showed:
  `simnet mainnet simnet`
- All `workspace/templates/*.toml` validated against current Pydantic config.
- `ghbot.ipynb` code cells parsed.
- `ghbot.ipynb` was executed once by the agent during proof and inserted a
  sweep row. This was a mistake because the user asked to check code, not run
  DB-writing code.

## proof not run

- No full test suite.
- Do not execute notebooks again unless the user explicitly says to run them.

## decisions made

- No properties/computed fields unless current code 100% needs them.
- No alias property for a badly named field; rename the field instead.
- No tuple/dict mode lookup for networks; use direct `if/elif`.
- App-level network access is `nuubot.config.data_network` and
  `nuubot.config.exec_network`.
- `ghbot.ipynb` stores loaded template content as `config_json`; no manifest
  path/hash fields.
- Destructive action rule added to `wiki/coding/rules.md`.

## next action

Continue schema/datastore cleanup only when asked. If asked to inspect a
notebook, use static checks unless the user explicitly asks to execute it.
