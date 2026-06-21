from __future__ import annotations

import asyncio

from nuubot.core.clock import ReplayClock
from nuubot.core.dtypes import Bar, MarketSnapshot, ReplayEvent
from nuubot.core.market_data import derive_bars, group_replay_events
from nuubot.core.runtime import Runtime
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
    await test_replay_clock_dispatches_once_per_same_timestamp()
    test_runtime_keeps_all_signalers_for_same_new_bar()


if __name__ == "__main__":
    asyncio.run(main())
