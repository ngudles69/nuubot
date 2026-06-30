from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from nuubot.core.context import IdCtx
from nuubot.core.dtypes import Bar, Signal
from nuubot.core.logger import format_bar, format_ms, logger
from nuubot.core.market_data import date_ms, load_binance_bars
from nuubot.core.models.mconfig import BotrunConfig
from nuubot.datastore import BotrunRow, SweeprunRow
from nuubot.signaler.emacross import SignalerEmaCross
from nuubot.sweeps.models import SweeprunConfig
from nuubot.tradebot.tradebot import ExecutorTrade, TradeConfig, TradeLedger


@dataclass
class Sweeprun:
    db_path: str
    sweep_id: int
    sweeprun_id: int
    worker_name: str
    bot_id: int | None = None
    config: BotrunConfig | None = None
    sweeprun_config: SweeprunConfig | None = None
    id_ctx: IdCtx | None = None
    bars: list[Bar] | None = None
    signaler: SignalerEmaCross | None = None
    executor: ExecutorTrade | None = None
    engine: Engine | None = None
    run_log: Any | None = None
    log_path: Path | None = None

    def load(self) -> None:
        if self.engine is None:
            raise RuntimeError("sweeprun engine missing")
        with Session(self.engine, expire_on_commit=False) as session:
            sweeprun = session.get(SweeprunRow, self.sweeprun_id)
            if sweeprun is None or sweeprun.sweep_id != self.sweep_id:
                raise RuntimeError(f"sweeprun row missing: {self.sweeprun_id}")
            sweeprun.status = "running"
            botrun = session.query(BotrunRow).filter_by(sweeprun_id=self.sweeprun_id, botrun_index=0).one_or_none()
            if botrun is None:
                raise RuntimeError(f"botrun row missing: {self.sweeprun_id}")
            botrun.status = "running"
            self.sweeprun_config = SweeprunConfig.model_validate(json.loads(sweeprun.config_json))
            self.config = self.sweeprun_config.botrun
            self.bot_id = int(botrun.bot_id)
            session.commit()

    async def run(self) -> dict[str, Any]:
        self.engine = create_engine(f"sqlite:///{Path(self.db_path).as_posix()}", future=True, connect_args={"timeout": 30})
        try:
            self.load()
            result = await self.loop()
            result_json = json.dumps(result, sort_keys=True, separators=(",", ":"))
            with Session(self.engine, expire_on_commit=False) as session:
                sweeprun = session.get(SweeprunRow, self.sweeprun_id)
                if sweeprun is None:
                    raise RuntimeError(f"sweeprun row missing: {self.sweeprun_id}")
                sweeprun.status = "complete"
                sweeprun.results_json = result_json
                sweeprun.error_code = None
                sweeprun.error_text = None
                for botrun in session.query(BotrunRow).filter_by(sweeprun_id=self.sweeprun_id):
                    if botrun.status != "complete":
                        botrun.status = "complete"
                        botrun.results_json = result_json
                        botrun.error_code = None
                        botrun.error_text = None
                session.commit()
            return result
        finally:
            self.engine.dispose()

    async def loop(self) -> dict[str, Any]:
        self._setup()
        if self.config is None or self.bars is None or self.signaler is None or self.executor is None or self.run_log is None:
            raise RuntimeError("sweeprun setup incomplete")
        start_ms = date_ms(self.config.backtest.start)
        stop_ms = date_ms(self.config.backtest.stop)
        warmup = [bar for bar in self.bars if bar.ts_ms < start_ms][-self.signaler.required_bars :]
        if len(warmup) < self.signaler.required_bars:
            raise RuntimeError(f"not enough warmup bars: need={self.signaler.required_bars} got={len(warmup)}")

        self.run_log.info(
            f"sweeprun_start worker={self.worker_name} sweep_id={self.sweep_id} sweeprun_id={self.sweeprun_id} "
            f"symbol={self.config.market.symbol} interval={self.config.market.interval} warmup_bars={len(warmup)}"
        )
        await self.signaler.start(warmup)
        await self.executor.start()

        bars_processed = 0
        entry_signals = 0
        exit_signals = 0
        first_ts = None
        last_ts = None
        last_bar = None
        pending_signal = Signal()
        for bar in self.bars:
            if bar.ts_ms < start_ms or bar.ts_ms > stop_ms:
                continue
            await self.executor.loop_once(bar, pending_signal)
            signal = await self.signaler.loop_once(bar)
            pending_signal = signal
            bars_processed += 1
            first_ts = bar.ts_ms if first_ts is None else first_ts
            last_ts = bar.ts_ms
            last_bar = bar
            if signal.entry:
                entry_signals += 1
            if signal.exit:
                exit_signals += 1
            self.run_log.info(
                f"bar worker={self.worker_name} sweep_id={self.sweep_id} sweeprun_id={self.sweeprun_id} "
                f"ts={format_ms(bar.ts_ms)} data={format_bar(bar)} "
                f"ema_fast={self.signaler.fast_ema} ema_slow={self.signaler.slow_ema} "
                f"entry={str(signal.entry).lower()} exit={str(signal.exit).lower()} reason={signal.reason}"
            )

        await self.executor.stop(last_bar)
        trade_result = asdict(self.executor.result(bars_processed))
        result = {
            "sweep_id": self.sweep_id,
            "sweeprun_id": self.sweeprun_id,
            "worker_name": self.worker_name,
            "status": "complete",
            "bars": bars_processed,
            "warmup_bars": len(warmup),
            "entry_signals": entry_signals,
            "exit_signals": exit_signals,
            "first_ts": first_ts,
            "last_ts": last_ts,
            "log_path": str(self.log_path),
            "tradebot": trade_result,
        }
        self.run_log.info("sweeprun_complete " + json.dumps(result, sort_keys=True))
        return result

    def _setup(self) -> None:
        if self.config is None or self.bot_id is None or self.sweeprun_config is None:
            raise RuntimeError("sweeprun must load before setup")
        if self.engine is None:
            raise RuntimeError("sweeprun engine missing")
        self.id_ctx = IdCtx(
            sweep_id=self.sweep_id,
            sweeprun_id=self.sweeprun_id,
            bot_id=self.bot_id,
            account_id="default",
            bot_config=self.config,
        )
        self.log_path = Path(self.db_path).parent.parent / "logs" / f"sweep_{self.sweep_id}_sweeprun_{self.sweeprun_id}.log"
        self.run_log = logger(str(self.log_path))
        self.bars = load_binance_bars(self.config)
        self.signaler = SignalerEmaCross(self.config.signalers[0])
        if self.config.executor.name != "tradebot":
            raise ValueError(f"sweep supports tradebot only: {self.config.executor.name}")
        self.executor = ExecutorTrade(
            TradeConfig(
                self.config.runtime.bot_id,
                self.config.executor.take_profit_pct,
                self.config.executor.stop_loss_pct,
                self.config.executor.max_cycles,
                self.config.market.symbol,
                "default",
            ),
            self.run_log,
            TradeLedger(self.engine, self.id_ctx),
        )


def run_sweeprun_task(db_path: str, sweep_id: int, sweeprun_id: int, worker_name: str) -> dict[str, Any]:
    try:
        return asyncio.run(Sweeprun(db_path, sweep_id, sweeprun_id, worker_name).run())
    except Exception as exc:
        engine = create_engine(f"sqlite:///{Path(db_path).as_posix()}", future=True, connect_args={"timeout": 30})
        try:
            with Session(engine, expire_on_commit=False) as session:
                sweeprun = session.get(SweeprunRow, sweeprun_id)
                if sweeprun is not None:
                    sweeprun.status = "failed"
                    sweeprun.error_code = "sweeprun_failed"
                    sweeprun.error_text = str(exc)
                for botrun in session.query(BotrunRow).filter_by(sweeprun_id=sweeprun_id):
                    if botrun.status != "complete":
                        botrun.status = "failed"
                        botrun.error_code = "sweeprun_failed"
                        botrun.error_text = str(exc)
                session.commit()
        finally:
            engine.dispose()
        return {"sweep_id": sweep_id, "sweeprun_id": sweeprun_id, "worker_name": worker_name, "status": "failed", "error": str(exc)}
