# handoff

Last updated: 2026-07-02

## focus

Sweep signaler data ownership and `SwEmacross` reference shape.

## current status

- Latest implementation commit: `41364e4 Clarify sweep signaler data ownership`.
- Sweep signaler design is documented in `wiki/design/sweeps.md`.
- `SwData` declares all fields up front:
  `name`, `symbol`, `timeframe`, `warmup_bars`, `max_age_ms`, `start_ms`,
  `stop_ms`, `frame`.
- `SwEmacross` owns its signal data internally as `self.crossover`.
- `SwEmacross` lifecycle is:
  `init`, `start`, `load`, `calc`, `check`, `stop`.
- Signalers do not expose `data_req()` or `signaler.data`.
- `load()` determines warmup bars and the dataset load window, then loads data.
- `calc()` calculates the full loaded dataset.
- `check()` picks the latest closed calculated row as of the requested time and
  returns `SwSignal`.
- Sweeprun owns replay `SwData`; executor consumes bars and signals.
- Binance monthly `.zip` is canonical when both `.zip` and extracted `.csv`
  exist for the same month.
- `DataLoader` reuses `nuubot.core.market_data.read_binance_file()` for parsing.

## active server

- Server is running on `127.0.0.1:5001`.
- Current server PID from port owner: `54608`.
- Started via `bash ./server.sh` after stopping old PID `13488`.

## active agents

None.

## blockers

None known.

## files changed in latest implementation

- `nuubot/core/data_loader.py`
- `nuubot/core/dtypes.py`
- `nuubot/sweeps/executors/swtradebot.py`
- `nuubot/sweeps/signalers/signaler.py`
- `nuubot/sweeps/signalers/swemacross.py`
- `nuubot/sweeps/sweeprun.py`
- `tests/test_emacross_params.py`
- `tests/test_swemacross.py`
- `wiki/design/sweeps.md`

## proof run

- `rtk uv run python -m compileall -q nuubot tests`
- `PYTHONPATH=.` all `tests/test_*.py`
- `rtk git diff --check`
- Server restart proof:
  - stopped old port owner PID `13488`
  - `bash ./server.sh`
  - server restarted on PID `54608`
  - `/status` returned running
- Sweep `28` rerun through current server API:
  - `POST /api/sweeps/28/run` returned `status=running`, `total_count=36`
  - final `/api/sweeps/28/metrics` returned `status=complete`
  - `complete_count=36`
  - `failed_count=0`
  - `progress=36/36`
  - `total_ms=1202`
  - `bars=157680`
  - `bars_per_second=131181.36`
  - `timing_signaler_check_ms` present
- SQLite check:
  - no sweeprun error text
  - `complete|36`

## proof not run

- No new adversarial audit after commit `41364e4`.
- No synthetic ZIP fixture test. ZIP behavior is covered by file-selection test
  and real sweep 28 path.

## decisions made

- Use protocol shape for sweep signalers instead of inheritance.
- Keep signaler datasets owned by the signaler implementation.
- Keep replay data owned by `Sweeprun`.
- Use `check()` as the signal query method.
- Keep `SwSignal` as the standardized return:
  `enter_long`, `enter_short`, `exit_long`, `exit_short`, `reason`.
- Use Polars frames for loaded/calculated sweep signaler data.
- Keep indicator column names private to each signaler.
- Keep `calc()` and `check()` paired inside each signaler implementation.
- Use Binance `.zip` as canonical monthly source when duplicate `.csv` exists.
- Keep placeholder builders for sweep signalers/executors for now.

## next action

None. Push current commits; resume from latest `main`.
