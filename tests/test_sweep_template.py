from __future__ import annotations

from pathlib import Path
import tomllib

from nuubot.core.models.mconfig import BotrunConfig
from nuubot.sweeps.sweeprun import validate_supported_sweeprun_runtime
from nuubot.sweeps.template import expand_sweep_template, normalize_sweep_template


def main() -> None:
    expands_2025_halves_template_to_36_sweepruns()
    rejects_bad_labels_after_toml_parse()
    rejects_sweeprun_runtime_multiple_signalers()


def expands_2025_halves_template_to_36_sweepruns() -> None:
    data = tomllib.loads(Path("workspace/templates/sweeps/emacross-tradebot-2025-halves.toml").read_text(encoding="utf-8"))
    normalized = normalize_sweep_template(data, "workspace/data/binance/raw/spot/monthly/klines")
    rows = expand_sweep_template(normalized)
    assert len(rows) == 36
    assert rows[0]["meta"] == {"data": "01", "signalers": "01", "executors": "01", "run": "001"}
    assert rows[0]["botrun"]["market"] == {"symbol": "BTCUSDT", "interval": "1h"}
    assert rows[0]["botrun"]["signalers"][0]["params"] == {"fast": 5, "slow": 20}
    assert rows[-1]["meta"] == {"data": "02", "signalers": "01", "executors": "01", "run": "036"}
    assert rows[-1]["botrun"]["market"] == {"symbol": "SOLUSDT", "interval": "1h"}
    assert rows[-1]["botrun"]["signalers"][0]["params"] == {"fast": 11, "slow": 50}


def rejects_bad_labels_after_toml_parse() -> None:
    data = tomllib.loads(
        """
[sweep]
mode = "fast"
data_dir = "workspace/data/binance/raw/spot/monthly/klines"

[[data."bad/label"]]
[data."bad/label".market]
symbol = "BTCUSDT"
interval = "1m"

[data."bad/label".sweeprun]
start = "2025-01-01"
stop = "2025-01-31"

[[signalers.01]]
[[signalers.01.items]]
name = "emacross"
interval = "1m"
params = { fast = 5, slow = 20 }

[[executors.01]]
[executors.01.executor]
name = "tradebot"
take_profit_pct = 0.0
stop_loss_pct = 0.0
max_cycles = 0
"""
    )
    try:
        normalize_sweep_template(data, "workspace/data/binance/raw/spot/monthly/klines")
    except ValueError as exc:
        assert "invalid data label: bad/label" in str(exc)
    else:
        raise AssertionError("bad quoted label should fail")


def rejects_sweeprun_runtime_multiple_signalers() -> None:
    config = BotrunConfig.model_validate(
        {
            "runtime": {"bot_id": 1, "mode": "sweep", "max_loop": 0, "loop_seconds": 1.0},
            "market": {"symbol": "BTCUSDT", "interval": "1h"},
            "backtest": {
                "start": "2025-01-01",
                "stop": "2025-01-02",
                "data_dir": "workspace/data/binance/raw/spot/monthly/klines",
            },
            "signalers": [
                {"name": "emacross", "interval": "1h", "params": {"fast": 5, "slow": 20}},
                {"name": "emacross", "interval": "1h", "params": {"fast": 8, "slow": 30}},
            ],
            "executor": {"name": "tradebot", "take_profit_pct": 0.0, "stop_loss_pct": 0.0, "max_cycles": 0},
        }
    )
    try:
        validate_supported_sweeprun_runtime(config)
    except ValueError as exc:
        assert "sweep supports exactly one signaler: got=2" in str(exc)
    else:
        raise AssertionError("multiple signalers should fail loud")


if __name__ == "__main__":
    main()
