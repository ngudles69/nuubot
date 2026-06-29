---
title: botmanager design
created: 2026-06-29
updated: 2026-06-29
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
- bot actor start/stop/freeze/status through Ray.
- bot lifecycle validation before manager actions.
- bot DB file discovery.

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
| `start_bot(bot_id)` | Configured bot id. | Ray actor handle/status. | Starts one Ray bot actor with `exec_network` and `bot_id`. |
| `stop_bot(bot_id)` | Running bot id. | Stop accepted/result. | Calls Ray actor command path. |
| `freeze_bot(bot_id)` | Running bot id. | Freeze accepted/result. | Calls Ray actor command path. Deferred until lifecycle command exists. |
| `ping_bot(bot_id)` | Bot id. | Liveness result. | Checks Ray actor evidence and heartbeat freshness. |
| `status_bot(bot_id)` | Bot id. | Status result. | Combines DB file existence, Ray actor state, heartbeat, and bot DB status. |

## notes

- File and template creation share one implementation path.
- Notebook workflows may pass loaded templates directly.
- Live/sim/operator creation may pass file paths.
- Bot existence is the bot DB file.
- Do not add a central bot catalog table unless file discovery is measured and
  proven insufficient.
- BotManager replaces `nuutrader6` subprocess spawning with Ray actor starts.
- BotManager replaces Redis command nudges with Ray actor calls for managed
  runs and bot-local `command` writes for manual runs.
