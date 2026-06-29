---
title: webgui design
created: 2026-06-29
updated: 2026-06-29
type: wiki
status: active
tags: [design, server, webgui, fasthtml]
---

# webgui design

## purpose

WebGUI is the operator display and command-control surface.

It is part of Server, not a peer application.

## package

```text
nuubot/server/__main__.py
nuubot/server/api.py
nuubot/server/server.py
nuubot/server/sweepmgr.py
nuubot/server/webgui.py
nuubot/webgui/app.py
nuubot/webgui/layout.py
nuubot/webgui/sweeps/create.py
nuubot/webgui/sweeps/list.py
```

Start it with:

```bash
./server.sh
```

Server does not use Uvicorn reload by default. Stop and start the server after
code changes. Use `--reload` only when explicitly needed.

Repo-root helpers:

```bash
./server.sh
```

## rules

- Use FastHTML with MonsterUI standard components.
- Keep the first layout simple: header bar, sidebar, main content.
- Prefer server-rendered pages, normal forms, POST/redirect, and MonsterUI
  `Toast(...)`.
- HTMX attributes are allowed for standard request indicators, server-rendered
  swaps, and conditional 2-second polling while sweeps are active. Do not add
  hand-written browser JavaScript for this.
- Do not add custom browser JavaScript for tables, polling, toasts, file
  dialogs, or command actions unless explicitly approved.
- User-edited bot/sweep templates stay as TOML.
- API submit body for create flows may be raw TOML text.
- DB storage uses canonical JSON after manager/domain validation.
- Sweep run progress comes from SQLite rows, not worker memory.
- Keep route handlers small.
- WebGUI display code may build HTML.
- WebGUI owns HTML page shape, toast shape, and redirect behavior.
- Browser pages use FastHTML-style routes without `.html`.
- API routes use `/api/...` URLs.
- App behavior must go through Server/BotManager/SweepManager.
- Do not add a separate frontend build system.
- Do not put WebGUI in a peer package.
- `nuubot/server/webgui.py` is the Server-facing GUI entry.
- `nuubot/webgui/**` owns the actual FastHTML display code.

## first routes

```text
GET /        dashboard
GET /bots    bot control surface
GET /sweeps  sweep list
GET /sweeps/create  create sweep form
GET /server  server status surface
GET /user    user settings placeholder
GET /ping    plain liveness
GET /status  JSON status
```
