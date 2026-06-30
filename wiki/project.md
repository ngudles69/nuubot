---
title: project
created: 2026-06-20
updated: 2026-06-29
type: wiki
status: active
tags: [project, objective]
---

# project

## objective

`nuubot` is a clean algo-trading bot project.

The objective is to create capital-protective, profitable algo-trading bots.

The key financial target is `10,000` profit per month while protecting capital.

The first bot direction is a simple but extensive grid bot. The bot should be
easy to understand, easy to run, and hard to overcomplicate.

## references

- `D:\rust\nuutrader6`: working reference code. Look here first for existing
  behavior before designing new bot/runtime/sweep code. Ask the user before
  bringing code over, then adapt it to `nuubot`; never copy it as-is.
- `D:\rust\nuutrader-references\BlackBot`: working grid-bot behavior
  reference. Use it to understand the strategy. Do not paste it in.

## principles

- Prefer the smallest working design.
- Build the actual grid bot before adding platform around it.
- Protect capital before chasing profit.
- Avoid hidden fallback behavior.
- Use references for patterns, not wholesale copying.
- Use SQLite for runtime state: one DB file per bot/sweep/sweeprun instance,
  plus one persistent server DB for seq numbers, server state, and
  exchange meta.
- Code/test bots through notebooks using direct BotRuntime.
- Use `ProcessPoolExecutor` for sweep parallelism.
- Keep managed bot process control simple and defer it until BotManager needs
  real live lifecycle handling.
- Keep bot websocket/feed clients bot-local first.

## commands

- Use repo commands directly.
- Search with `rg -n ...`.
- Find files with `rg --files`.
- Use `apply_patch` for manual file edits.

## knowledge layout

- Keep durable facts in `wiki/**`.
- Keep project management in `.project/**`.
- Keep task-scoped research in `.research/**`.
