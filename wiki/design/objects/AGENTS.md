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

1. `nuubot.md`: shared infra owner.
2. `runtime.md`: master composer.
3. `config.md`: config holder.
4. `account.md`: exchange account composer, simulator, ledger.
5. `ledger.md`: positions, orders, fills.
6. `datastore.md`: SQLite datastore boundary.
7. `data.md`: `WsData`, `FileData`, meta helpers.
8. `signaler.md`: signaler, indicators, consensus.
9. `executor.md`: strategy execution logic.
10. `cli.md`: bot manager program.
11. `command.md`: runtime command-table server.
