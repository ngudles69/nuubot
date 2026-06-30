from __future__ import annotations

import asyncio

from nuubot.core.clock import ReplayClock
from pydantic import ValidationError

from nuubot.core.dtypes import Bar, DataNetwork, ExecNetwork, MarketSnapshot, Mode, ReplayEvent
from nuubot.config.models import AppConfig
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.core.format import format_bar, format_bbo, format_ms
from nuubot.core.market_data import derive_bars, group_replay_events
from nuubot.bots.runtime import Runtime
from nuubot.core.telemetry import Telemetry


class DummySignaler:
    def __init__(self, interval: str, partial: bool = False) -> None:
        self.interval = interval
        self.partial = partial


def test_same_timestamp_events_group_into_one_batch() -> None:
    events = [
        ReplayEvent(1_000, 20, 0, "bar", "1m"),
        ReplayEvent(1_000, 30, 1, "bar", "1h"),
        ReplayEvent(2_000, 20, 2, "bar", "next"),
    ]

    batches = group_replay_events(events)

    assert [batch.ts_ms for batch in batches] == [1_000, 2_000]
    assert [event.payload for event in batches[0].events] == ["1m", "1h"]


def test_larger_interval_bars_are_derived_from_closed_base_bars() -> None:
    base = [
        Bar(0, 10.0, 11.0, 9.0, 10.5, 1.0),
        Bar(60_000, 10.5, 12.0, 10.0, 11.5, 2.0),
        Bar(120_000, 11.5, 13.0, 11.0, 12.5, 3.0),
    ]

    bars = derive_bars(base, "1m", "3m")

    assert bars == [Bar(0, 10.0, 13.0, 9.0, 12.5, 6.0)]


def test_log_format_helpers_are_compact() -> None:
    assert format_ms(1_000).endswith(".000")
    assert "," not in format_ms(1_000)
    assert format_bar(Bar(1_000, 1.0, 2.0, 0.5, 1.5, 10.0)) == "[o:1.0 h:2.0 l:0.5 c:1.5 v:10.0 closed:true]"
    assert format_bbo({"bbo": [{"px": "1", "sz": "2", "n": 3}, {"px": "4", "sz": "5", "n": 6}]}) == "[bid:1 bid_sz:2 bid_n:3 ask:4 ask_sz:5 ask_n:6]"


def test_runtime_rejects_manual_network_fields() -> None:
    data = {
        "runtime": {"bot_id": 1, "mode": "simnet", "data_network": "mainnet", "exec_network": "mainnet", "max_loop": 1, "loop_seconds": 1.0},
        "market": {"symbol": "BTC", "interval": "1m"},
        "signalers": [{"name": "startnow", "interval": "1m"}],
        "executor": {"name": "tradebot", "take_profit_pct": 0.0, "stop_loss_pct": 0.0, "max_cycles": 0},
    }
    try:
        BotrunConfig.model_validate(data)
    except ValidationError as exc:
        assert "Extra inputs are not permitted" in str(exc)
    else:
        raise AssertionError("manual network fields passed")


def test_pydantic_parses_runtime_mode_enums() -> None:
    config = BotrunConfig.model_validate({
        "runtime": {"bot_id": 1, "mode": "simnet", "max_loop": 1, "loop_seconds": 1.0},
        "market": {"symbol": "BTC", "interval": "1m"},
        "signalers": [{"name": "startnow", "interval": "1m"}],
        "executor": {"name": "tradebot", "take_profit_pct": 0.0, "stop_loss_pct": 0.0, "max_cycles": 0},
    })
    assert config.runtime.mode == Mode.SIMNET
    assert config.runtime.data_network == DataNetwork.MAINNET
    assert config.runtime.exec_network == ExecNetwork.SIMNET


