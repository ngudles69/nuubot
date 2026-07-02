---
title: coding rules
created: 2026-06-20
updated: 2026-07-02
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
- Prefer the standard library for simple SQLite access. Use SQLAlchemy only
  when the current code path benefits from it and still keeps server DB access
  open/read-write/close.
- Anti-factory: no factory for one product.
- Anti-indirection: no wrapper that only calls another thing.
- Anti-clever: clever code is a maintenance cost.
- Anti-future: no helpers, flags, configs, or abstractions for later.
- Anti-fallback: do not hide invalid state with fallback behavior.
- Anti-compatibility: no old-version paths unless explicitly requested.
- Async-first: use `await` for project code to keep flow consistent, unless
  forcing async requires indirection.
- Capital protection beats simplicity when money can be lost.
- Before implementing bot/runtime/sweep behavior, inspect `D:\rust\nuutrader6`
  for working code. Ask before bringing code over. Adapt to this codebase;
  never paste it in unchanged.

## rules

- Code only after explicit edit/create/add/change/migrate/install/run/fix/proceed.
- If a destructive action is ambiguous, ask first. Do not infer drops, deletes,
  truncates, resets, or session kills from unclear wording.
- Do not hide bad input, bad output, or source errors.
- Validate at boundaries: file parse, DB load, generated config, and component
  init. After init succeeds, trust initialized runtime objects and do not repeat
  defensive shape checks in hot loops.
- `from __future__ import annotations` is allowed.
- Add no helper, wrapper, adapter, registry, fallback, cache, or abstraction
  unless the current path needs it.
- Add no Postgres path, migration layer, or DB compatibility bridge unless the
  user explicitly reverses the SQLite direction.
- Add no property or computed field unless the user requests it.
- Get user approval and document abbreviations in `wiki/abbreviations.md`
  before using them.
- Remove unused helpers and dead stubs.
- Comments explain intent, not mechanics.
- Comment code in short intent blocks before lifecycle actions.
- Do not comment the obvious mechanics of the next line.
- Test real code paths by default.
- Non-trivial logic needs one small runnable check.
- Keep durable facts in `wiki/**`.
- Keep project management in `.project/**`.
- Keep task-scoped research in `.research/**`.

## functions

Do:

- Do make a function for real functionality.
  Why: users and callers need stable operations such as `list()`, `clone()`,
  `delete()`, `archive()`, `run()`, and `metrics()`.
- Do name the function by caller-facing intent.
  Why: the name should say what useful job is being done, not how the code does
  it.
- Do let one function contain the checks that belong to its functionality.
  Why: `parse_template()` can parse and validate the template. If a template has
  100 fields, that does not mean it needs 100 field-check functions.
- Do keep simple field assembly inside the response or object builder.
  Why: a derived field like `name = config["sweep"]["name"]` is part of
  building a list row or metrics payload, not its own domain operation.
- Do use short intent comments inside a larger function when sections help.
  Why: comments can show structure without creating fake one-caller helpers.
- Do break code into more functions only when the user asks for it, the current
  function is getting difficult to read, the code is repeated or reused in many
  places, or the code is custom logic instead of standard commands.
  Why: helpers are for reducing actual complexity, not for making code look
  decomposed.

Don't:

- Don't add one-line indirection.
  Why: a function that only calls another function or returns one field adds a
  name without adding functionality.
- Don't split code only because a block has a smaller sub-intent.
  Why: one functionality can have several internal steps; each step does not
  deserve a function.
- Don't split parse and validate just because they are separate verbs.
  Why: split only when validation is reused, complex enough to deserve its own
  name, or useful as a separate caller-facing operation.
- Don't name functions after mechanics, types, storage, parsing method, or
  plumbing.
  Why: names like `_from_path`, `_text`, `_using_regex`, or `_raw` describe how
  the code works instead of why the caller wants it.
- Don't create one helper per field.
  Why: if `sweep_name()` is justified, then every config field can become a
  function, which turns field access into ceremony.
- Don't keep fake concepts just because they are used.
  Why: used code is not automatically useful code. A one-caller helper can
  still be noise.
- Don't expose storage layout as a public manager operation.
  Why: functions like `archive_dir()` describe internal placement, not user
  intent.

## logging

Use `wiki/logging.md`.

## objects

- Use `wiki/coding/samples/objects.md` for object shape.
- Composing objects own and coordinate other project objects.
- Primitive objects are standalone and depend only on libraries or plain inputs.
- Create objects directly.
- Never hide creation behind a factory.

## commands

- Use repo commands directly.
- Search with `rg -n ...`.
- Find files with `rg --files`.
- Use PowerShell only when there is no practical Unix-style alternative.
- Use `apply_patch` for manual file edits.

## samples

- `wiki/coding/samples/objects.md`: composing and primitive objects.
- `wiki/coding/samples/scaffold.md`: new-file scaffold samples.
- `wiki/coding/samples/bots.md`: bot samples.
- `wiki/coding/samples/sweeps.md`: sweep samples.
- `wiki/coding/samples/helpers.md`: helper samples.
