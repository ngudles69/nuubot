# Sweeprun Design Scratchpad

This file is an independent working design note. Nothing should import it or
link to it.

Use this as the fast design scratchpad before coding. Keep it small: object
fit, key methods, simple signatures, and intent comments.

Risk is skipped for now. Until it is designed, `risk_score` is just an input to
the executor path.

## Current Code

Implemented today:

1. `nuubot/sweeps/sweeprun.py`
   - `Sweeprun`
   - `run_sweeprun()`
2. `nuubot/sweeps/signalers/signaler.py`
   - `SwSignal`
   - `SwSignaler`
   - `create_signaler()`
3. `nuubot/sweeps/signalers/swemacross.py`
   - `SwEmacross`
4. `nuubot/sweeps/executors/executor.py`
   - `SwExecutor`
   - `create_executor()`
5. `nuubot/sweeps/executors/swtradebot.py`
   - `SwTradeBot`
6. `nuubot/account/`
   - `TradingAccount`
   - `TradeLedger`
   - `TradePosition`
   - `Order`
   - `Fill`
7. `nuubot/exchange/simulator.py`
   - `Simulator`

Still deferred:

- durable ledger save/load.
- live Hyperliquid adapter.
- simulator persistence.
- bounded recon windows for speed.
- `risk.py`
    - skipped for now

## Target Loop

Current `sweeprun.py` loop:

```text
for event in replay:
  signal = signaler.check(event.ts_ms)
  executor.next(event, signal, config.risk.score)
```

Current account-aware loop:

```text
for tick in replay:
  signal = signaler.check(tick.ts_ms)
  await executor.next(tick, signal, config.risk.score)
```

`SwTradeBot.next()` owns account `ingest_bbo()` and throttled `recon()` for its
single configured account. Do not add a multi-account protocol until a real
executor needs it.

Signal timing is fixed. A signal is stored on the OHLCV row whose close
created it. `signaler.check(current_ts_ms)` receives the current decision
timestamp in milliseconds, not a precomputed prior-row timestamp. Each signaler
dataset finds its own latest closed signal row at that time. For example: 1h
reads the hour bar that just closed, 4h reads the latest closed 4h block, and
1d reads the latest closed day.

`Sweeprun` owns replay, timing, DB status, and result persistence. It does not
own strategy decisions, signal delay rules, execution timing, order matching,
or ledger mutation rules.

## 1. `sweeprun.py`

Matches current code. Assume replay feeds tick/BBO events; do not add a bar
compatibility layer unless code still needs it during implementation.

```python
class Sweeprun:
    async def execute(self) -> dict:
        # Start runtime.
        await self.start()

        # Run replay.
        await self.loop()

        # Save result.
        return await self.stop()

    async def start(self) -> None:
        # Start total timer.
        # Load sweeprun row.
        # Validate config.
        # Mark row running.
        # Set runtime values.
        # Create run log.
        # Create signaler.
        # Create executor.
        self.executor = create_executor(...)

        # Initialize executor.
        await self.executor.init()

        # Set active window.
        # Create data loader.
        # Load replay bars.
        # Log start.
        # Start signaler.
        # Load signaler data.
        # Calculate signaler data.
        # Start executor.
        await self.executor.start()

        # Record start timing.

    async def loop(self) -> None:
        # Require runtime values.
        # Run active events.
        for event in self.events:
            await self.next(event)

        # Record loop timing.

    async def stop(self) -> dict:
        # Stop signaler.
        # Stop executor.
        result = await self.executor.stop(self.last_event, self.events_processed)

        # Record stop timing.
        # Collect telemetry.
        telemetry = self.executor.telemetry()

        # Compose result payload.
        # Log result.
        # Persist result.

    async def next(self, tick: object) -> None:
        # Require runtime values.

        # Check signal.
        signal = self.signaler.check(tick.ts_ms)

        # Run executor.
        await self.executor.next(tick, signal, self.config.risk.score)

        # Update counters.

    def record_timing_ms(self, key: str, ms: int) -> None:
        # Add timing.

    def _save_result(self, result: dict) -> None:
        # Serialize result payload.
        # Update sweeprun row.
        # Update actual botrun rows.
        # Commit result.


def run_sweeprun(db_path: str, sweep_id: int, sweeprun_id: int, worker_name: str) -> dict:
    # Create sweeprun.
    # Run worker.
    # Save worker failure.
```

## 2. `signalers/signaler.py`

Current code is complete but should use the same short intent-comment shape as
`sweeprun.py` when edited.

