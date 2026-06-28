---
title: coding rules
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [coding, rules]
---

# coding rules

## objective

Write simple, clear code.

## guidance

- Fail FAST. Fail LOUD.
- Ponytail rules are the default.
  - Ask if the thing needs to exist at all.
  - Use the standard library before custom code.
  - Use native platform features before dependencies.
  - Use proven libraries before self-coding common infrastructure.
  - Use already-installed dependencies before adding new ones.
  - Prefer one line before many lines.
  - Write the minimum code that works.
  - Delete over add.
  - Boring over clever.
  - Fewest files wins.
  - YAGNI: if it is not needed now, skip it.
- Prefer proven libraries for solved problems, for example SQLAlchemy for SQL.
- Anti-factory: no factory for one product.
- Anti-indirection: no wrapper that only calls another thing.
- Anti-clever: clever code is a maintenance cost.
- Anti-future: no helpers, flags, configs, or abstractions for later.
- Anti-fallback: do not hide invalid state with fallback behavior.
- Anti-compatibility: no old-version paths unless explicitly requested.
- Async-first: use `await` for project code to keep flow consistent, unless
  forcing async requires indirection.
- Capital protection beats simplicity when money can be lost.

## rules

- Code only after explicit edit/create/add/change/migrate/install/run/fix/proceed.
- If a destructive action is ambiguous, ask first. Do not infer drops, deletes,
  truncates, resets, or session kills from unclear wording.
- Do not hide bad input, bad output, or source errors.
- `from __future__ import annotations` is allowed.
- Add no helper, wrapper, adapter, registry, fallback, cache, or abstraction
  unless the current path needs it.
- Add no property or computed field unless current code 100% needs it.
- Remove unused helpers and dead stubs.
- Comments explain intent, not mechanics.
- Comment code in short intent blocks before lifecycle actions.
- Do not comment the obvious mechanics of the next line.
- Test real code paths by default.
- Non-trivial logic needs one small runnable check.
- Keep durable facts in `wiki/**`.
- Keep project management in `.project/**`.
- Keep task-scoped research in `.research/**`.

## logging

Use `wiki/logging.md`.

## objects

- Use `wiki/coding/samples/objects.md` for object shape.
- Composing objects own and coordinate other project objects.
- Primitive objects are standalone and depend only on libraries or plain inputs.
- Create objects directly.
- Never hide creation behind a factory.

## commands

- Prefix repo commands with `rtk`.
- Search with `rtk rg -n ...`.
- Find files with `rtk rg --files`.
- Use PowerShell only when there is no practical Unix-style alternative.
- Use `apply_patch` for manual file edits.

## samples

- `wiki/coding/samples/objects.md`: composing and primitive objects.
- `wiki/coding/samples/scaffold.md`: new-file scaffold samples.
- `wiki/coding/samples/bots.md`: bot samples.
- `wiki/coding/samples/sweeps.md`: sweep samples.
- `wiki/coding/samples/helpers.md`: helper samples.
