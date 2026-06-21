from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from nuubot.core.logger import logger

log = logger("workspace/logs/runtime.log")

TimerCallback = Callable[["TimeEvent"], Awaitable[None]]


@dataclass
class TimeEvent:
    name: str
    ts_event_ms: int
    ts_init_ms: int


@dataclass
class Timer:
    name: str
    interval_ms: int
    next_ms: int
    callback: TimerCallback


class Clock:
    def __init__(self, min_timer_interval_ms: int = 1000) -> None:
        self.min_timer_interval_ms = min_timer_interval_ms
        self._now_ms = self._wall_ms()
        self.timers: dict[str, Timer] = {}

    def now_ms(self) -> int:
        return self._now_ms

    def set_timer(self, name: str, interval_seconds: float, callback: TimerCallback) -> None:
        if name in self.timers:
            raise ValueError(f"timer already exists: {name}")
        interval_ms = int(interval_seconds * 1000)
        if interval_ms < self.min_timer_interval_ms:
            log.warning(f"timer {name} interval is too low. setting to {self.min_timer_interval_ms} ms.")
            interval_ms = self.min_timer_interval_ms
        self.timers[name] = Timer(name, interval_ms, self._now_ms + interval_ms, callback)

    def cancel_timer(self, name: str) -> None:
        if name not in self.timers:
            raise ValueError(f"timer does not exist: {name}")
        del self.timers[name]

    async def tick(self) -> list[TimeEvent]:
        if self.timers:
            sleep_ms = min(timer.next_ms for timer in self.timers.values()) - self._wall_ms()
            if sleep_ms > 0:
                await asyncio.sleep(sleep_ms / 1000)
        self._now_ms = self._wall_ms()
        events = self.advance(self._now_ms)
        await self.dispatch(events)
        return events

    async def dispatch(self, events: list[TimeEvent]) -> None:
        for event in events:
            timer = self.timers.get(event.name)
            if timer is not None:
                await timer.callback(event)

    async def run(self) -> None:
        while self.timers:
            await self.tick()

    def advance(self, now_ms: int) -> list[TimeEvent]:
        if now_ms < self._now_ms:
            raise ValueError(f"clock cannot go backwards: {now_ms} < {self._now_ms}")
        self._now_ms = now_ms
        events = []
        for timer in self.timers.values():
            if timer.next_ms <= now_ms:
                events.append(TimeEvent(timer.name, timer.next_ms, self._now_ms))
                timer.next_ms = now_ms + timer.interval_ms
        return events

    def _wall_ms(self) -> int:
        return int(time.time() * 1000)


class ReplayClock(Clock):
    def __init__(self, min_timer_interval_ms: int = 1000) -> None:
        super().__init__(min_timer_interval_ms)
        self._now_ms = 0

    async def advance_and_dispatch(self, now_ms: int) -> list[TimeEvent]:
        events = self.advance(now_ms)
        await self.dispatch(events)
        return events
