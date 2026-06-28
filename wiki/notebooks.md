---
title: notebook rules
created: 2026-06-26
updated: 2026-06-26
type: wiki
status: active
tags: [notebooks, development]
---

# notebook rules

## purpose

Use notebooks to accelerate runtime development one step at a time.

Notebook work is executable object documentation. A notebook may hold the
object's design intent, flow, smoke checks, functional checks, and observed
output in one place.

A notebook can be the prototype, smoke test, regression harness, bug
investigation harness, and source for migrated module code. Prove behavior in
the notebook first, then migrate stable `prod` code into modules and rerun the
same notebook against imports.

Keep `wiki/**` as the fast-readable map and durable decision source. Notebooks
prove behavior; wiki pages point to stable notebooks when the notebook is clean
and repeatable.

Do not replace wiki detail with notebook references until the notebook is
stable enough to review without scratch/debug noise.

## workflow

Create one notebook per object. Each notebook proves smoke behavior and
functional behavior for that object's contract.

Standard object notebook layout:

```text
cell 1: simple notebook setup.
cell 2: simple documentation.
cell 3: imports.
cell 4: object/function contract being tested.
cell 5+: smoke/functional usage cells.
```

```text
setup imports/config
create runtime/object
run init
inspect result
run start
inspect result
run one loop
inspect result
run next loop
inspect result
fix errors as they appear
```

Do not hide errors. If a cell fails, stop, inspect the output/state, fix the
source, then rerun the needed cells.

## prototype to module loop

Use this loop for object notebooks:

```text
write notebook-local code
run notebook smoke path
migrate stable prod code into modules
change notebook to import module code
rerun same smoke path
compare notebook-local behavior to module behavior when bugs appear
```

Do not delete useful notebook-local implementation after migration. Keep it
commented or isolated in unmarked cells so it can be uncommented for bug
investigation.

## cell markers

Only marked cells are candidates for extraction.

Production code:

```python
# nuubot: prod
```

Smoke checks:

```python
# nuubot: smoke
```

No marker means:

```text
none
```

`none` cells are trial/error cells and must not be extracted.

## extraction rules

```text
prod  -> real module code
smoke -> smoke checks
none  -> ignore
```

Default is `none`.

Never extract a cell unless it is explicitly marked `prod` or `smoke`.

## charting

Notebook charts should use the same ECharts option contract planned for the web
UI.

Preferred shape:

```text
candles/trades -> build ECharts option -> notebook HTML renderer
candles/trades -> build ECharts option -> React renderer later
```

Do not make reusable chart logic depend on React. React and notebook HTML are
renderers. The shared part is the ECharts option builder.

## notes

- Keep notebooks out of runtime control flow.
- Move stable `prod` code into `.py` modules before depending on it.
- Move stable `smoke` code into `smoke/**`.
- Keep debug output in unmarked cells.
