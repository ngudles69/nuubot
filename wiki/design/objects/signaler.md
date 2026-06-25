---
title: signaler object
created: 2026-06-23
updated: 2026-06-25
type: wiki
status: active
tags: [design, objects, signaler, indicators]
---

# signaler object

## purpose

Signaler owns signal production.

Signaler owns an ensemble of indicators. Each indicator produces raw
indicator-specific rows. Signaler interprets those rows and produces one
standard trading signal.

Code layout target:

```text
nuubot/signaler/
  signaler.py
  emacross/
    emacross.py
  startnow.py
```

Do not add deeper folders until a real signaler needs them.

## interfaces

External commands:

- `init()`
- `start(data)`
- `stop()`
- `observe(snapshot)`
- `loop_once()`
- `exit()`
- `telemetry()`

Signaler receives:

- config.
- history from data object.
- BBO/candle input from Runtime.

Signaler outputs:

- signal state.
- entry/exit/hold consensus.
- reason string.
- required history count.
- freshness/missing-data diagnostics.

Indicator commands:

- `init(config)`
- `seed(data)`
- `ingest(data, partial=False)`
- `row(at=None, partial=False)`

Indicator rows are raw and indicator-specific. Each row must include the row
timestamp and data payload. The payload can be scalar, tuple, dict, dataclass,
or any shape the owning Signaler understands.

## contracts

| Interface | Input | Output | Contract |
| --- | --- | --- | --- |
| `init()` | Signaler config. | Initialized Signaler. | Builds indicator ensemble and validates signaler-level rules. |
| `start(data)` | Data object/history source. | Seeded Signaler. | Seeds every owned indicator or child signaler. Fails loud if required seed data is missing. |
| `stop()` | Running Signaler. | Stopped Signaler. | Stops owned indicators and releases owned resources. |
| `observe(snapshot)` | Market snapshot. | Boolean new-signalable data state. | Filters usable bars, rejects stale/duplicate closed bars, and records progress for Runtime telemetry. |
| `loop_once()` | Previously observed usable market data. | Standardized Signal decision. | Runs owned signalers/indicators and applies signal priority/consensus. Runtime does not loop over child signalers. |
| `exit()` | Current signaler state. | Boolean. | Returns whether Signaler requests runtime stop. |
| `telemetry()` | Current signaler state. | JSON-safe telemetry. | Returns indicator diagnostics, freshness state, and consensus data. |
| `Indicator.init(config)` | Indicator config. | Initialized Indicator. | Validates indicator config and prepares empty state. |
| `Indicator.seed(data)` | Initial data. | Seeded Indicator. | Calculates initial state. Full-history seed and required-window seed must produce the same row values. |
| `Indicator.ingest(data, partial=False)` | New or revised data. | Updated Indicator. | Adds records or updates the open partial record, then recalculates affected state. |
| `Indicator.row(at=None, partial=False)` | Optional time and partial flag. | Indicator row with `ts` and `data`. | Returns raw indicator-specific row. Does not decide trading meaning or freshness policy. |

## processing

Internal functions:

- validate signaler params.
- initialize all indicators.
- seed all indicators.
- select usable bars from the runtime market snapshot.
- ingest new data into all relevant indicators.
- assess each indicator.
- combine indicator assessments into consensus.
- expose one signal result to Runtime/Executor.
- apply stale/missing-data policy per indicator.
- record signal diagnostics.

Indicator row rule:

- `row(at=None, partial=False)` returns the latest closed row.
- `row(at=None, partial=True)` returns the latest row, even if the row is still
  partial/open.
- `row(at=<time>, partial=False)` returns the latest closed row at or before
  that time.
- `row(at=<time>, partial=True)` returns the latest row at or before that time,
  including partial/open rows.
- Default is `partial=False`; closed-row reads are the normal and safe path.
- Partial reads are explicit because they can change before the candle closes.
- Returned rows must expose `ts` and `data`.
- Live and backtest use the same API.
- In live mode, `at=None` means latest available data.
- In backtest mode, `at=<replay time>` means read as if runtime is at that
  replay timestamp.
- Backtest signalers must pass replay time through `at` and must default to
  `partial=False` to avoid future/open-candle leakage.

Freshness rule:

- Indicator exposes timestamped rows.
- Signaler owns stale-data and missing-data policy.
- Market indicators can be strict, for example reject a 4h row that is days old.
- Social, news, or economic indicators can be lenient or use validity windows
  that depend on how the Signaler interprets them.
- If stale/missing data would make the signal unsafe, fail loud instead of
  silently using stale state.

## key helpers

- indicator loader.
- required-bars calculator.
- indicator assessment.
- consensus function.
- freshness policy.
- missing-data policy.
- signal reason builder.
- indicator diagnostics builder.

## notes

- Runtime should not know indicator internals.
- Runtime talks to one `Signaler`, not many signalers.
- Signaler owns all indicator loading and interpretation.
- Signaler owns child-signal/indicator eligibility, seeding, and signal
  priority. Runtime only asks whether signalable data exists and then asks for
  one decision.
- Start with simple signalers; split deeper only when the object grows.
- Indicator does not return a standardized trading signal. Signaler converts
  indicator rows into one standardized signal.
