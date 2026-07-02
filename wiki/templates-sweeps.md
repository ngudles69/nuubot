---
title: sweep templates
created: 2026-07-01
updated: 2026-07-02
type: wiki
status: active
tags: [templates, sweeps, config]
---

# sweep templates

## path

Sweep templates live under `workspace/templates/sweeps/**`.

`workspace/templates/sweeps/old/**` is reference-only. Do not use it as the
active template set.

## model

Sweep templates are authoring files. They expand into concrete scalar
sweeprun configs before records are created.

Expansion rule:

```text
expanded data sets
x expanded signaler sets
x expanded executor sets
x expanded risk values
= generated sweeprun configs
```

Generated sweeprun configs drop the set wrappers and store one definitive
`market.symbol`, one `market.interval`, one `signaler`, concrete executor
params, optional risk config, and a `sweeprun` section with the test window and
metadata. Botrun config readers ignore the whole `sweeprun` section.

## set families

Only the family prefix is semantic:

```toml
[[data.01]]
[[signalers.01]]
[[executors.01]]
```

The label after the prefix is metadata for humans, logs, and results. Use
numeric labels when order is enough. Use names when meaning matters.

Valid labels use only letters, numbers, `_`, and `-`. Do not use `/`, `.`, `=`,
spaces, or quoted labels.

TOML parsing catches unquoted bad labels such as `[[data.bad/label]]`.
Quoted bad labels such as `[[data."bad/label"]]` parse, but template validation
must reject them.

## sweepable values

Sweep templates may use:

```toml
fast = [5, 8, 11]
slow = { start = 20, stop = 50, step = 10 }
```

Rules:

- Scalars copy through unchanged.
- Lists expand as exact values.
- `{ start, stop, step }` expands as an inclusive numeric range.
- Values inside one set expand internally.
- Expanded sets cross with other expanded sets and expanded risk values.

## example

```toml
[sweep]
mode = "fast"
workers = 8

[[data.01]]
[data.01.market]
symbol = ["BTCUSDT", "SOLUSDT"]
interval = "1h"

[data.01.sweeprun]
start = "2025-01-01"
end = "2025-06-30T23:59:59"

[[data.02]]
[data.02.market]
symbol = ["BTCUSDT", "SOLUSDT"]
interval = "1h"

[data.02.sweeprun]
start = "2025-07-01"
end = "2025-12-31T23:59:59"

[[signalers.01]]
[[signalers.01.items]]
name = "emacross"
interval = "1h"
params = { fast = { start = 5, stop = 11, step = 3 }, slow = [20, 30, 50] }

[[executors.01]]
[executors.01.executor]
name = "tradebot"
take_profit_pct = 0.0
stop_loss_pct = 0.0
max_cycles = 0

[risk]
score = 1
```

This expands to:

```text
2 symbols x 2 data windows x 3 fast values x 3 slow values = 36 sweepruns
```

Generated sweeprun name:

```text
emacross-tradebot-2025-halves/data=01/signaler=01/executor=01/risk=default/run=001
```

Use this as DB/log/display metadata. If a filesystem-safe slug is needed, derive
it from the same metadata.

## rules

- Write active templates as TOML.
- Keep one template to one runnable purpose.
- Keep values explicit; do not hide defaults in comments.
- `[sweep].mode` is the execution shell: currently `fast` or `standard`.
- `[sweep].mode` must not silently change `[executor].name`.
- Data sets must generate `[market]` with `symbol` and `interval`.
- Data sets must generate `sweeprun` with `start` and `end`.
- Signaler sets generate final `[signaler]`.
- Executor sets generate final `[executor]`.
- If two groups write the same final path, fail loud.
- Generated sweepruns must validate before records are created.
- Percent fields use plain numeric percent values when the field name ends in
  `_pct`.
- `risk.score` is an integer from `1` to `100`; use `1` for the blank low-risk
  template.

## validation

1. Parse TOML.
2. Validate set labels.
3. Expand set permutations.
4. Validate generated sweepruns with Pydantic.
5. Create records only after all generated sweepruns pass.