```python
class SwSignal:
    # Carry signal intent.
    enter_long: bool
    enter_short: bool
    exit_long: bool
    exit_short: bool
    reason: str


class SwSignaler(Protocol):
    # Report warmup loaded for telemetry.
    warmup_bars: int

    def init(self, config: SignalerConfig, symbol: str) -> None: ...
    def start(self) -> None: ...
    def load(self, loader: DataLoader, start_ms: int, stop_ms: int) -> None: ...
    def calc(self) -> None: ...
    def check(self, current_ts_ms: int) -> SwSignal: ...
    def stop(self) -> None: ...


def create_signaler(config: SignalerConfig, symbol: str) -> SwSignaler:
    # Select signaler.
    # Initialize signaler.
    # Reject unsupported signaler.
```

Signaler owns signal-intent data and no-lookahead timing. Signals stay on the
OHLCV row whose close created them. `check(current_ts_ms)` receives the current
decision timestamp in milliseconds and reads the latest closed signal row for
each timeframe.

`Sweeprun` must not inspect `signaler.data`, signaler internals, or how the
signal row is selected.

## 3. `signalers/swemacross.py`

Current code mostly follows this shape. `__init__`, `start()`, and `stop()` are
still sparse/no-op code and should get short intent comments when the Python
file is edited.

```python
class SwEmacross:
    def __init__(self) -> None:
        # Set defaults.
        # Setup cache.

    def init(self, config: SignalerConfig, symbol: str) -> None:
        # Validate config.
        # Validate timeframe.
        # Validate EMA periods.
        # Set values.
        # Setup data requirements.
        # Setup cache.

    def start(self) -> None:
        # Start signaler.

    def load(self, loader: DataLoader, start_ms: int, stop_ms: int) -> None:
        # Determine warmup window.
        # Load crossover data.
        # Validate crossover data.

    def calc(self) -> None:
        # Validate loaded frame.
        # Calculate the full crossover dataset.
        # Calculate cross columns.
        # Store calculated frame.
        # Cache signal rows for fast checks.

    def check(self, current_ts_ms: int) -> SwSignal:
        # Normalize check time.
        # Validate calculated frame.
        # Select latest calculated signal.
        # Return signal.

    def stop(self) -> None:
        # Stop signaler.
```

`SwEmacross` is the sample signaler. Use it to sharpen the protocol, not to add
generic signaler framework.

## 4. `executors/executor.py`

Current shape.

```python
class SwExecutor:
    status: str

    async def init(self) -> None:
        # Validate config.
        # Set values.

    async def start(self) -> None:
        # Start executor.

    async def next(self, event: object, signal: SwSignal, risk_score: int) -> None:
        # Run executor step.

    async def stop(self, event: object | None, ticks: int) -> BotRunResult:
        # Stop executor.
        # Return result.

    def telemetry(self) -> dict:
        # Report telemetry.


def create_executor(config_id: int, config: Any, run_log: Any) -> SwExecutor:
    # Select executor.
    # Build executor config.
    # Use executor account.

    # Create executor.
    executor = SwTradeBot(...)

    # Return executor.
    return executor

    # Reject unsupported executor.
```

## 5. `executors/swtradebot.py`

Current code uses `TradingAccount` as the execution/account boundary.
`SwTradeBot` creates position/order intent, submits through account methods,
and relies on `account.recon()` to apply exchange or simulator evidence.

```python
class SwTradeBot:
    def __init__(self, config: TradeConfig, run_log: Any, account: TradingAccount | None = None) -> None:
        # Set config.
        # Set account.
        # Set trade state.
        # Set counters.
        # Set risk state.

    async def init(self) -> None:
        # Validate config.
        # Init account.

    async def start(self) -> None:
        # Mark started.

    async def next(self, event: object, signal: SwSignal, risk_score: int) -> None:
        # Validate risk.
        # Exit active trade.
        # Enter new trade.

    async def stop(self, event: object | None, ticks: int) -> BotRunResult:
        # Close active trade.
        # Build result.

    async def exit(self) -> bool:
        # Report exit state.

    def telemetry(self) -> dict:
        # Report telemetry.
```

Current account-aware shape:

```python
class SwTradeBot:
    def __init__(self, config: TradeConfig, run_log: Any, account: TradingAccount | None = None) -> None:
        # Set config.
        # Set log.
        # Set account.
        # Set trade state.
        # Set counters.

    async def init(self) -> None:
        # Validate config.
        # Init account.

    async def start(self) -> None:
        # Mark started.

    async def next(self, event: object, signal: SwSignal, risk_score: int) -> None:
        # Validate risk.
        # Ingest BBO into account.
        # Run throttled account recon.
        # Sync position state.
        # Check exits.
        # Check entries.
        # Send order intent through account.
        # Update telemetry.

    async def stop(self, event: object | None, ticks: int) -> BotRunResult:
        # Run pre-close recon.
        # Submit market close if still open.
        # Close result.
```

For TradeBot specifically:

