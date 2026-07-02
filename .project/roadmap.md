---
title: roadmap
created: 2026-06-20
updated: 2026-07-02
type: project
status: active
tags: [roadmap]
---

# nuubot project plan

This file is the project plan.

## status markers

- `[ ]` not started
- `[o]` in progress
- `[x]` done this session only

## rules

- Keep tasks short.
- Put durable facts and decisions in `wiki/**`.
- Put proof notes in `.project/**` or `.research/**` while they are active.
- Treat this file as working state. It can be out of date.
- Remove old done items after they are no longer useful for current work.

## project plan

### [x] 1. Runtime direction

  - [x] 1.1 Lock SQLite-only datastore.
  - [x] 1.2 Lock one bot runtime to one bot SQLite DB.
  - [x] 1.3 Lock BotRuntime as plain Python runnable without Ray.
  - [x] 1.4 Replace Ray with stdlib process pools for sweeps.
  - [x] 1.5 Lock notebooks as the code/test path.
  - [x] 1.6 Lock Server + managers as the live run path.
  - [x] 1.7 Lock bot-local websocket/feed clients first.
  - [x] 1.8 Lock no Redis and no shared websocket server first.

### [x] 2. Datastore schemas

  - [x] 2.1 Create server tables: `seq`, `state`, `meta`.
  - [x] 2.2 Remove central bot/sweep/sweeprun catalog tables.
  - [x] 2.3 Create bot tables: `bot`, `account`, `command`, `event`,
    `botstate`, `position`, `order`, `fill`, `simstate`.
  - [x] 2.4 Create sweep tables: `sweep`, `sweeprun`, `botrun`, `account`,
    `event`, `position`, `order`, `fill`.
  - [x] 2.5 Remove redundant `bot_id` from per-bot position/order/fill tables.
  - [x] 2.6 Add atomic server seq allocation with `BEGIN IMMEDIATE`.
  - [x] 2.7 Prove table creation and seq allocation with a temp SQLite
    check.

### [o] 3. Datastore behavior

  - [ ] 3.1 Clean up datastore module boundaries around server DB, bot DB, and
    sweep DB.
  - [ ] 3.2 Keep server tables separate from bot tables in schema creation.
  - [ ] 3.3 Enforce short open/read-write/close access for `server.db`.
  - [ ] 3.4 Use DB file existence as bot/sweep/sweeprun existence truth.
  - [ ] 3.5 Add focused tests for server seq, meta refresh, bot DB table
    creation, and file discovery.

### [o] 4. Nuubot setup

  - [ ] 4.1 Rejig `nuubot_setup()` into the single shared setup entrypoint.
  - [ ] 4.2 Make create-vs-load behavior explicit for server DB and meta.
  - [ ] 4.3 Keep exchange meta fetch/update inside setup when missing or older
    than 24 hours.
  - [ ] 4.4 Prove setup is idempotent for repeated process-local calls.

### [o] 5. Bot create/load/setup

  - [ ] 5.1 Add `create_botrow_via_file(path)`.
  - [ ] 5.2 Add `create_botrow_via_template(template)`.
  - [ ] 5.3 Make file and template creation share one implementation path.
  - [ ] 5.4 Add `bot_setup(exec_network, bot_id)`.
  - [ ] 5.5 Load bot row, bot state, accounts, positions, orders, and fills.
  - [ ] 5.6 Read required meta from `server.db`, fail loud if missing, and
    write a local bot DB meta snapshot.
  - [ ] 5.7 Prove notebooks can pass a loaded template directly and live/sim
    creation can pass a file path.

### [o] 6. Server, WebGUI, managers, workers, and CLI

  - [x] 6.1 Add Server as the parent/control process.
  - [ ] 6.2 Add BotManager for bot create/load/clone/delete/view/ping/status.
  - [x] 6.3 Add SweepManager for sweep create/run/metrics/archive operations.
  - [x] 6.4 Add Server API routes as thin adapters.
  - [x] 6.5 Add FastHTML WebGUI under `nuubot/webgui/**`.
  - [x] 6.6 Start WebGUI with `uv run python -m nuubot.server`.
  - [x] 6.7 Add repo-root `server.cmd` and `server.sh` helpers.
  - [x] 6.8 Add sweep create/list WebGUI pages and `/api/sweeps` routes.
  - [x] 6.9 Remove Ray from the active runtime path.
  - [ ] 6.10 Start live managed bots through BotManager when lifecycle code needs it.
  - [x] 6.11 Submit sweep tasks through SweepManager using `ProcessPoolExecutor`.
  - [x] 6.12 Keep API/routes tiny: validate input, call one manager/helper,
    return result.
  - [ ] 6.13 Keep CLI as a thin operator helper over the same manager/helper
    functions.
  - [ ] 6.14 Prove one managed bot process creates one bot DB and returns status.

