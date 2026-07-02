from __future__ import annotations

from nuubot.core.models.mconfig import SignalerConfig
from nuubot.signalers.emacross import SignalerEmaCross
from nuubot.sweeps.signalers import SwEmacross


def main() -> None:
    rejects_non_integer_ema_periods()


def rejects_non_integer_ema_periods() -> None:
    for cls in (SignalerEmaCross, SwEmacross):
        config = SignalerConfig(name="emacross", interval="1h", params={"fast": 5.9, "slow": 20})
        try:
            if cls is SwEmacross:
                signaler = cls()
                signaler.init(config)
            else:
                cls(config)
        except ValueError as exc:
            assert "EMA periods must be integers" in str(exc)
        else:
            raise AssertionError(f"{cls.__name__} accepted non-integer EMA period")


if __name__ == "__main__":
    main()
