---
title: abbreviations
created: 2026-06-29
updated: 2026-06-30
type: wiki
status: active
tags: [glossary, naming]
---

# abbreviations

Use these abbreviations consistently in code, schemas, notebooks, and wiki
when a short name is clearer than the full word.

## rule

- Use the abbreviation only when it is listed here.
- Get user agreement before adding or using a new abbreviation.
- Document the abbreviation in this file before using it in code, schema,
  notebooks, or wiki.
- Prefer the listed field name for IDs.
- Do not invent one-off abbreviations in local code.
- Hyperliquid-provided IDs keep Hyperliquid names.

## standard names

| Abbrev | Meaning | Standard field/class use |
| --- | --- | --- |
| `acct` | account | general short name |
| `acct_id` | account id | account key |
| `mgr` | manager | general short name |
| `botmgr` | bot manager | `BotManager` instance name |
| `sweepmgr` | sweep manager | `SweepManager` instance name |
| `pos` | position | general short name |
| `pos_id` | position id | position key when using short form |
| `seq` | sequence | server DB sequence table |
| `cfg` | config | local variable only when obvious |
| `db` | database | file/path/local variable |
| `tbl` | table | local variable only when obvious |
| `ctx` / `Ctx` | context | local variable / class suffix |
| `IdCtx` | id context | small dataclass carrying IDs/config |

## id naming

- DB primary keys use explicit `<thing>_id`, for example `bot_id`,
  `sweep_id`, `sweeprun_id`, `position_id`, `order_id`, and `fill_id`.
- References use the same explicit `<thing>_id` name.
- Python objects may expose `self.id` internally when it is the object's own
  id.
- Do not rename DB primary keys to bare `id` unless the schema rule changes.

## exchange ids

| Name | Meaning | Source |
| --- | --- | --- |
| `oid` | order id | Hyperliquid |
| `cloid` | client order id | app/client supplied to Hyperliquid |
| `tid` | trade id | Hyperliquid |

## table class names

Table row classes keep explicit names:

| Table | Class |
| --- | --- |
| `account` | `AccountRow` |
| `position` | `PositionRow` |
| `order` | `OrderRow` |
| `fill` | `FillRow` |