### [o] 7. Bot-local data feeds

  - [ ] 7.1 Make `WsData` own bot-local websocket/feed clients.
  - [ ] 7.2 Add lazy websocket connection on bot data start.
  - [ ] 7.3 Add reconnect/status handling inside the bot-local feed object.
  - [ ] 7.4 Expose latest BBO/candle snapshots to Runtime.
  - [ ] 7.5 Keep shared DataEngines deferred until measured need.

### [o] 8. Bot runtime and lifecycle

  - [ ] 8.1 Add plain Python `BotRuntime(exec_network, bot_id)`.
  - [ ] 8.2 Make notebooks run BotRuntime directly.
  - [ ] 8.3 Runtime setup checks server infra/meta once and fails loud if
    unavailable.
  - [ ] 8.4 Runtime setup calls `bot_setup()` once.
  - [ ] 8.5 Runtime composes signaler, risk, executor, data, and clock after
    bot state is loaded.
  - [ ] 8.6 Add bot-local `command`, `event`, and `botstate` handling.
  - [ ] 8.7 Add lifecycle commands: start, stop, freeze/exit, status.
  - [ ] 8.8 Prove direct notebook runtime and managed bot runtime share the same
    BotRuntime path.

### [o] 9. Sweep

  - [x] 9.1 Implement a basic EMA-cross data/indicator sweep loop.
  - [x] 9.2 Use EMA-cross sweep as the template for future sweeps.
  - [x] 9.3 Prove sweep runs through SweepManager and process-pool task path.

### [o] 10. Template system

  - [ ] 10.1 Add boundary-validation rules to `AGENTS.md` and
    `wiki/coding/rules.md`: validate at file/DB/component init boundaries,
    then trust initialized runtime objects.
  - [ ] 10.2 Update `wiki/templates*.md` with the MT5-style template model:
    loose sweep authoring, grouped data/signalers/executors sets, concrete
    generated sweeprun configs, and component-owned param validation.
  - [ ] 10.3 Create active `workspace/templates/bots/**` and
    `workspace/templates/sweeps/**` examples; keep
    `workspace/templates/sweeps/old/**` reference-only.
  - [ ] 10.4 Implement sweep-template parsing with label validation for
    `data.*`, `signalers.*`, and `executors.*`; labels are metadata and must
    stay simple for names like
    `template/data=01/signalers=01/executors=01/run=001`.
  - [ ] 10.5 Expand grouped set permutations into concrete scalar sweeprun
    bot configs: expanded data sets x signaler sets x executor sets x
    non-grouped sweep values.
  - [ ] 10.6 Validate every generated sweeprun with Pydantic before records are
    created; reject malformed TOML, missing minimum fields, bad dates, bad
    types, and duplicate/conflicting final paths.
  - [ ] 10.7 Revalidate stored `config_json` when each sweeprun starts, then run
    component init checks: signalers, executor, risk, data coverage, then
    execute.
  - [x] 10.8 Create the BTCUSDT/SOLUSDT 2025-halves EMA-cross sweep template:
    2 symbols x 2 periods x fast `[5, 8, 11]` x slow `[20, 30, 50]` = 36
    sweepruns.
  - [x] 10.9 Run the sweep through the real SweepManager/process-pool path,
    fix bugs, and prove all 36 sweepruns complete or fail with specific
    boundary/component/data errors.
  - [x] 10.10 Run adversarial audits before and after implementation; accept
    correctness/proof findings and reject trivial or design-opposing findings
    with written disposition.

### [ ] 11. Strategy variations

  - [ ] 11.1 Add more coded signalers with fail-fast param validation.
  - [ ] 11.2 Add more coded executors with fail-fast param validation.
  - [ ] 11.3 Add practical template variations only after the template system
    proof is stable.

### [ ] 12. Results and charts

  - [x] 12.1 Improve sweep result calculations after template execution is
    stable.
  - [ ] 12.2 Display sweep and sweeprun results in the WebGUI.
  - [ ] 12.3 Add chart display for selected results and generated bot configs.

### [ ] 13. Profitability search

  - [ ] 13.1 Use the stable template/sweep system to search for profitable
    strategy candidates.
  - [ ] 13.2 Export strong parameter sets as concrete TOML bot/sweeprun base
    files with scalar values only.

### [ ] 14. Stable bot path

  - [ ] 14.1 Build a stable workable bot from proven templates, using
    `D:\rust\nuutrader6` as the behavior reference.
  - [ ] 14.2 Prove the bot path from simulator to testnet to mainnet.
  - [ ] 14.3 Run long-duration stability checks for days, including memory
    behavior and restart handling.

### [ ] 15. Monitoring and stability

  - [ ] 15.1 Improve monitoring after the stable bot path exists.
  - [ ] 15.2 Improve operational stability based on long-run failures and
    evidence.

## project / tooling
