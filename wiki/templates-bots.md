---
title: bot templates
created: 2026-07-01
updated: 2026-07-01
type: wiki
status: active
tags: [templates, bots, config]
---

# bot templates

## path

Bot templates live under `workspace/templates/bots/**`.

## model

Bot templates are concrete strategy configs. They may include extra values that
some bots ignore, but coded components must fail fast when the values they need
are missing or invalid.

Generic botrun loading validates the runnable boundary shape. Coded signalers,
executors, and risk objects validate their own params during init.

## concrete bot template

```toml
[market]
symbol = "BTCUSDT"
interval = "1m"

[[signalers]]
name = "emacross"
interval = "1m"
params = { fast = 9, slow = 21 }

[executor]
name = "tradebot"
take_profit_pct = 0.0
stop_loss_pct = 0.0
max_cycles = 0

[risk]
score = 1
```

## rules

- Write active templates as TOML.
- Keep one template to one runnable purpose.
- Keep values explicit; do not hide defaults in comments.
- Current runnable bot configs require `[market]`.
- Current runnable bot configs require at least one `[[signalers]]` entry.
  A run path that needs a specific signaler fails during component init if it is
  missing.
- Current runnable bot configs require `[executor]`.
- `[risk]` is optional.
- Unknown top-level bot keys may be carried as metadata and ignored by the
  runtime. Component-owned sections remain strict.
- Component-specific params are owned by the coded component that uses them.
- Percent fields use plain numeric percent values when the field name ends in
  `_pct`.
- `risk.score` is an integer from `1` to `100`; use `1` for the blank low-risk
  template.

## sweeprun extension

A generated sweeprun record stores metadata beside one concrete botrun config.
The fixed run window is stored in `[botrun.backtest]`:

```toml
[meta]
data = "01"
signalers = "01"
executors = "01"
run = "001"

[botrun.backtest]
start = "2025-01-01"
stop = "2025-06-30T23:59:59"
data_dir = "workspace/data/binance/raw/spot/monthly/klines"
```

Live bots ignore sweeprun-only metadata. Sweeprun execution requires
`[botrun.backtest]`.
