from __future__ import annotations


def dbname(id: int, kind: str, network: str = "") -> str:
    if kind == "sweep":
        return f"sweep_{id}.db"
    if kind == "bot":
        if not network:
            raise RuntimeError("bot db needs network")
        return f"{network}_bot_{id}.db"
    raise RuntimeError(f"unknown db kind: {kind}")