def test_mode_network_mapping_is_canonical() -> None:
    cases = [
        ("mainnet", DataNetwork.MAINNET, ExecNetwork.MAINNET),
        ("testnet", DataNetwork.TESTNET, ExecNetwork.TESTNET),
        ("simnet", DataNetwork.MAINNET, ExecNetwork.SIMNET),
        ("backtest", DataNetwork.FILENET, ExecNetwork.SIMNET),
        ("sweep", DataNetwork.FILENET, ExecNetwork.SWEEP),
    ]

    for mode, data_network, exec_network in cases:
        config = BotrunConfig.model_validate({
            "runtime": {"bot_id": 1, "mode": mode, "max_loop": 1, "loop_seconds": 1.0},
            "market": {"symbol": "BTC", "interval": "1m"},
            "signalers": [{"name": "startnow", "interval": "1m"}],
            "executor": {"name": "tradebot", "take_profit_pct": 0.0, "stop_loss_pct": 0.0, "max_cycles": 0},
            "backtest": {"start": "2025-01-01", "stop": "2025-01-02", "data_dir": "workspace/data"},
        })
        assert config.runtime.data_network == data_network
        assert config.runtime.exec_network == exec_network


def test_app_config_rejects_manual_network_fields() -> None:
    data = app_config_data()
    data["general"]["data_network"] = "mainnet"
    data["general"]["exec_network"] = "mainnet"

    try:
        AppConfig.model_validate(data)
    except ValidationError as exc:
        assert "Extra inputs are not permitted" in str(exc)
    else:
        raise AssertionError("manual network fields passed")


def test_app_config_keeps_networks_out_of_general() -> None:
    config = AppConfig.model_validate(app_config_data())

    assert config.general.mode == Mode.SIMNET
    assert config.model_dump(mode="json")["general"] == {"mode": "simnet"}


def app_config_data() -> dict:
    return {
        "workspace": {"root": "."},
        "general": {"mode": "simnet"},
        "paths": {
            "config_dir": "workspace/config",
            "data_dir": "workspace/data",
            "db_dir": "workspace/db",
            "logs_dir": "workspace/logs",
            "results_dir": "workspace/results",
        },
        "databases": {
            "server": "nuubot_server",
            "mainnet": "nuubot_mainnet",
            "testnet": "nuubot_testnet",
            "simnet": "nuubot_simnet",
            "backtest": "nuubot_backtest",
            "sweeps": "nuubot_sweeps",
        },
        "hyperliquid": {"default_network": "testnet"},
        "credentials": {
            "database": {"host": "127.0.0.1", "port": 5432, "user": "postgres", "password": "postgres"},
            "hyperliquid": {
                "accounts": [
                    {"network": "simnet", "name": "grid", "address": "0x0", "api_key": "key"},
                ]
            },
        },
    }


async def test_replay_clock_dispatches_once_per_same_timestamp() -> None:
    clock = ReplayClock()
    called = []

    async def callback(event) -> None:
        called.append(event)

    clock.set_timer("runtime", 1.0, callback)
    clock.set_time(1_000)
    await clock.dispatch_due(1_000)
    await clock.dispatch_due(1_000)

    assert len(called) == 1


def test_runtime_keeps_all_signalers_for_same_new_bar() -> None:
    runtime = Runtime.__new__(Runtime)
    runtime.signalers = [DummySignaler("1m"), DummySignaler("1m")]
    runtime.last_bar_ms_by_interval = {"1m": 999}
    runtime.last_bar = None
    runtime.bars_processed = 0
    runtime.telemetry = Telemetry()

    bar = Bar(1_000, 1.0, 2.0, 0.5, 1.5, 10.0)
    snapshot = MarketSnapshot(bars={"1m": bar})

    eligible = Runtime.eligible_signalers(runtime, snapshot)
    Runtime.mark_bars_processed(runtime, eligible)

    assert len(eligible) == 2
    assert runtime.last_bar_ms_by_interval["1m"] == 1_000
    assert runtime.bars_processed == 1


async def main() -> None:
    test_same_timestamp_events_group_into_one_batch()
    test_larger_interval_bars_are_derived_from_closed_base_bars()
    test_log_format_helpers_are_compact()
    test_runtime_rejects_manual_network_fields()
    test_pydantic_parses_runtime_mode_enums()
    test_mode_network_mapping_is_canonical()
    test_app_config_rejects_manual_network_fields()
    test_app_config_keeps_networks_out_of_general()
    await test_replay_clock_dispatches_once_per_same_timestamp()
    test_runtime_keeps_all_signalers_for_same_new_bar()


if __name__ == "__main__":
    asyncio.run(main())
