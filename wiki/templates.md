---
title: templates
created: 2026-07-01
updated: 2026-07-01
type: wiki
status: active
tags: [templates, config]
---

# templates

## purpose

Templates are author-facing TOML files for creating bot and sweep configs.
They should be readable, explicit, and runnable through the current code.

Templates follow an MT5-style model:

- bot templates define concrete strategy settings.
- sweeprun configs are bot templates plus a fixed run window.
- sweep templates define grouped sets and sweepable values that generate
  concrete sweeprun configs.

## layout

```text
workspace/templates/
  AGENTS.md
  bots/
    AGENTS.md
  sweeps/
    AGENTS.md
    old/
```

Rules:

- Put bot templates under `workspace/templates/bots/**`.
- Put sweep templates under `workspace/templates/sweeps/**`.
- `workspace/templates/sweeps/old/**` is reference-only.
- Do not put active templates directly under `workspace/templates/`.

## docs

- `wiki/templates-bots.md`: bot template authoring rules.
- `wiki/templates-sweeps.md`: sweep template authoring rules.
- `wiki/design/strategy.md`: signaler, executor, and risk rules.
- `wiki/design/sweeps.md`: sweep behavior and result rules.

## validation

Validation happens at boundaries:

1. Parse TOML. Malformed TOML fails immediately.
2. Validate raw template labels and expansion shape.
3. Expand sweep templates into concrete sweeprun configs.
4. Validate every generated sweeprun config with Pydantic before creating
   records.
5. Revalidate stored `config_json` when a sweeprun starts.
6. Initialize signalers, executor, and risk. Each component validates its own
   required params and fails loud.
7. Validate data path, date coverage, and warmup/history needs.

After init succeeds, runtime code trusts initialized objects and does not
repeat boundary checks in hot loops.
