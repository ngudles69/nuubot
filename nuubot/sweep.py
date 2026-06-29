from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tomllib
from typing import Any

from nuubot.core.models.mconfig import SweepConfig
from nuubot.datastore import SweepRow
from nuubot.nuubot import Nuubot


@dataclass(frozen=True)
class SweepManager:
    nuubot: Nuubot

    def create_sweep(self, template: str | dict[str, Any]) -> int:
        template_data = self._template_data(template)
        sweep_id = self.nuubot.datastore.next_seq("sweep")
        db_path = self.sweep_db_path(sweep_id)
        self.nuubot.datastore.init_sweep(db_path)
        with self.nuubot.datastore.session(db_path) as session:
            session.add(
                SweepRow(
                    sweep_id=sweep_id,
                    sweep_desc="sweep",
                    config_json=json.dumps(template_data, sort_keys=True, separators=(",", ":")),
                    results_json="{}",
                    status="configured",
                    sweeprun_count=0,
                )
            )
            session.commit()
        return sweep_id

    def load_sweep(self, sweep_id: int) -> dict[str, Any]:
        db_path = self.sweep_db_path(sweep_id)
        if not db_path.exists():
            raise RuntimeError(f"sweep DB missing: {db_path}")
        with self.nuubot.datastore.session(db_path) as session:
            sweep = session.get(SweepRow, sweep_id)
            if sweep is None:
                raise RuntimeError(f"sweep row missing: {sweep_id}")
            config = json.loads(sweep.config_json)
        SweepConfig.model_validate(config)
        return config

    def sweep_db_path(self, sweep_id: int) -> Path:
        return Path(self.nuubot.config.workspace.root) / self.nuubot.config.paths.db_dir / f"sweep_{sweep_id}.db"

    def _template_data(self, template: str | dict[str, Any]) -> dict[str, Any]:
        data = tomllib.loads(template) if isinstance(template, str) else template
        data["botrun"]["runtime"].setdefault("loop_seconds", 1.0)
        data["botrun"]["backtest"]["data_dir"] = (
            f"{self.nuubot.config.paths.data_dir}/binance/raw/spot/monthly/klines"
        )
        SweepConfig.model_validate(data)
        return data


def sweepmgr_setup(nuubot: Nuubot) -> SweepManager:
    if nuubot.config is None or nuubot.datastore is None:
        raise RuntimeError("nuubot_setup() must complete before sweepmgr_setup()")
    return SweepManager(nuubot)
