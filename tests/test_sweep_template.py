from __future__ import annotations

from pathlib import Path
import tomllib

from nuubot.sweeps.template import expand_sweep_template, generate_sweepruns


def main() -> None:
    expands_2025_halves_template_to_36_sweepruns()
    rejects_bad_labels_after_toml_parse()


def expands_2025_halves_template_to_36_sweepruns() -> None:
    data = tomllib.loads(Path("workspace/templates/sweeps/emacross-tradebot-2025-halves.toml").read_text(encoding="utf-8"))
    normalized = expand_sweep_template(data, "workspace/data/binance/raw/spot/monthly/klines")
    rows = generate_sweepruns(normalized)
    assert len(rows) == 36
    assert rows[0]["sweeprun"]["meta"] == {"data": "01", "signaler": "01", "executor": "01", "risk": "default", "run": "001"}
    assert rows[0]["executor"]["symbol"] == "BTCUSDT"
    assert rows[0]["executor"]["interval"] == "1h"
    assert rows[0]["sweeprun"]["end"] == "2025-06-30T23:59:59"
    assert rows[0]["signaler"]["params"] == {"fast": 5, "slow": 20}
    assert rows[-1]["sweeprun"]["meta"] == {"data": "02", "signaler": "01", "executor": "01", "risk": "default", "run": "036"}
    assert rows[-1]["executor"]["symbol"] == "SOLUSDT"
    assert rows[-1]["executor"]["interval"] == "1h"
    assert rows[-1]["sweeprun"]["end"] == "2025-12-31T23:59:59"
    assert rows[-1]["signaler"]["params"] == {"fast": 11, "slow": 50}


def rejects_bad_labels_after_toml_parse() -> None:
    data = tomllib.loads(
        """
[sweep]
mode = "fast"
data_dir = "workspace/data/binance/raw/spot/monthly/klines"

[[data."bad/label"]]
[data."bad/label".sweeprun]
start = "2025-01-01"
end = "2025-01-31"

[[signalers.01]]
[[signalers.01.items]]
name = "emacross"
interval = "1m"
params = { fast = 5, slow = 20 }

[[executors.01]]
[executors.01.executor]
symbol = "BTCUSDT"
interval = "1m"
name = "tradebot"
take_profit_pct = 0.0
stop_loss_pct = 0.0
max_cycles = 0
"""
    )
    try:
        expand_sweep_template(data, "workspace/data/binance/raw/spot/monthly/klines")
    except ValueError as exc:
        assert "invalid data label: bad/label" in str(exc)
    else:
        raise AssertionError("bad quoted label should fail")


if __name__ == "__main__":
    main()