```text
entry signal -> account.place_orders(entry intent)
exit signal -> account.place_orders(reduce-only exit intent)
take profit -> account.place_orders(reduce-only exit intent)
stop loss -> account.place_orders(reduce-only exit intent)
account.recon() -> Ledger applies fills -> SwTradeBot syncs active state
```

TradeBot creates position and order intent, then submits it through
`TradingAccount`. Fills remain exchange evidence and are created by simulator or
live recon only.

## 6. `account.py`

Reference: `nuutrader6` uses `TradingAccount` as the boundary that owns exchange
I/O plus one `TradeLedger`. For this repo, keep the same ownership but smaller.

```python
class ReconResult:
    # Report recon outcome.
    summary: Any
    fills_applied: int
    order_updates_applied: int
    open_orders_seen: int
    fills_seen: int
    recon_ok: bool


class TradingAccount:
    def __init__(self, ledger: TradeLedger, simulator: Simulator) -> None:
        # Set ledger.
        # Set simulator.

    def init(self) -> None:
        # Start account.

    def close(self) -> None:
        # Close account.

    def ingest_bbo(self, tick: object) -> None:
        # Feed market tick.
        # Record simulator fills.

    def place_position(self, position: TradePosition, ts_ms: int) -> list[OrderResult]:
        # Place all position orders.

    def place_orders(self, orders: list[Order], ts_ms: int) -> list[OrderResult]:
        # Submit orders.
        # Record fills before terminal status.
        # Update order status.

    def cancel_orders(self, orders: list[Order]) -> list[CancelResult]:
        # Cancel open orders.
        # Update order status.

    def close_positions(self, positions: list[TradePosition], price: Decimal, ts_ms: int, reason: str) -> None:
        # Cancel active child orders.
        # Submit cleanup orders.

    def recon(self, ts_ms: int, reason: str) -> ReconResult:
        # Pull needed evidence.
        # Record fills before terminal status.
        # Apply order updates.
        # Return summary.

    def set_leverage(self, leverage: int) -> Any:
        # Set exchange or simulator leverage.

    def leverage(self) -> Any:
        # Read current leverage.

    def balance(self) -> Any:
        # Read account balance.
```

`TradingAccount` owns execution behavior and one ledger. It is one Hyperliquid
account. Unsupported trading calls must fail loud or return explicit
unsupported results. Silent no-ops are not allowed for trading actions.

Sweep/backtest can immediate-fill through simulator, but it still routes
evidence through `TradingAccount` and `Ledger` so executor-facing code stays
the same as live.

## 7. `ledger.py`

Reference: `nuutrader6` `TradeLedger` is broad. Keep the same hierarchy and
evidence rules, but do not bring over the full surface until code needs it.

```python
class TradeLedger:
    def __init__(self) -> None:
        # Set collections.
        # Set next position id.

    def init(self) -> None:
        # Load ledger.

    def close(self) -> None:
        # Save ledger.

    def load(self) -> None:
        # Load positions.

    def save(self) -> None:
        # Save positions.
        # Save ledger metrics.

    def create_position(self, symbol: str) -> TradePosition:
        # Create position.

    def position(self, position_id: int) -> TradePosition:
        # Find position or fail.

    def open_positions(self) -> list[TradePosition]:
        # Return non-terminal positions.

    def open_orders(self) -> list[tuple[TradePosition, Order]]:
        # Return non-terminal orders under non-terminal positions.

    def find_open_order(self, *, cloid: str = "", oid: int | None = None) -> tuple[TradePosition, Order] | None:
        # Find open order.

    def update_orders(self, updates: list[OrderUpdate]) -> set[int]:
        # Update open orders.
        # Return changed position ids.

    def record_fills(self, fills: list[Fill]) -> tuple[set[int], int]:
        # Record fills on open orders.
        # Return changed position ids and recorded fill count.

    def recalc(self, position_ids: set[int]) -> None:
        # Recalculate changed positions.

    def save_changed(self) -> None:
        # Save changed positions.

    def state(self) -> LedgerState:
        # Calculate ledger metrics.

    def pnl(self) -> Decimal:
        # Return closed-position PnL.
```

Ledger owns positions, orders, fills, and PnL. It should not call exchange,
simulator, signaler, or executor.

## 8. `position.py`

Reference: `nuutrader6` `Position` owns accounting for fills and mark price.

