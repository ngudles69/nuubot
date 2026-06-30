FAIL

Findings ordered by severity:

- High `nuubot/config/models.py`, `workspace/config/config.toml`,
  `tests/test_runtime_flow.py`: stale logical DB names still existed in the
  active config schema and tracked config/test fixtures.
  - Required fix: remove the old DB-name config object, delete tracked
    DB-name config, and update the runtime-flow fixture.

Verified proof/test surfaces:

- Datastore boundary grep found no `create_engine`, `Session`, or SQLAlchemy
  session use outside `nuubot/datastore/**`.
- `nuubot/datastore/dbname.py` centralizes `sweep_<id>.db` and
  `<network>_bot_<id>.db`.
- Worker validation happens before reset.
- Run/update share the same lock.
- Failure result paths write status.
- Tests exist for dbname, missing DB guard, process failure result,
  invalid-worker no-reset, and update-vs-run locking.
- No old command-wrapper references found in `AGENTS.md`, `wiki`, `.project`,
  `HANDOFF.md`, or `pyproject.toml`.
- No old core sweep module command found; `nuubot/core/sweep.py` only keeps
  helpers.
- `git diff --check` passed with LF/CRLF warnings only.

Residual risks:

- Audit did not rerun Python tests because it was read-only.
- Ignored `workspace/config/credentials.example.toml` still contains a stale
  `[database]` example; it is not tracked.
