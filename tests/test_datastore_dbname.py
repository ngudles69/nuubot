from __future__ import annotations

from nuubot.datastore import dbname


def main() -> None:
    assert dbname(25, "sweep") == "sweep_25.db"
    assert dbname(7, "bot", "mainnet") == "mainnet_bot_7.db"
    try:
        dbname(7, "bot")
    except RuntimeError as exc:
        assert str(exc) == "bot db needs network"
    else:
        raise AssertionError("bot DB without network should fail")


if __name__ == "__main__":
    main()
