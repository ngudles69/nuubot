---
title: data objects
created: 2026-06-23
updated: 2026-06-23
type: wiki
status: active
tags: [design, objects, data, websocket, filedata, meta]
---

# data objects

## purpose

`WsData` owns websocket market data.

`FileData` owns historical file data.

Meta reads and latest exchange reference data belong here as helper methods
unless Account needs account-specific exchange access.

## interfaces

External commands:

- `init()`
- `start()`
- `stop()`
- `snapshot(at=None)`
- `history(interval, count)`
- `latest_meta()`

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
- meta helper results when needed.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Config. | Initialized data object. | Validates feed/file config. Does not start live streaming. |
| `start()` | Initialized data object. | Running data object. | Starts websocket or prepares file replay. Live path must pass readiness checks. |
| `stop()` | Running data object. | Stopped data object. | Closes live resources or clears replay runtime state. |
| `snapshot(at=None)` | Optional live/replay time. | Market snapshot. | Live `at=None` returns latest available. Backtest `at=<time>` returns only data available at that replay time. |
| `history(interval, count)` | Interval and required count. | Historical bars. | Returns enough closed history or fails loud if unavailable. |
| `latest_meta()` | Venue/symbol context. | Latest reference/meta data. | Returns latest known meta helper data when data owns the read. |
| `replay_batches()` | Prepared historical data. | Ordered replay batches. | Backtest only. Batches are timestamp ordered and same-timestamp events are grouped. |
| `ingest_replay_batch(batch)` | One replay batch. | Updated snapshot state. | Backtest only. Ingests every event before runtime dispatch. |

## processing

Internal functions:

- connect websocket.
- subscribe to BBO/candles.
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
- meta reader.
- historical file locator.
- closed-candle detector.
- same-timestamp batch merger.

## notes

- Runtime asks for snapshots; it does not parse data feeds.
- Backtest data must avoid future leakage.
- Live and backtest expose the same snapshot shape.
- `at=None` means latest available live data. `at=<replay time>` means data
  available at that replay timestamp.
