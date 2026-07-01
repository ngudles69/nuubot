---
title: botmanager design
created: 2026-06-29
updated: 2026-07-01
type: wiki
status: active
tags: [design, server, botmanager, bots]
---

# botmanager design

## purpose

BotManager owns bot control-plane operations.

Server owns BotManager. API routes and CLI helpers call BotManager; they do not
implement bot behavior themselves.

## owns

- bot DB create/load/clone/delete/view/ping/status.
- bot template creation from file or loaded template.
- managed bot start/stop/freeze/status when lifecycle code exists.
- bot lifecycle validation before manager actions.
- bot DB file discovery.
- bot archive/unarchive by DB file move.

## does not own

- Runtime loop logic.
- Signaler, risk, executor, account, ledger internals.
- bot-local websocket/feed internals.
- API route parsing beyond receiving validated inputs.
- CLI parsing or printing.

## interfaces

External functions:

- `create_botrow_via_file(path)`
- `create_botrow_via_template(template)`
- `clone_bot(bot_id)`
- `delete_bot(bot_id)`
- `load_bot(bot_id)`
- `list_bots()`
- `view_bot(bot_id)`
- `start_bot(bot_id)`
- `stop_bot(bot_id)`
- `freeze_bot(bot_id)`
- `ping_bot(bot_id)`
- `status_bot(bot_id)`
- `archive(bot_id)`
- `unarchive(bot_id)`

## contracts

| Function | Input | Output | Contract |
| --- | --- | --- | --- |
| `create_botrow_via_file(path)` | Template/config path. | Bot id and DB path. | Loads file, then calls `create_botrow_via_template(template)`. |
| `create_botrow_via_template(template)` | Loaded template object. | Bot id and DB path. | Validates through specialist config/template code, allocates server sequence, creates bot DB, and writes bot row. |
| `clone_bot(bot_id)` | Existing bot id. | New bot id and DB path. | Copies source bot config/state needed for a new configured bot. Runtime fields reset. |
| `delete_bot(bot_id)` | Configured bot id. | Deleted bot. | Only configured/not-running bots can be deleted. Fails loud otherwise. |
| `load_bot(bot_id)` | Bot id. | Bot row plus DB path. | Reads the bot DB. Does not start a bot. |
| `list_bots()` | None. | Bot DB paths/rows. | Discovers `workspace/db/*_bot_*.db`. |
| `view_bot(bot_id)` | Bot id. | Operator view. | Reads the bot DB read model. |
| `start_bot(bot_id)` | Configured bot id. | Managed process/status. | Starts one managed bot runtime with `exec_network` and `bot_id` when lifecycle code exists. |
| `stop_bot(bot_id)` | Running bot id. | Stop accepted/result. | Sends the managed bot command through the bot-local command path. |
| `freeze_bot(bot_id)` | Running bot id. | Freeze accepted/result. | Sends the managed bot command through the bot-local command path. Deferred until lifecycle command exists. |
| `ping_bot(bot_id)` | Bot id. | Liveness result. | Checks heartbeat freshness. |
| `status_bot(bot_id)` | Bot id. | Status result. | Combines DB file existence, heartbeat, and bot DB status. |
| `archive(bot_id)` | Inactive bot id. | None. | Moves `workspace/db/<network>_bot_<id>.db` to `workspace/db/archived/<network>_bot_<id>.db`. Does not rewrite data. |
| `unarchive(bot_id)` | Archived bot id. | None. | Moves `workspace/db/archived/<network>_bot_<id>.db` back to `workspace/db/<network>_bot_<id>.db`. |

## notes

- File and template creation share one implementation path.
- Notebook workflows may pass loaded templates directly.
- Live/sim/operator creation may pass file paths.
- Bot existence is the bot DB file.
- Archived bots live under `workspace/db/archived/` so normal bot listing does
  not scan or display them.
- Do not add a central bot catalog table unless file discovery is measured and
  proven insufficient.
- BotManager keeps managed process control simple until lifecycle code proves
  it needs more.
- BotManager replaces Redis command nudges with bot-local `command` writes.
