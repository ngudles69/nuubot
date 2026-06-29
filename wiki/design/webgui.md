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
nuubot/server/webgui.py
nuubot/webgui/app.py
```

Start it with:

```bash
uv run python -m nuubot.server
```

Repo-root helpers:

```bash
./server.cmd
./server.sh
```

## rules

- Use FastHTML.
- Keep the first layout simple: header bar, sidebar, main content.
- Keep route handlers small.
- WebGUI display code may build HTML.
- WebGUI owns HTML page shape, toast shape, and redirect behavior.
- App behavior must go through Server/BotManager/SweepManager.
- Do not add a separate frontend build system.
- Do not put WebGUI in a peer package.
- `nuubot/server/webgui.py` is the Server-facing GUI entry.
- `nuubot/webgui/**` owns the actual FastHTML display code.

## first routes

```text
GET /        dashboard
GET /bots    bot control surface
GET /sweeps  sweep control surface
GET /server  server status surface
GET /ping    plain liveness
GET /status  JSON status
```
