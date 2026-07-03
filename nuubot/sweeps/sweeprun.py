from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from nuubot.core.data_loader import DataLoader, bars_from_frame
from nuubot.core.dtypes import Bar, BotRunResult, SwData, Timeframe
from nuubot.core.logger import LOG_DIR, logger
from nuubot.core.market_data import date_ms, interval_ms
from nuubot.core.telemetry import pt_now_ts_ms
from nuubot.datastore import AccountRow, BotrunRow, Datastore, EventRow, FillRow, OrderRow, PositionRow, SweeprunRow
from nuubot.sweeps.executors import SwExecutor, create_executor
from nuubot.sweeps.models import SweeprunConfig
from nuubot.sweeps.signalers import SwSignal, SwSignaler, create_signaler

NOOP_LOG = logging.getLogger("nuubot.sweeps.noop")
NOOP_LOG.addHandler(logging.NullHandler())
NOOP_LOG.propagate = False
NOOP_LOG.setLevel(logging.CRITICAL + 1)


@dataclass
class Sweeprun:
    db_path: str
    sweep_id: int
    sweeprun_id: int
    worker_name: str
    config: SweeprunConfig | None = None
    bars: list[Bar] | None = None
    signaler: SwSignaler | None = None
    executor: SwExecutor | None = None
    bot_results: list[BotRunResult] = field(default_factory=list)
    datastore: Datastore = field(default_factory=Datastore)
    run_log: Any | None = None
    log_path: Path | None = None
    timing: dict[str, int] = field(default_factory=dict)
    pt_total_ts_ms: int = 0
    ticks_processed: int = 0
    warmup_bars: int = 0
    entry_signals: int = 0
    exit_signals: int = 0
    last_signal_ts_ms: int = 0
    last_entry_signal_ts_ms: int = 0
    signal_events: list[dict[str, Any]] = field(default_factory=list)
    botrun_ledgers: list[tuple[int, SwExecutor, BotRunResult]] = field(default_factory=list)
    botruns_started: int = 0
    botruns_stopped: int = 0
    bot_ticks_processed: int = 0
    last_bar: Bar | None = None
    start_ms: int = 0
    stop_ms: int = 0

    async def execute(self) -> dict[str, Any]:
        """Run the full process-pool sweeprun lifecycle."""

        # Start runtime.
        await self.start()

        # Run replay.
        await self.loop()

        # Save result.
        return await self.stop()

    async def start(self) -> None:
        """Initialize, validate, and prepare one sweeprun for the event loop."""

        # Start total timer.
        self.pt_total_ts_ms = pt_now_ts_ms()
        pt_start_ts_ms = self.pt_total_ts_ms

        # Load sweeprun row.
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)
            if sweeprun.sweep_id != self.sweep_id:
                raise RuntimeError(f"sweeprun row wrong sweep: {self.sweeprun_id}")
            config_json = sweeprun.config_json
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

        # Validate config.
        config = SweeprunConfig.model_validate(json.loads(config_json))

        # Mark row running.
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)
            sweeprun.status = "running"
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

        # Set runtime values.
        self.config = config

        # Create run log.
        self.log_path = LOG_DIR / f"sweep_{self.sweep_id}_sweeprun_{self.sweeprun_id}.log"
        self.run_log = logger(self.log_path.name)

        # Create signaler.
        pt_signaler_init_ts_ms = pt_now_ts_ms()
        self.signaler = create_signaler(config.signaler, config.executor.symbol)
        self.record_timing_ms("signaler_init", pt_now_ts_ms() - pt_signaler_init_ts_ms)

        # Set active window.
        self.start_ms = date_ms(config.sweeprun.start)
        self.stop_ms = date_ms(config.sweeprun.end)

        # Create data loader.
        pt_load_ts_ms = pt_now_ts_ms()
        loader = DataLoader(config.sweeprun.data_dir)
        replay_timeframe = Timeframe.M1
        replay_data = SwData(
            "replay",
            config.executor.symbol,
            replay_timeframe,
            0,
            interval_ms(replay_timeframe.value) * 2,
            self.start_ms,
            self.stop_ms,
            pl.DataFrame(),
        )

        # Load replay bars.
        replay_data.frame = loader.load(replay_data)
        self.bars = bars_from_frame(replay_data.frame.filter(pl.col("is_active")))
        self.record_timing_ms("load", pt_now_ts_ms() - pt_load_ts_ms)

        self.run_log.info(
            f"sweeprun_start worker={self.worker_name} sweep_id={self.sweep_id} sweeprun_id={self.sweeprun_id} "
            f"symbol={config.executor.symbol} interval={config.executor.interval}"
        )

        # Start signaler.
        pt_signaler_start_ts_ms = pt_now_ts_ms()
        self.signaler.start()
        self.record_timing_ms("signaler_start", pt_now_ts_ms() - pt_signaler_start_ts_ms)

        # Load signaler data.
        pt_signaler_load_ts_ms = pt_now_ts_ms()
        self.signaler.load(loader, self.start_ms, self.stop_ms)
        self.warmup_bars = self.signaler.warmup_bars
        self.record_timing_ms("signaler_load", pt_now_ts_ms() - pt_signaler_load_ts_ms)

        # Calculate signaler data.
        pt_signaler_calc_ts_ms = pt_now_ts_ms()
        self.signaler.calc()
        self.record_timing_ms("signaler_calc", pt_now_ts_ms() - pt_signaler_calc_ts_ms)

        # Record start timing.
        self.record_timing_ms("start", pt_now_ts_ms() - pt_start_ts_ms)

    async def loop(self) -> None:
        """Prepare the active window and execute one pass per event."""

        # Require runtime values.
        if self.config is None or self.bars is None or self.signaler is None or self.run_log is None:
            raise RuntimeError("sweeprun setup incomplete")

        # Run active events.
        pt_loop_ts_ms = pt_now_ts_ms()
        for bar in self.bars:
            if bar.ts_ms < self.start_ms or bar.ts_ms > self.stop_ms:
                continue
            for tick in _synthetic_ticks(bar):
                await self.next(tick)

        # Record loop timing.
        self.record_timing_ms("loop", pt_now_ts_ms() - pt_loop_ts_ms)

    async def stop(self) -> dict[str, Any]:
        """Stop execution, calculate results, and persist final sweeprun state."""

        # Stop signaler.
        pt_signaler_stop_ts_ms = pt_now_ts_ms()
        self.signaler.stop()
        self.record_timing_ms("signaler_stop", pt_now_ts_ms() - pt_signaler_stop_ts_ms)

        # Stop active bot.
        pt_stop_ts_ms = pt_now_ts_ms()
        if self.executor is not None:
            await self._stop_active_bot(self.last_bar)
        trade_result = asdict(self._result())

        # Record stop timing.
        self.record_timing_ms("stop", pt_now_ts_ms() - pt_stop_ts_ms)
        if self.pt_total_ts_ms:
            self.record_timing_ms("total", pt_now_ts_ms() - self.pt_total_ts_ms)

        # Collect telemetry.
        telemetry = {
            "replay_bars": len(self.bars or []),
            "ticks": self.ticks_processed,
            "warmup_bars": self.warmup_bars,
            "savedb": self.config.sweeprun.savedb,
            "entry_signals": self.entry_signals,
            "exit_signals": self.exit_signals,
            "signal_events": len(self.signal_events),
            "botruns_started": self.botruns_started,
            "botruns_stopped": self.botruns_stopped,
            "executor": self._executor_telemetry(),
            "timing": self.timing,
        }

        # Compose result payload.
        result = {
            "sweep_id": self.sweep_id,
            "sweeprun_id": self.sweeprun_id,
            "worker_name": self.worker_name,
            "status": "complete",
            "performance": trade_result,
            "telemetry": telemetry,
            "replay_bars": len(self.bars or []),
            "ticks": self.ticks_processed,
            "warmup_bars": self.warmup_bars,
            "savedb": self.config.sweeprun.savedb,
            "entry_signals": self.entry_signals,
            "exit_signals": self.exit_signals,
            "signal_events": len(self.signal_events),
            "botruns_started": self.botruns_started,
            "botruns_stopped": self.botruns_stopped,
            "log_path": str(self.log_path),
            "tradebot": trade_result,
        }

        # Log result.
        self.run_log.info("sweeprun_complete " + json.dumps(result, sort_keys=True))

        # Persist result.
        self._save_result(result)
        return result

    # Helpers

    async def next(self, event: Bar) -> None:
        """Process one ordered event. Today it is a bar; later it may be a tick."""

        # Require runtime values.
        if self.signaler is None:
            raise RuntimeError("sweeprun must be started before next")

        # Check signal.
        pt_signaler_check_ts_ms = pt_now_ts_ms()
        current_ts_ms = event.ts_ms
        signal = self.signaler.check(current_ts_ms)
        self.record_timing_ms("signaler_check", pt_now_ts_ms() - pt_signaler_check_ts_ms)

        # Update counters.
        self.ticks_processed += 1
        self.last_bar = event
        signal = self._dedupe_signal(signal)
        if signal.enter_long or signal.enter_short:
            self.entry_signals += 1
        if signal.exit_long or signal.exit_short:
            self.exit_signals += 1
        if signal.reason and self.config.sweeprun.savedb:
            self._record_signal(event, signal)

        # Start bot.
        if self.executor is None and (signal.enter_long or signal.enter_short):
            await self._start_active_bot()

        # Feed active bot.
        if self.executor is not None:
            pt_executor_next_ts_ms = pt_now_ts_ms()
            await self.executor.next(event, signal, self.config.risk.score)
            self.bot_ticks_processed += 1
            self.record_timing_ms("executor_next", pt_now_ts_ms() - pt_executor_next_ts_ms)

        # Clear stopped bot.
        if self.executor is not None and self.executor.status == "stopped":
            await self._stop_active_bot(event)

    def _dedupe_signal(self, signal: SwSignal) -> SwSignal:
        # Use each closed signal bar once.
        if not signal.reason:
            return signal
        if signal.signal_ts_ms == self.last_signal_ts_ms:
            return SwSignal()
        self.last_signal_ts_ms = signal.signal_ts_ms
        if signal.enter_long or signal.enter_short:
            if signal.signal_ts_ms == self.last_entry_signal_ts_ms:
                return SwSignal()
            self.last_entry_signal_ts_ms = signal.signal_ts_ms
        return signal

    def record_timing_ms(self, key: str, ms: int) -> None:
        key = f"timing_{key}_ms"
        self.timing[key] = self.timing.get(key, 0) + ms

    async def _start_active_bot(self) -> None:
        # Create active bot.
        pt_executor_init_ts_ms = pt_now_ts_ms()
        self.executor = create_executor(self.sweeprun_id, self.config.executor, self.run_log, self.config.sweeprun)
        await self.executor.init()
        self.record_timing_ms("executor_init", pt_now_ts_ms() - pt_executor_init_ts_ms)

        # Start active bot.
        pt_executor_start_ts_ms = pt_now_ts_ms()
        await self.executor.start()
        self.botruns_started += 1
        self.bot_ticks_processed = 0
        self.record_timing_ms("executor_start", pt_now_ts_ms() - pt_executor_start_ts_ms)

    async def _stop_active_bot(self, event: Bar | None) -> None:
        # Stop active bot.
        pt_executor_stop_ts_ms = pt_now_ts_ms()
        result = await self.executor.stop(event, self.bot_ticks_processed)
        self.bot_results.append(result)
        if self.config.sweeprun.savedb:
            self.botrun_ledgers.append((self.botruns_stopped + 1, self.executor, result))
        self.executor = None
        self.botruns_stopped += 1
        self.bot_ticks_processed = 0
        self.record_timing_ms("executor_stop", pt_now_ts_ms() - pt_executor_stop_ts_ms)

    def _result(self) -> BotRunResult:
        # Aggregate bot results.
        return BotRunResult(
            config_id=self.sweeprun_id,
            pnl_pct=sum(result.pnl_pct for result in self.bot_results),
            wins=sum(result.wins for result in self.bot_results),
            losses=sum(result.losses for result in self.bot_results),
            trades=sum(result.trades for result in self.bot_results),
            max_drawdown_pct=max((result.max_drawdown_pct for result in self.bot_results), default=0.0),
            ticks=self.ticks_processed,
            cycles=sum(result.cycles for result in self.bot_results),
        )

    def _executor_telemetry(self) -> dict[str, Any]:
        # Report bot telemetry.
        result = self._result()
        telemetry = asdict(result)
        telemetry["active"] = self.executor is not None
        telemetry["status"] = self.executor.status if self.executor is not None else "stopped"
        telemetry["botruns_started"] = self.botruns_started
        telemetry["botruns_stopped"] = self.botruns_stopped
        return telemetry

    def _save_result(self, result: dict[str, Any]) -> None:
        """Persist final sweeprun result."""

        # Serialize result payload.
        result_json = json.dumps(result, sort_keys=True, separators=(",", ":"))

        # Update sweeprun row.
        tx = self.datastore.tx(Path(self.db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=self.sweeprun_id)
            sweeprun.status = "complete"
            sweeprun.results_json = result_json
            sweeprun.error_code = None
            sweeprun.error_text = None

            # Save signal events.
            for signal_event in self.signal_events:
                tx.insert(
                    EventRow(
                        event_ts=signal_event["event_ts"],
                        level="info",
                        event="signal",
                        message=signal_event["reason"],
                        data_json=json.dumps(signal_event, sort_keys=True, separators=(",", ":")),
                    )
                )
            for botrun_index, executor, botrun_result in self.botrun_ledgers:
                self._save_botrun_ledger(tx, botrun_index, executor, botrun_result)

            # Update actual botrun rows.
            for botrun in tx.select(BotrunRow, sweeprun_id=self.sweeprun_id):
                if botrun.status != "complete":
                    botrun.status = "complete"
                    botrun.results_json = result_json
                    botrun.error_code = None
                    botrun.error_text = None

            # Commit result.
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()

    def _record_signal(self, event: Bar, signal: Any) -> None:
        # Store signaler output.
        if self.config is None:
            raise RuntimeError("sweeprun config missing")
        self.signal_events.append(
            {
                "event_ts": event.ts_ms,
                "sweep_id": self.sweep_id,
                "sweeprun_id": self.sweeprun_id,
                "symbol": self.config.executor.symbol,
                "interval": self.config.signaler.interval,
                "signaler": self.config.signaler.name,
                "reason": signal.reason,
                "signal_ts_ms": signal.signal_ts_ms,
                "enter_long": signal.enter_long,
                "enter_short": signal.enter_short,
                "exit_long": signal.exit_long,
                "exit_short": signal.exit_short,
                "open": event.open,
                "high": event.high,
                "low": event.low,
                "close": event.close,
            }
        )

    def _save_botrun_ledger(self, tx: Any, botrun_index: int, executor: SwExecutor, result: BotRunResult) -> None:
        """Persist one stopped bot's account ledger."""

        # Find ledger.
        if self.config is None:
            raise RuntimeError("sweeprun config missing")
        account = getattr(executor, "account", None)
        if account is None:
            return

        # Build botrun identity.
        bot_id = self.sweeprun_id * 1_000_000 + botrun_index
        acct_id = self.config.executor.account
        result_json = json.dumps(asdict(result), sort_keys=True, separators=(",", ":"))
        config_json = json.dumps(self.config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

        # Save ledger rows.
        tx.upsert(AccountRow(acct_id=acct_id, bot_id=bot_id, role="trade", name=acct_id, exec_network="sweep", status="active"))
        botrun = tx.insert(BotrunRow(sweeprun_id=self.sweeprun_id, bot_id=bot_id, botrun_index=botrun_index, config_json=config_json, results_json=result_json, status="complete"))
        for position in account.ledger.positions:
            db_position_id = bot_id * 1_000 + position.position_id
            position.recalc()
            entry_orders = [order for order in position.orders if not order.reduce_only]
            exit_orders = [order for order in position.orders if order.reduce_only]
            filled_exit_orders = [order for order in exit_orders if order.filled_size > 0]
            entry_order = entry_orders[0] if entry_orders else None
            exit_order = filled_exit_orders[-1] if filled_exit_orders else None
            fill_times = [fill.ts_ms for order in position.orders for fill in order.fills]
            entry_cash = sum((abs(order.signed_cash()) for order in entry_orders), start=position.net_size * 0)
            exit_cash = sum((abs(order.signed_cash()) for order in exit_orders), start=position.net_size * 0)
            entry_fee = sum((order.fee for order in entry_orders), start=position.net_size * 0)
            exit_fee = sum((order.fee for order in exit_orders), start=position.net_size * 0)
            db_position = tx.insert(
                PositionRow(
                    position_id=db_position_id,
                    sweep_id=self.sweep_id,
                    sweeprun_id=self.sweeprun_id,
                    bot_id=bot_id,
                    botrun_id=botrun.botrun_id,
                    acct_id=acct_id,
                    symbol=position.symbol,
                    status=position.status,
                    side=("long" if entry_order and entry_order.side == "buy" else "short" if entry_order else None),
                    current_sz=str(position.net_size),
                    max_abs_sz=str(_max_abs_size(position.orders)),
                    avg_entry_px=str(entry_order.avg_fill_price) if entry_order else None,
                    avg_exit_px=str(exit_order.avg_fill_price) if exit_order else None,
                    mark_px=str((exit_order or entry_order).avg_fill_price) if (exit_order or entry_order) else None,
                    entry_cash=str(entry_cash),
                    exit_cash=str(exit_cash),
                    open_entry_cash="0" if position.status == "closed" else str(entry_cash),
                    entry_fee=str(entry_fee),
                    exit_fee=str(exit_fee),
                    total_fee=str(entry_fee + exit_fee),
                    gross_pnl=str(position.pnl()),
                    realized_pnl=str(position.pnl() if position.status == "closed" else 0),
                    unrealized_pnl="0",
                    net_pnl=str(position.pnl()),
                    opened_ts=min(fill_times) if fill_times else None,
                    closed_ts=max(fill_times) if position.status == "closed" and fill_times else None,
                    last_update_ts=max(fill_times) if fill_times else 0,
                    exit_reason=exit_order.role if exit_order else None,
                )
            )
            for order_index, order in enumerate(position.orders, start=1):
                db_order_id = db_position.position_id * 100 + order_index
                fill_times = [fill.ts_ms for fill in order.fills]
                db_order = tx.insert(
                    OrderRow(
                        order_id=db_order_id,
                        oid=order.oid,
                        cloid=order.cloid,
                        sweep_id=self.sweep_id,
                        sweeprun_id=self.sweeprun_id,
                        bot_id=bot_id,
                        botrun_id=botrun.botrun_id,
                        position_id=db_position.position_id,
                        acct_id=acct_id,
                        submit_cloid=order.cloid,
                        submit_ts=min(fill_times) if fill_times else 0,
                        submit_coin=order.symbol,
                        submit_side=order.side,
                        submit_quantity=str(order.size),
                            submit_price=str(order.price),
                            submit_reduceonly=order.reduce_only,
                            submit_type=order.kind,
                            submit_trigger_price=str(order.trigger_price) if order.trigger_price is not None else None,
                            submit_tpsl=order.tpsl or None,
                            submit_parent_cloid=order.parent_cloid or None,
                        status=order.status,
                        exchange_status=order.exchange_status or None,
                        terminal_reason=order.terminal_reason or None,
                        filled_quantity=str(order.filled_size),
                        remaining_quantity=str(order.remaining_size) if order.remaining_size is not None else None,
                        avg_fill_price=str(order.avg_fill_price),
                        fee=str(order.fee),
                        fill_count=len(order.fills),
                        first_fill_ts=min(fill_times) if fill_times else None,
                        last_fill_ts=max(fill_times) if fill_times else None,
                        raw_json="{}",
                    )
                )
                for fill_index, fill in enumerate(order.fills, start=1):
                    tx.insert(
                        FillRow(
                            fill_id=db_order.order_id * 100 + fill_index,
                            oid=fill.oid,
                            cloid=fill.cloid,
                            sweep_id=self.sweep_id,
                            sweeprun_id=self.sweeprun_id,
                            bot_id=bot_id,
                            botrun_id=botrun.botrun_id,
                            order_id=db_order.order_id,
                            acct_id=acct_id,
                            coin=order.symbol,
                            side=fill.side,
                            px=str(fill.price),
                            sz=str(fill.size),
                            time=fill.ts_ms,
                            fee=str(fill.fee),
                            closedPnl=str(position.pnl()) if order.reduce_only else None,
                            raw_json=json.dumps(fill.raw, sort_keys=True, separators=(",", ":")),
                        )
                    )


def run_sweeprun(db_path: str, sweep_id: int, sweeprun_id: int, worker_name: str) -> dict[str, Any]:
    """Sweeprun process-pool entry point for one sweeprun."""

    try:
        # Create sweeprun.
        sweeprun = Sweeprun(db_path, sweep_id, sweeprun_id, worker_name)

        # Run worker.
        return asyncio.run(sweeprun.execute())
    except Exception as exc:
        # Save worker failure.
        datastore = Datastore()
        tx = datastore.tx(Path(db_path))
        tx.start()
        try:
            sweeprun = tx.get(SweeprunRow, sweeprun_id=sweeprun_id)
            sweeprun.status = "failed"
            sweeprun.error_code = "sweeprun_failed"
            sweeprun.error_text = str(exc)
            for botrun in tx.select(BotrunRow, sweeprun_id=sweeprun_id):
                if botrun.status != "complete":
                    botrun.status = "failed"
                    botrun.error_code = "sweeprun_failed"
                    botrun.error_text = str(exc)
            tx.commit()
        except Exception:
            tx.rollback()
            raise
        finally:
            tx.close()
        return {"sweep_id": sweep_id, "sweeprun_id": sweeprun_id, "worker_name": worker_name, "status": "failed", "error": str(exc)}


def _max_abs_size(orders: list[Any]) -> Any:
    # Calculate peak exposure.
    current = orders[0].filled_size * 0 if orders else 0
    peak = current
    for order in orders:
        current += order.signed_size()
        peak = max(peak, abs(current))
    return peak


def _synthetic_ticks(bar: Bar) -> list[Bar]:
    # Replay a deterministic intrabar price path.
    if bar.close >= bar.open:
        path = [bar.open, bar.high, bar.low, bar.close]
    else:
        path = [bar.open, bar.low, bar.high, bar.close]
    offsets = [0, 20_000, 40_000, 59_999]
    return [Bar(bar.ts_ms + offset, price, price, price, price, 0.0, bar.closed, price, price) for offset, price in zip(offsets, path, strict=True)]
