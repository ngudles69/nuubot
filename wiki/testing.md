---
title: testing
created: 2026-06-21
updated: 2026-06-29
type: wiki
status: active
tags: [testing, smoke, runtime]
---

# testing

## smoke test backtest

Use this when asked to test backtest mode.

Target proof is the CLI/Ray bot actor launch path. Until that exists, this is
only a pre-Ray smoke check:

```bash
rtk uv run python -m nuubot.core.runtime -f workspace/templates/smoke-backtest.toml
```

Expected:

- Uses Binance BTCUSDT 1m file data.
- Uses January 1, 2025 through January 31, 2025 data window.
- Stops after 200 runtime loops.
- Runs quickly because replay time drives the clock.

## smoke test simnet

Use this when asked to test simnet mode. The template filename still says
`papertest` until the file is renamed.

Target proof is the CLI/Ray bot actor launch path. Until that exists, this is
only a pre-Ray smoke check:

```bash
rtk uv run python -m nuubot.core.runtime -f workspace/templates/smoke-papertest.toml
```

Expected:

- Connects to Hyperliquid mainnet websocket.
- Subscribes to BTC BBO and 1m candles.
- Stops after 20 runtime loops.
- Takes about 20 seconds because wall time drives the clock.

## compile check

Run this before smoke tests when runtime, config, clock, signaler, executor, or
sweep code changed.

```bash
rtk uv run python -m py_compile nuubot/core/config.py nuubot/core/models/mconfig.py nuubot/core/clock.py nuubot/core/market_data.py nuubot/core/runtime.py nuubot/core/sweep.py nuubot/core/risk.py nuubot/executor/tradebot.py nuubot/signaler/emacross.py nuubot/signaler/startnow.py
```

## runtime flow check

```bash
rtk uv run python -m tests.test_runtime_flow
```

## sweep fast check

Target proof is the CLI/Ray task launch path. Until that exists, this is only a
pre-Ray smoke check:

```bash
rtk uv run python -m nuubot.core.sweep -f workspace/templates/ema-1h-fast.toml
```

## sweep standard check

Target proof is the CLI/Ray task launch path. Until that exists, this is only a
pre-Ray smoke check:

```bash
rtk uv run python -m nuubot.core.sweep -f workspace/templates/ema-1h-standard.toml
```
