# handoff

Last updated: 2026-07-02

## focus

Sweep signaler protocol and `SwEmacross` reference implementation.

## current status

- Sweep signaler design is documented in `wiki/design/sweeps.md`.
- `SwSignal`, `SwSignaler`, `SwData`, `Timeframe`, generic `DataLoader`, and
  `SwEmacross` are implemented.
- `SwEmacross` lifecycle is:
  `init`, `start`, `data_req`, `load`, `calc`, `check`, `stop`.
- `calc()` writes calculated columns to the Polars frame and builds a small
  close-time signal cache for fast `check()` lookup.
- Binance monthly `.zip` is treated as canonical when both `.zip` and extracted
  `.csv` exist for the same month.
- `DataLoader` reuses `nuubot.core.market_data.read_binance_file()` for parsing.
- Closeout audit passed: `audits/07-02-sweep-signaler-audit-v1.md`.
- Closeout commit: this commit.

## active server

- Server is running on `127.0.0.1:5001`.
- Current server PID from port owner: `13488`.
- Started via `bash ./server.sh` after stopping old PID `29184`.

## active agents

None. Adversarial sub-agent `019f2300-acf9-7f31-ad70-9ff5895ad0e7` completed PASS.

## blockers

None known.

## files changed

- `HANDOFF.md`
- `audits/07-02-sweep-signaler-audit-v1.md`
- `nuubot/core/data_loader.py`
- `nuubot/core/dtypes.py`
- `nuubot/signalers/emacross/emacross.py`
- `nuubot/sweeps/executors/__init__.py`
- `nuubot/sweeps/executors/executor.py`
- `nuubot/sweeps/executors/swtradebot.py`
- `nuubot/sweeps/signalers/__init__.py`
- `nuubot/sweeps/signalers/signaler.py`
- `nuubot/sweeps/signalers/swemacross.py`
- `nuubot/sweeps/sweeprun.py`
- `pyproject.toml`
- `uv.lock`
- `tests/test_data_loader.py`
- `tests/test_emacross_params.py`
- `tests/test_swemacross.py`
- `wiki/design/sweeps.md`

## proof run

- `rtk uv run python -m compileall -q nuubot tests`
- `PYTHONPATH=.` all `tests/test_*.py`
- `rtk git diff --check`
- real loader check:
  - `4375` rows
  - `4375` unique timestamps
  - `4344` active BTCUSDT 1h bars
- Server restart proof:
  - stopped old port owner PID `29184`
  - `bash ./server.sh`
  - server restarted on PID `13488`
  - `/status` returned running
- Sweep `28` rerun through current server API:
  - `POST /api/sweeps/28/run` returned `status=running`, `total_count=36`
  - final `/api/sweeps/28/metrics` returned `status=complete`
  - `complete_count=36`
  - `failed_count=0`
  - `progress=36/36`
  - `total_ms=1243`
  - `bars=157680`
  - `bars_per_second=126854.38`
  - `timing_signaler_check_ms` present
- SQLite check:
  - `complete|36`
  - no sweeprun error text
- Adversarial audit:
  - first pass found stale proof, stale handoff, duplicate parser
  - fixes applied
  - second pass PASS

## proof not run

- No synthetic ZIP fixture test. ZIP behavior is covered by file-selection test
  and real sweep 28 path.

## decisions made

- Use protocol shape for sweep signalers instead of inheritance.
- Use `check()` as the signal query method.
- Keep `SwSignal` as the standardized return:
  `enter_long`, `enter_short`, `exit_long`, `exit_short`, `reason`.
- Use one `SwData` object as both request and loaded-data holder.
- Use Polars frames for loaded/calculated sweep signaler data.
- Keep indicator column names private to each signaler.
- Keep `calc()` and `check()` paired inside each signaler implementation.
- Use Binance `.zip` as canonical monthly source when duplicate `.csv` exists.
- Keep placeholder builders for sweep signalers/executors for now.

## next action

None. Work is complete; pushed commit should be the current resume point.
