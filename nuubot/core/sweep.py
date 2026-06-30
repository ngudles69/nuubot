from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import time
from pathlib import Path
from typing import Any

from nuubot.core.config import load_sweep_config
from nuubot.core.logger import logger
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.core.market_data import load_binance_bars, required
from nuubot.core.runtime import Runtime
from nuubot.tradebot.tradebot import ExecutorTrade, TradeConfig
from nuubot.signaler.emacross import SignalerEmaCross

log = logger("workspace/logs/runtime.log")


def expand_values(value: Any) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    if isinstance(value, dict):
        current = float(required(value, "start", "params"))
        stop = float(required(value, "stop", "params"))
        step = float(required(value, "step", "params"))
        output = []
        while current <= stop + 1e-12:
            output.append(round(current, 10))
            current += step
        return output
    raise TypeError(f"bad parameter shape: {value}")


def load_sweep(path: Path) -> tuple[str, list[BotrunConfig]]:
    config = load_sweep_config(path)
    sweep = config.sweep
    params = config.params
    mode = str(required(sweep, "mode", "sweep"))
    start_bot_id = int(required(sweep, "start_bot_id", "sweep"))
    if mode not in {"fast", "standard"}:
        raise ValueError(f"unsupported sweep mode: {mode}")

    configs = []
    grid = itertools.product(
        expand_values(required(params, "ema_fast", "params")),
        expand_values(required(params, "ema_slow", "params")),
    )
    for index, (fast, slow) in enumerate(grid):
        bot_data = sweep_bot_data(config.botrun, start_bot_id + index, int(fast), int(slow))
        configs.append(BotrunConfig.model_validate(bot_data))
    return mode, configs


def sweep_bot_data(config: BotrunConfig, bot_id: int, ema_fast: int, ema_slow: int) -> dict[str, Any]:
    bot_data = config.model_dump()
    bot_data["runtime"]["bot_id"] = bot_id
    bot_data["runtime"]["mode"] = "sweep"
    bot_data["signalers"][0]["params"]["fast"] = ema_fast
    bot_data["signalers"][0]["params"]["slow"] = ema_slow
    return bot_data


async def run_fast(configs: list[BotrunConfig]) -> None:
    total_start = time.perf_counter()
    load_start = time.perf_counter()
    bars = load_binance_bars(configs[0])
    load_ms = (time.perf_counter() - load_start) * 1000

    results = []
    indicator_ms = 0.0
    run_ms = 0.0
    for config in configs:
        try:
            indicator_start = time.perf_counter()
            signaler = SignalerEmaCross(config.signalers[0])
            signals = await signaler.ingest_many(bars)
            indicator_ms += (time.perf_counter() - indicator_start) * 1000

            run_start = time.perf_counter()
            if config.executor.name != "tradebot":
                raise ValueError(f"fast sweep supports tradebot only: {config.executor.name}")
            executor = ExecutorTrade(TradeConfig(config.runtime.bot_id, config.executor.take_profit_pct, config.executor.stop_loss_pct, config.executor.max_cycles))
            for bar, signal in zip(bars, signals, strict=True):
                await executor.loop_once(bar, signal)
            await executor.stop(bars[-1])
            results.append(executor.result(len(bars)))
            run_ms += (time.perf_counter() - run_start) * 1000
        except Exception:
            log.error("sweeprun aborted.")
            raise

    total_ms = (time.perf_counter() - total_start) * 1000
    summary = {
        "mode": "fast",
        "configs": len(results),
        "bars": len(bars),
        "data_load_ms": round(load_ms, 3),
        "indicator_build_ms": round(indicator_ms, 3),
        "strategy_run_ms": round(run_ms, 3),
        "total_ms": round(total_ms, 3),
        "bars_per_second": round(len(bars) * len(results) / max(run_ms / 1000, 1e-9), 3),
        "configs_per_second": round(len(results) / max(run_ms / 1000, 1e-9), 3),
        "worker_count": 1,
    }
    print("SWEEP_SUMMARY:\n" + json.dumps(summary, indent=2, sort_keys=True))
    print("SWEEP_BEST:\n" + json.dumps([result.__dict__ for result in sorted(results, key=lambda item: item.pnl_pct, reverse=True)[:5]], indent=2, sort_keys=True))


async def run_standard(configs: list[BotrunConfig]) -> None:
    total_start = time.perf_counter()
    results = []
    for config in configs:
        try:
            runtime = Runtime(config)
            await runtime.init()
            await runtime.start()
            try:
                await runtime.loop()
            finally:
                await runtime.stop()
            if runtime.result is None:
                raise RuntimeError(f"missing runtime result for bot_id={config.runtime.bot_id}")
            results.append(runtime.result)
        except Exception:
            log.error("sweeprun aborted.")
            raise

    total_ms = (time.perf_counter() - total_start) * 1000
    loops = sum(result.bars for result in results)
    summary = {
        "mode": "standard",
        "configs": len(results),
        "loops": loops,
        "total_ms": round(total_ms, 3),
        "loops_per_second": round(loops / max(total_ms / 1000, 1e-9), 3),
        "configs_per_second": round(len(results) / max(total_ms / 1000, 1e-9), 3),
        "worker_count": 1,
    }
    print("SWEEP_SUMMARY:\n" + json.dumps(summary, indent=2, sort_keys=True))
    print("SWEEP_BEST:\n" + json.dumps([result.__dict__ for result in sorted(results, key=lambda item: item.pnl_pct, reverse=True)[:5]], indent=2, sort_keys=True))


async def run(path: Path) -> None:
    try:
        mode, configs = load_sweep(path)
        if not configs:
            raise RuntimeError("sweep produced no configs")
        if mode == "fast":
            await run_fast(configs)
        else:
            await run_standard(configs)
    except Exception:
        log.error("sweep aborted.")
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True)
    args = parser.parse_args()
    asyncio.run(run(Path(args.file)))

if __name__ == "__main__":
    main()
