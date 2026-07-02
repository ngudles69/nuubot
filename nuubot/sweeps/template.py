from __future__ import annotations

from itertools import product
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nuubot.core.market_data import date_ms
from nuubot.sweeps.models import SweeprunConfig

LABEL_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class GeneratedSweeprun(SweeprunConfig):
    model_config = ConfigDict(extra="forbid")


class GroupSweepConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    sweep: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, list[dict[str, Any]]]
    signalers: dict[str, list[dict[str, Any]]]
    executors: dict[str, list[dict[str, Any]]]
    risk: dict[str, Any] = Field(default_factory=lambda: {"score": 1})

    @model_validator(mode="after")
    def validate_labels(self) -> "GroupSweepConfig":
        for family in ("data", "signalers", "executors"):
            for label in getattr(self, family):
                if not LABEL_RE.fullmatch(label):
                    raise ValueError(f"invalid {family} label: {label}")
        return self


def normalize_sweep_template(data: dict[str, Any], data_dir: str) -> dict[str, Any]:
    config = GroupSweepConfig.model_validate(data)
    result = config.model_dump(mode="json")
    result["sweep"]["data_dir"] = data_dir
    generated = expand_sweep_template(result)
    if not generated:
        raise RuntimeError("sweep produced no sweepruns")
    return result


def expand_sweep_template(data: dict[str, Any]) -> list[dict[str, Any]]:
    config = GroupSweepConfig.model_validate(data)
    mode = str(config.sweep.get("mode", ""))
    if mode not in {"fast", "standard"}:
        raise RuntimeError(f"unsupported sweep mode: {mode}")
    start_bot_id = int(config.sweep.get("start_bot_id", 0))
    data_dir = str(config.sweep.get("data_dir", ""))
    if not data_dir:
        raise RuntimeError("sweep.data_dir is required")

    data_sets = _family_variants("data", config.data)
    signaler_sets = _family_variants("signalers", config.signalers)
    executor_sets = _family_variants("executors", config.executors)
    risk_values = expand_object(config.risk)

    rows: list[dict[str, Any]] = []
    for index, (data_set, signaler_set, executor_set, risk) in enumerate(product(data_sets, signaler_sets, executor_sets, risk_values), start=1):
        bot_id = start_bot_id + index - 1
        meta = {
            "data": data_set["label"],
            "signalers": signaler_set["label"],
            "executors": executor_set["label"],
            "run": f"{index:03d}",
        }
        market = _required_dict(data_set["value"], "market", f"data.{meta['data']}")
        sweeprun = _required_dict(data_set["value"], "sweeprun", f"data.{meta['data']}")
        _validate_window(sweeprun)
        executor = _required_dict(executor_set["value"], "executor", f"executors.{meta['executors']}")
        signalers = signaler_set["value"].get("items")
        if not isinstance(signalers, list):
            raise RuntimeError(f"signalers.{meta['signalers']}.items is required")

        botrun = {
            "runtime": {"bot_id": bot_id, "mode": "sweep", "max_loop": 0, "loop_seconds": 1.0},
            "market": market,
            "backtest": {"start": sweeprun["start"], "stop": sweeprun["stop"], "data_dir": data_dir},
            "signalers": signalers,
            "executor": executor,
            "risk": risk,
        }
        row = GeneratedSweeprun.model_validate({**botrun, "meta": meta}).model_dump(mode="json")
        rows.append(row)
    return rows


def expand_object(value: Any) -> list[Any]:
    if isinstance(value, dict):
        if set(value) == {"start", "stop", "step"}:
            return _range_values(value)
        keys = list(value)
        variants = [expand_object(value[key]) for key in keys]
        return [dict(zip(keys, items)) for items in product(*variants)]
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            variants = [expand_object(item) for item in value]
            return [list(items) for items in product(*variants)]
        return value
    return [value]


def _family_variants(family: str, groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for label, values in groups.items():
        if not LABEL_RE.fullmatch(label):
            raise ValueError(f"invalid {family} label: {label}")
        for value in values:
            for expanded in expand_object(value):
                rows.append({"label": label, "value": expanded})
    return rows


def _range_values(value: dict[str, Any]) -> list[float | int]:
    current = float(value["start"])
    stop = float(value["stop"])
    step = float(value["step"])
    if step <= 0:
        raise ValueError(f"range step must be positive: {value}")
    output = []
    while current <= stop + 1e-12:
        item = round(current, 10)
        output.append(int(item) if item.is_integer() else item)
        current += step
    return output


def _required_dict(data: dict[str, Any], key: str, section: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"{section}.{key} is required")
    return value


def _validate_window(sweeprun: dict[str, Any]) -> None:
    if "start" not in sweeprun:
        raise RuntimeError("sweeprun.start is required")
    if "stop" not in sweeprun:
        raise RuntimeError("sweeprun.stop is required")
    if date_ms(str(sweeprun["start"])) > date_ms(str(sweeprun["stop"])):
        raise RuntimeError(f"sweeprun.start must be <= stop: {sweeprun['start']}..{sweeprun['stop']}")
