# handoff

Last updated: 2026-06-25

## focus

Runtime cleanup is in progress after the datastore/Nuubot simplification.
Runtime should read close to BlackBot: visible clock/replay flow, clear loop
sequence, one composed object call for signaler/executor/risk behavior.

## current status

- Last commit: `9043e0b Add object design and command datastore scaffold`.
- Worktree has the uncommitted datastore/Nuubot/runtime/signaler cleanup.
- `progflow.pdf` is untracked and intentionally left alone for now.
- Runtime main flow is approved; do not change the runtime sequence.
- Datastore is now infra-only: `Datastore(config).init()`, `session()`,
  `stop()`.
- `Nuubot.setup()` owns config loading and datastore initialization.
- CLI owns bot catalog commands and uses SQLAlchemy sessions/models directly.
- Runtime creates `self.nuubot = nuubot_setup()` and will pass that to
  CommandServer when CommandServer is implemented.
- Runtime now talks to one `Signaler` composer. The composer owns child
  signaler creation, seeding, eligibility, and signal selection.
- Constructor/input order is locked: `nuubot`, then object id, then qualifiers
  or callbacks.
- Runtime target loop is phase-based: gather command/market/signaler/risk/
  executor inputs, check exits only after started, check entries before
  started, then active processing for recon/order exits/new orders, then
  heartbeat/status persistence.
- Fresh start and restart use the same loop: Executor reconciles exchange/
  account/ledger state first. Fresh start should reconcile to flat/no-op.
- Reconcile is mandatory before every non-kill operation. Only `kill` skips it
  because no trading/closing operation follows.
- `kill` exits the runtime process without canceling orders or closing
  positions; the bot remains restartable.
- Graceful `stop` closes the bot through Executor, then marks terminal stopped.
  Terminal stopped/error bots cannot be restarted.

## active agents

None.

## blockers

None known.

## decisions made

- Datastore has no `start()`.
- Datastore does not own bot lifecycle commands.
- Datastore `init()` creates every configured database, table, and SQLAlchemy
  metadata index if missing.
- Current implementation uses one SQLite file per configured DB name under
  `workspace/db`; PostgreSQL remains later.
- `create_databases()`, `create_tables()`, and `create_indexes()` are not public
  datastore commands.
- `Nuubot` is the infra owner for `config` and `datastore`.
- Runtime uses `Nuubot` for infra, but the approved runtime loop order is
  unchanged.
- Runtime and Clock interaction should stay explicit in Runtime.
- Signaler/account/executor internals should stay inside their own objects.
- Current runtime implementation is intentionally simpler than the target loop:
  command polling, started-state handling, recon, order exits, new-order
  submission, and DB status writes wait for those owning objects.

## files changed

- `HANDOFF.md`
- `nuubot/__init__.py`
- `nuubot/nuubot.py`
- `nuubot/cli/cli.py`
- `nuubot/datastore/__init__.py`
- `nuubot/datastore/datastore.py`
- `nuubot/core/runtime.py`
- `nuubot/signaler/__init__.py`
- `nuubot/signaler/signaler.py`
- `wiki/AGENTS.md`
- `wiki/design/overview.md`
- `wiki/design/objects/AGENTS.md`
- `wiki/design/objects/cli.md`
- `wiki/design/objects/datastore.md`
- `wiki/design/objects/nuubot.md`
- `wiki/design/objects/runtime.md`
- `wiki/design/objects/signaler.md`

## proof run

- Compile:
  `uv run python -m py_compile nuubot/nuubot.py nuubot/datastore/datastore.py nuubot/datastore/models.py nuubot/cli/cli.py nuubot/cli/__main__.py`
- Config smoke:
  `uv run python -m smoke.config`
- Infra setup:
  `uv run python -c "from nuubot import Nuubot; n=Nuubot.setup(); print(n.config.general.mode); print(sorted(n.datastore.sessions)); n.stop()"`
- CLI:
  `uv run python -m nuubot.cli create -f workspace/templates/smoke-backtest.toml`
- CLI:
  `uv run python -m nuubot.cli view`
- CLI:
  `uv run python -m nuubot.cli clone 1`
- CLI:
  `uv run python -m nuubot.cli stop 1`
- CLI:
  `uv run python -m nuubot.cli ping 1`
- Runtime smoke:
  `uv run python -m nuubot.core.runtime -f workspace/templates/smoke-backtest.toml`
- Compile after runtime cleanup:
  `uv run python -m py_compile nuubot/core/runtime.py nuubot/signaler/signaler.py nuubot/signaler/__init__.py nuubot/core/sweep.py`
- Whitespace:
  `rtk git diff --check`

## proof not run

- CLI `start` still intentionally fails loud because runtime launch is not
  wired yet.

## next action

Continue runtime cleanup only if it keeps behavior unchanged: keep clock/replay
visible in Runtime, push object internals into their owning object, then
implement DB-backed `CommandServer(nuubot, bot_id, callbacks)`.
