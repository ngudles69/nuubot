"""Runtime Telemetry"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Telemetry:
    loops: int = 0
    bbo_received: int = 0
    candles_received: int = 0
    bars_processed: int = 0
    signal_entries: int = 0
    signal_exits: int = 0
