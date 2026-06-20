---
title: frontend design
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [design, frontend]
---

# frontend design

Frontend is a separate scope from bot runtime.

Frontend means a separate frontend server that serves pages and provides views
into datastore state. It is interchangeable:

- CLI
- TUI
- Streamlit
- NiceGUI
- Gradio
- Vite
- another HTTP client

Frontend server should not own bot execution. Viewer pages are hosted by the
frontend server, not by bots. Frontend reads from datastore. Frontend may send
commands to a bot's per-bot `CommandServer` over HTTP when command actions are
needed.

Frontend server responsibilities:

- List configured bots.
- List running bots.
- List terminal bots.
- Show bot status.
- Show bot command port.
- Show bot liveness from HTTP ping/status when the bot is running.
- Show latest risk score.
- Show latest signal state.
- Show open positions.
- Show closed positions.
- Show orders.
- Show fills.
- Show events.
- Show dirty state when cleanup failed.
- Show redacted config snapshot used by a bot run.

Bot/runtime responsibilities for frontend:

- Persist bot status to datastore.
- Persist configured-but-not-started bots to datastore.
- Persist running bot state to datastore.
- Persist terminal bot state to datastore.
- Persist events to datastore.
- Persist positions, orders, and fills to datastore.
- Persist redacted config snapshot to datastore.

Minimum frontend server API routes later:

```text
GET /bots
GET /bots/{bot_id}
GET /bots/{bot_id}/positions
GET /bots/{bot_id}/orders
GET /bots/{bot_id}/fills
GET /bots/{bot_id}/events
```

These routes read datastore only. They do not execute strategy logic.

Bot command routes remain on each bot's local `CommandServer`. Bot command
servers do not host viewer pages.

Minimum bot command routes:

```text
GET /ping
GET /status
POST /stop
```

Do not build a frontend now. Document the datastore state needed so any
frontend can be built later.
