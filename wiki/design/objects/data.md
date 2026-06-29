---
title: data objects
created: 2026-06-23
updated: 2026-06-29
type: wiki
status: active
tags: [design, objects, data, websocket, filedata, meta]
---

# data objects

## purpose

Bot-local data objects own live websocket market data first.

`WsData` is the bot-facing live data object. In the first design it opens and
maintains the bot's own websocket/feed client.

`FileData` owns historical file data.

Exchange meta is loaded by `Nuubot`/`ExchangeMeta` from the server DB. Data
objects may receive already-loaded meta, but they do not own meta persistence.

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `snapshot(at=None)`
- `history(interval, count)`

`FileData` also exposes:

- `replay_batches()`
- `ingest_replay_batch(batch)`

Data objects receive:

- config.
- runtime clock time.
- websocket messages or historical files.

Data objects output:

- latest BBO.
- candle bars.
- historical bars.
- replay batches.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Config. | Initialized data object. | Validates feed/file config. Does not start live streaming. |
| `start()` | Initialized data object. | Running data object. | Starts websocket or prepares file replay. Live path must pass readiness checks. |
| `stop()` | Running data object. | Stopped data object. | Closes live resources or clears replay runtime state. |
| `snapshot(at=None)` | Optional live/replay time. | Market snapshot. | Live `at=None` returns latest available. Backtest `at=<time>` returns only data available at that replay time. |
| `history(interval, count)` | Interval and required count. | Historical bars. | Returns enough closed history or fails loud if unavailable. |
| `replay_batches()` | Prepared historical data. | Ordered replay batches. | Backtest only. Batches are timestamp ordered and same-timestamp events are grouped. |
| `ingest_replay_batch(batch)` | One replay batch. | Updated snapshot state. | Backtest only. Ingests every event before runtime dispatch. |

## processing

Internal functions:

- open bot-local websocket/feed subscriptions.
- validate BBO readiness.
- load historical files.
- derive higher intervals.
- group replay events by timestamp.
- expose only data available at current runtime time.
- keep BBO latest-only.
- keep bars keyed by interval and timestamp.
- reject impossible or malformed market rows.

## key helpers

- BBO validator.
- candle parser.
- interval converter.
- replay batch grouper.
- historical file locator.
- closed-candle detector.
- same-timestamp batch merger.

## notes

- Runtime asks for snapshots; it does not parse data feeds.
- Shared DataEngines are a later optimization only after per-bot feeds fail
  against a measured exchange limit, bandwidth, CPU, or fanout problem.
- Do not add Redis or a shared websocket server first.
- Backtest data must avoid future leakage.
- Live and backtest expose the same snapshot shape.
- `at=None` means latest available live data. `at=<replay time>` means data
  available at that replay timestamp.
