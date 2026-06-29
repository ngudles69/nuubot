---
title: config object
created: 2026-06-23
updated: 2026-06-23
type: wiki
status: active
tags: [design, objects, config]
---

# config object

## purpose

Config is a simple object that holds validated bot config.

It does not own trading logic, runtime flow, persistence, or exchange access.

## interfaces

External commands:

- `Config(path)`
- `load()`
- `stop()`
- `validate()`

Config receives:

- TOML param file path.
- credentials file from the same config path.

Config outputs:

- validated runtime, market, credentials, exchange/account, signaler, executor,
  risk, and backtest settings.
- Pydantic config objects that can be displayed through Pydantic dump methods.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `Config(path)` | Existing TOML path. | Config object. | Stores config path and prepares empty state. Does not load yet. |
| `load()` | Stored config path. | Pydantic config object. | Reads the config file and credentials file from the same path, then validates the Pydantic model. Fails loud on missing credentials, parse errors, or unreadable files. |
| `stop()` | Loaded Config. | Stopped Config. | No external resources; clears transient state if any. |
| `validate()` | Loaded config data. | Valid config or error. | Runs all field and cross-section checks. Does not repair bad input. |
| Pydantic dump | Valid config. | JSON-safe display data. | Use Pydantic `model_dump(mode="json")` or `model_dump_json()`. Secret fields must display masked values. Do not code custom JSON output. |

## processing

Internal functions:

- read TOML.
- read credentials from the same config path.
- validate required sections.
- reject unknown fields.
- validate cross-section rules, for example backtest mode requires backtest
  config.
- load credential fields into Pydantic secret types.

## key helpers

- mode validation.
- section validation.
- path normalization.
- literal enum parsing.

## notes

- Config should stay boring.
- Do not add config flags for values that never change.
- Config does not create runtime objects.
- Config opens only the config file and its credentials file.
- Fail fast. Fail loud. Do not infer, repair, default, or silently ignore bad
  config.
- Use Pydantic `SecretStr` for secrets such as `api_key`.
- `model_dump(mode="json")` and `model_dump_json()` are the display path.
- Do not add custom `to_json()` or an unredacted JSON view.
