from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


def dec(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class Fill:
    cloid: str
    oid: int | None
    side: str
    price: Decimal
    size: Decimal
    fee: Decimal
    ts_ms: int
    raw: dict[str, Any] = field(default_factory=dict)

    def init(self) -> None:
        if not self.cloid and self.oid is None:
            raise ValueError("fill requires cloid or oid")
        if self.size <= 0:
            raise ValueError(f"fill size must be positive: {self.size}")
        if self.side not in {"buy", "sell"}:
            raise ValueError(f"fill side must be buy or sell: {self.side}")

    def key(self) -> str:
        raw_key = self.raw.get("fill_key")
        if raw_key:
            return str(raw_key)
        return f"{self.cloid}:{self.oid}:{self.ts_ms}:{self.side}:{self.price}:{self.size}"
