# loop proof audit v1

## result

FAIL

## findings

1. Medium, `nuubot/runtime.py`: invalid `mode` silently falls into `BacktestData`.

   Why it matters: a typo in config can run the wrong runtime path instead of
   failing loud.

   Required fix: explicitly branch `papertest` and `backtest`; raise
   `ValueError` for anything else.

2. Medium, `nuubot/runtime.py`: websocket listener task failure is not checked
   during the loop.

   Why it matters: papertest can keep looping on stale or empty data after the
   feed dies, making proof misleading.

   Required fix: in `snapshot()`, if `_task.done()`, call `_task.result()` so
   websocket errors fail fast.

3. Medium, `nuubot/runtime.py`: candle freshness uses only candle open time
   `t`.

   Why it matters: Hyperliquid updates the same open candle many times; those
   updates are logged but treated as not new after the first same-`t` candle.
   If BBO is quiet, updated candle data can be skipped by signal/risk/executor.

   Required fix: track candle message receive sequence/time, or use a separate
   latest candle update timestamp for freshness.

4. Low, `nuubot/runtime.py`: config uses silent defaults for `bot_id`,
   `max_loop`, `loop_seconds`, `log_file`, `data.dir`, `start`, `stop`, and
   `network`.

   Why it matters: missing config can produce a plausible but wrong proof run.

   Required fix: require the fields used by these proof templates; only default
   values that are intentionally optional.

5. Low, `nuubot/runtime.py`: unused module-level logger creates
   `workspace/logs/runtime.log`.

   Why it matters: extra proof artifact, 0-byte file, and unnecessary side
   effect.

   Required fix: delete the unused global `log`.

6. Low, `nuubot/runtime.py`: `date_ms()` overwrites timezone with UTC.

   Why it matters: aware timestamps with offsets will be shifted incorrectly;
   date-only `stop = "2025-01-03"` also means midnight inclusive, not the full
   day.

   Required fix: if parsed datetime is naive, assign UTC; if aware, convert
   with `astimezone(UTC)`. Clarify date-only stop semantics.

## proof checked

- `git status --short`: recent runtime proof files are untracked.
- Wrappers call the requested commands.
- Templates match intended proof values: backtest `max_loop=200`; papertest
  `max_loop=20`, `loop_seconds=5.0`.
- Backtest log has one 200-loop run and exits `max_loop=200`.
- Papertest log has 20 loop snapshots plus live BBO/candle receive logs.
- Binance ZIP exists and contains real `BTCUSDT-1m-2025-01.csv`; rows are
  microsecond timestamps and code converts them to ms.
- No live `nuubot.runtime` process was found.
- `uv` exists; `pyproject.toml` declares `websockets`.

## proof missing

- No rerun by audit agent because the audit was read-only.
- No captured command transcript proves logs came from the exact wrapper entry
  points.
- No negative-path proof for websocket disconnect, bad config, or invalid mode.

## assumptions

- Existing logs were generated from the current untracked code.
- For this proof, no DB and no tests are intentional.
- `BTC` is intended for Hyperliquid papertest; `BTCUSDT` is intended for
  Binance backtest.

## open questions

- Should same-minute candle updates drive signal/risk/executor, or only new
  candle opens?
- Should date-only `stop` mean midnight inclusive or the full calendar day?

## bloat check

No fake DB/server/framework found. Found small bloat/side effect: unused global
logger and silent config fallback paths. Found real logic risks: invalid mode
fallback, hidden websocket task failure, stale candle freshness handling, and
weak date handling.
