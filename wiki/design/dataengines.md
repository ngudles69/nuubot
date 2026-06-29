---
title: dataengines design
created: 2026-06-29
updated: 2026-06-29
type: wiki
status: active
tags: [design, server, dataengines, websocket]
---

# dataengines design

## purpose

DataEngines are the optional shared websocket/feed service.

They are not the first live-bot design. The first design is bot-local
websocket/feed clients inside each BotRuntime.

Use this page only if per-bot feeds become insufficient.

## owns

- lazy websocket connection on first use.
- reconnect loop.
- subscription tracking.
- latest BBO buffers.
- candle buffers.
- data health/status.

## does not own

- bot runtime decisions.
- signaler/risk/executor logic.
- order execution.
- historical file replay.
- managed process lifecycle.
- normal first-pass live bot feeds.

## interfaces

External functions:

- `init()`
- `start()`
- `stop()`
- `subscribe_bbo(symbol, data_network)`
- `subscribe_candles(symbol, interval, data_network)`
- `unsubscribe_bbo(symbol, data_network)`
- `unsubscribe_candles(symbol, interval, data_network)`
- `snapshot(symbol, intervals, data_network)`
- `status()`

## contracts

| Function | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Server config. | Initialized DataEngines. | Does not connect websockets yet. |
| `start()` | Initialized DataEngines. | Ready service. | Starts service state. Connection remains lazy. |
| `stop()` | Running DataEngines. | Stopped service. | Closes websockets and clears runtime tasks. |
| `subscribe_bbo(...)` | Symbol/network. | Subscription active. | Opens websocket lazily if needed and tracks subscription count. |
| `subscribe_candles(...)` | Symbol/interval/network. | Subscription active. | Opens websocket lazily if needed and tracks subscription count. |
| `unsubscribe_bbo(...)` | Symbol/network. | Subscription removed. | Removes or decrements subscription. |
| `unsubscribe_candles(...)` | Symbol/interval/network. | Subscription removed. | Removes or decrements subscription. |
| `snapshot(...)` | Symbol/intervals/network. | Latest market snapshot. | Returns latest known data or fails loud when required data is unavailable. |
| `status()` | None. | JSON-safe status. | Reports connection, reconnect count, subscriptions, and last error. |

## process rule

DataEngines are not managed processes first and are not Server-owned first.

Add a shared DataEngine only if bot-local websocket clients fail against a
measured exchange limit, bandwidth, CPU, or fanout problem.

Move a shared DataEngine to its own process only if the shared service itself
needs crash isolation, placement, or multi-machine fanout.
