# AGENTS.md

Rules for files under `wiki/design/objects/**`.

## Purpose

- Each file defines one object boundary.
- Use the standard sections:
  - `purpose`
  - `interfaces`
  - `contracts`
  - `processing`
  - `key helpers`
  - `notes`
- Keep the allowed connections explicit.
- If an object needs a new connection to another object, update the relevant
  object file before code uses that connection.

## Files

1. `runtime.md`: master composer.
2. `config.md`: config holder.
3. `account.md`: exchange account composer, simulator, ledger.
4. `ledger.md`: positions, orders, fills.
5. `datastore.md`: PostgreSQL and SQLAlchemy boundary.
6. `data.md`: `WsData`, `FileData`, meta helpers.
7. `signaler.md`: signaler, indicators, consensus.
8. `executor.md`: strategy execution logic.
9. `cli.md`: bot manager program.
10. `command.md`: runtime command-table server.
