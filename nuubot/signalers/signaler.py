from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from nuubot.core.dtypes import Bar, MarketSnapshot, Signal
from nuubot.core.format import format_ms
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.signalers.emacross import SignalerEmaCross
from nuubot.signalers.startnow import SignalerStartNow


@dataclass
class SignalerDecision:
    bar: Bar
    signal: Signal
    event: Literal["", "entry", "exit"] = ""


class Signaler:
    def __init__(self, config: BotrunConfig, run_log: Any) -> None:
        self.items = [create_signaler(signaler) for signaler in config.signalers]
        self.log = run_log
        self.last_bar_ms_by_interval: dict[str, int] = {}
        self.last_bar: Bar | None = None
        self.new_bars = 0
        self._eligible: list[tuple[Any, Bar]] = []

    async def init(self) -> None:
        for signaler in self.items:
            await signaler.init()

    async def start(self, data: Any, now_ms: int) -> None:
        for signaler in self.items:
            history = await data.history(signaler.interval, signaler.required_bars)
            self.log.info(f"signaler_seed name={signaler.__class__.__name__} bars={len(history)} ts_now: {format_ms(now_ms)}")
            await signaler.start(history)
            self._mark_closed_history(signaler.interval, history)

    def observe(self, snapshot: MarketSnapshot) -> bool:
        self._eligible = self._eligible_items(snapshot)
        if not self._eligible:
            self.new_bars = 0
            return False

        self.new_bars = self._mark_bars_processed(self._eligible)
        return True

    async def loop_once(self) -> SignalerDecision:
        results = []
        for signaler, bar in self._eligible:
            results.append((bar, await signaler.loop_once(bar)))

        exit_signal = next(((bar, signal) for bar, signal in results if signal.exit), None)
        if exit_signal is not None:
            bar, signal = exit_signal
            self.log.info(f"signal_exit reason={signal.reason} ts_now: {format_ms(bar.ts_ms)}")
            return SignalerDecision(bar, signal, "exit")

        entry_signal = next(((bar, signal) for bar, signal in results if signal.entry), None)
        if entry_signal is not None:
            bar, signal = entry_signal
            self.log.info(f"signal_entry reason={signal.reason} ts_now: {format_ms(bar.ts_ms)}")
            return SignalerDecision(bar, signal, "entry")

        bar, signal = results[0]
        return SignalerDecision(bar, signal)

    async def exit(self) -> bool:
        for signaler in self.items:
            if await signaler.exit():
                return True
        return False

    async def stop(self) -> None:
        for signaler in self.items:
            await signaler.stop()

    def _eligible_items(self, snapshot: MarketSnapshot) -> list[tuple[Any, Bar]]:
        eligible = []
        for signaler in self.items:
            bar = snapshot.bars.get(signaler.interval)
            if bar is None:
                continue
            if not bar.closed and not signaler.partial:
                continue
            if bar.closed and bar.ts_ms <= self.last_bar_ms_by_interval.get(signaler.interval, 0):
                continue
            eligible.append((signaler, bar))
        return eligible

    def _mark_bars_processed(self, eligible: list[tuple[Any, Bar]]) -> int:
        seen: dict[str, Bar] = {}
        for signaler, bar in eligible:
            if bar.closed:
                seen[signaler.interval] = bar

        for interval, bar in seen.items():
            self.last_bar_ms_by_interval[interval] = bar.ts_ms
            if self.last_bar is None or bar.ts_ms >= self.last_bar.ts_ms:
                self.last_bar = bar
        return len(seen)

    def _mark_closed_history(self, interval: str, history: list[Bar]) -> None:
        closed_history = [bar for bar in history if bar.closed]
        if not closed_history:
            return
        last = closed_history[-1]
        self.last_bar_ms_by_interval[interval] = max(self.last_bar_ms_by_interval.get(interval, 0), last.ts_ms)
        if self.last_bar is None or last.ts_ms >= self.last_bar.ts_ms:
            self.last_bar = last


def create_signaler(config: Any) -> Any:
    if config.name == "emacross":
        return SignalerEmaCross(config)
    if config.name == "startnow":
        return SignalerStartNow(config)
    raise ValueError(f"unsupported signaler: {config.name}")