```python
class TradePosition:
    def __init__(self, position_id: int, symbol: str) -> None:
        # Set identity.
        # Set orders.
        # Set accounting fields.

    def init(self) -> None:
        # Validate position.

    def close(self) -> None:
        # Close flat position.

    def load(self) -> None:
        # Load position.

    def save(self) -> None:
        # Save position.

    def add_order(self, order: Order) -> None:
        # Attach order.

    def open_orders(self) -> list[Order]:
        # Return non-terminal orders.

    def find_open_order(self, *, cloid: str = "", oid: int | None = None) -> Order | None:
        # Find open order.

    def update_order(self, update: OrderUpdate) -> bool:
        # Update open order.

    def record_fill(self, fill: Fill) -> bool:
        # Record fill on open order.

    def recalc(self) -> None:
        # Recalculate size, PnL, and status.

    def state(self) -> PositionState:
        # Report state.

    def pnl(self) -> Decimal:
        # Return position PnL.

    def is_open(self) -> bool:
        # Report normal recon eligibility.

    def terminal(self) -> bool:
        # Report terminal status.
```

Position owns position accounting only.

## 9. `order.py`

Reference: `nuutrader6` `Order` carries local intent plus exchange state.

```python
class Order:
    def __init__(self) -> None:
        # Set submitted request.
        # Set exchange state.
        # Set fills.

    def init(self) -> None:
        # Validate order.
        # Require cloid before submit.

    def close(self) -> None:
        # Mark closed.

    def update(self, update: OrderUpdate) -> bool:
        # Update open order status.

    def record_fill(self, fill: Fill) -> bool:
        # Skip duplicate fill.
        # Update filled size.
        # Update average fill price.
        # Update fees.

    def recalc(self) -> None:
        # Recalculate remaining size and terminal state.

    def signed_size(self) -> Decimal:
        # Return signed filled size.

    def signed_cash(self) -> Decimal:
        # Return signed cash.

    def is_open(self) -> bool:
        # Report normal recon eligibility.

    def terminal(self) -> bool:
        # Report terminal status.
```

Order owns order state only. It does not update position PnL directly.

## 10. `fill.py`

Reference: `nuutrader6` simulator and recon both normalize fills into one fill
shape before Ledger sees them.

```python
class Fill:
    def __init__(self) -> None:
        # Set exchange ids and order ids.
        # Set price and size.
        # Set fee.
        # Set raw evidence.

    def init(self) -> None:
        # Validate fill.
        # Require stable fill key.

    def key(self) -> str:
        # Return dedupe key.
```

Fill is execution evidence. It should be immutable after validation.

## 11. `simulator.py`

Reference: `nuutrader6` simulator accepts order intents, ingests market ticks,
matches orders, records fills, exposes exchange-like reads, and persists
restart state. For sweep, start smaller and in-memory unless durable simulator
state is proven necessary.

```python
class Simulator:
    def __init__(self) -> None:
        # Set open orders.
        # Set fills.
        # Set leverage.

    def init(self) -> None:
        # Validate simulator settings.

    def close(self) -> None:
        # Close simulator.

    def ingest_bbo(self, tick: object) -> list[Fill]:
        # Ingest tick.
        # Match resting orders.
        # Match trigger orders.
        # Cancel invalid reduce-only orders.
        # Create fills.
        # Update simulator position.
        # Return fills.

    def place_orders(self, orders: list[Order], ts_ms: int) -> list[OrderResult]:
        # Submit orders.
        # Fill market orders immediately.
        # Store nonmarket orders.

    def cancel_orders(self, orders: list[Order]) -> list[CancelResult]:
        # Cancel orders.

    def open_orders(self) -> list[Order]:
        # Read open simulated orders.

    def fills(self) -> list[Fill]:
        # Read simulated fills.

    def set_leverage(self, leverage: int) -> int:
        # Set leverage.

    def leverage(self) -> int:
        # Read leverage.

    def balance(self) -> dict:
        # Read balance.
```

Simulator owns matching behavior only. `TradingAccount` owns when simulator
evidence is applied to Ledger.

## 12. `recon.py`

Reference: `nuutrader6` recon pulls bounded fills, open orders, builds order
updates, applies fills, and returns a diagnostic summary. Keep that flow, but
do not copy the wide helper set until the current `TradingAccount` needs it.

```python
async def recon_account(
    account: TradingAccount,
    observed_at_ms: int,
    reason: str,
) -> ReconResult:
    # Read latest fill checkpoint.
    # Pull bounded fill history.
    # Deduplicate fills.
    # Pull open orders.
    # Filter rows for account symbol.
    # Build order status updates.
    # Apply order updates.
    # Apply fills.
    # Build summary.
    # Clear dirty state.
    # Return result.


def build_order_updates(
    ledger: Ledger,
    open_orders: list[OrderEvidence],
    fills: list[Fill],
    symbol: str,
) -> list[OrderUpdate]:
    # Read non-terminal ledger orders.
    # Mark seen open orders.
    # Infer filled orders from fills.
    # Infer canceled orders only when safe.
    # Return updates.
```

Recon only what the bot needs. Do not recon the entire exchange account
before every decision.

## 13. `risk.py`

Skipped for now.

Keep the current `risk_score` input in executor signatures so the future risk
path has a place to connect without designing it now.
