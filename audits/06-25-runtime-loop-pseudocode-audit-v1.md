# runtime loop pseudocode audit v1

## result

FAIL

## findings

1. High, `nuubot/core/runtime.py:137-142`: the target loop gathers market, signaler, risk, and executor inputs before handling command stop.

   Why it matters: if market snapshot, signaler observation, risk scoring, or executor status blocks/fails, a pending stop command is delayed or missed for that loop.

   Required fix: poll command first and handle hard stop before expensive input reads. Then gather market/signaler/risk/executor inputs.

2. High, `wiki/design/objects/runtime.md:156-169`: exit paths return before end-loop status/heartbeat.

   Why it matters: command/risk/signaler/executor exits can leave the DB/status row stale. Operator sees old state until another path updates it.

   Required fix: exit decisions should set an exit reason, then run end-loop status write/heartbeat once before returning.

3. Medium, `nuubot/core/runtime.py:133-150`: max-loop order is ambiguous and can become off-by-one.

   Why it matters: current working code allows loop `N` to run, then exits at the end when `max_loop=N`. The target pseudocode can exit before processing the final loop depending on implementation.

   Required fix: keep the current rule explicit: pre-check before increment for already exhausted runs, then end-loop `exit_if_max_loop()` after processing.

4. Medium, `wiki/design/objects/runtime.md:160-181`: `bot has started` has no owner.

   Why it matters: if Runtime owns a boolean, it can drift from real orders/positions. Started state should come from Executor/Account/Ledger status.

   Required fix: source started/open state from `Executor.status()` or account/ledger state returned through Executor. Do not add a second runtime flag.

5. Medium, `wiki/design/objects/runtime.md:181-184`: active loop always reaches `submit_orders(...)`.

   Why it matters: after reconcile and stop-loss/order-exit handling, the bot may be exiting, cooling down, waiting for fills, or otherwise not allowed to place new orders.

   Required fix: make order submission conditional on executor decision after reconcile/order-exit handling. Runtime should call the object in sequence; Executor decides whether to place orders.

6. Low, `nuubot/core/runtime.py:137-142`: gathering `risk` and `executor` every loop before knowing whether there is usable signaler/market data may do unnecessary work.

   Why it matters: harmless now, but can become slow when those calls hit DB/exchange/account state.

   Required fix: keep command and clock checks first, get market/signaler next, then call risk/executor only when the phase needs them.

## proof checked

- Read current target pseudocode in `nuubot/core/runtime.py`.
- Read canonical loop text in `wiki/design/objects/runtime.md`.
- Compared against current working `loop_once()` ordering.

## proof missing

- No runtime behavior change was made.
- No rerun needed for this read-only audit.

## assumptions

- Command stop should be responsive even if market/risk/executor work is slow.
- DB/status freshness matters for operator trust.
- Executor will own active/started/order state.

## open questions

- Should command `stop` mean graceful stop after end-loop status write, or immediate abort with best-effort status write?
- Does `started` mean first entry order submitted, first fill received, or open position exists?

## bloat check

Found no need for locks, queues, concurrent gather, or extra state machine yet. Found real logic/order risks: command stop delayed by input gather, exit paths skipping status finalization, max-loop ambiguity, unclear started-state ownership, and unconditional order submission. Keep the fix as ordering and ownership clarification only.
