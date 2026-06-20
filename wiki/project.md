---
title: project
created: 2026-06-20
updated: 2026-06-20
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

- `D:\rust\nuutrader6`: working but bloated reference code. Use it for proven
  patterns and lessons. Do not copy it wholesale.
- `D:\rust\nuutrader-references\BlackBot`: working grid-bot behavior
  reference. Use it to understand the strategy. Do not paste it in.

## principles

- Prefer the smallest working design.
- Build the actual grid bot before adding platform around it.
- Protect capital before chasing profit.
- Avoid hidden fallback behavior.
- Use references for patterns, not wholesale copying.

## commands

- Prefix repo commands with `rtk`.
- Search with `rtk rg -n ...`.
- Find files with `rtk rg --files`.
- Use `apply_patch` for manual file edits.

## knowledge layout

- Keep durable facts in `wiki/**`.
- Keep project management in `.project/**`.
- Keep task-scoped research in `.research/**`.
