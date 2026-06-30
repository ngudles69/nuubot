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

Target proof is the direct runtime path until BotManager live process handling
exists:

```bash
uv run python -m nuubot.bots.runtime -f workspace/templates/smoke-backtest.toml
```

Expected:

- Uses Binance BTCUSDT 1m file data.
- Uses January 1, 2025 through January 31, 2025 data window.
- Stops after 200 runtime loops.
- Runs quickly because replay time drives the clock.

## smoke test simnet

Use this when asked to test simnet mode. The template filename still says
`papertest` until the file is renamed.

Target proof is the direct runtime path until BotManager live process handling
exists:

```bash
uv run python -m nuubot.bots.runtime -f workspace/templates/smoke-papertest.toml
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
python -m compileall -q nuubot tests
```

## runtime flow check

```bash
uv run python -m tests.test_runtime_flow
```

## webgui screenshot check

When WebGUI changes, run a headless Playwright check and inspect screenshots.

Target screenshots live in:

```text
workspace/results/webgui-sweeps.png
workspace/results/webgui-sweeps-create.png
```

## sweep check

Target proof is the SweepManager process-pool task path. On Windows, run it
from the server/API or from a guarded proof script that calls
`sweepmgr.run(sweep_id)`; do not launch process-pool sweep work from stdin or
`python -c`.

```bash
uv run python -m nuubot.server
curl.exe -X POST http://127.0.0.1:5001/api/sweeps/<sweep_id>/run
curl.exe http://127.0.0.1:5001/api/sweeps/<sweep_id>/status
```
