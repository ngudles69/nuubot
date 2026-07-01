# AGENTS.md

Rules for agents working in `D:\rust\nuubot\workspace\data`.

## Source

- Binance public data archive:
  `https://data.binance.vision/`
- Binance public-data docs:
  `https://github.com/binance/binance-public-data`

Use direct URLs. Do not rediscover this source each month.

Monthly kline file:

```text
https://data.binance.vision/data/spot/monthly/klines/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{YYYY-MM}.zip
```

Daily kline file:

```text
https://data.binance.vision/data/spot/daily/klines/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{YYYY-MM-DD}.zip
```

Checksum file is the same URL with `.CHECKSUM` appended.

## Local Layout

Keep the Binance layout under:

```text
D:\rust\nuubot\workspace\data\binance\raw\spot\monthly\klines\{SYMBOL}\{INTERVAL}\
D:\rust\nuubot\workspace\data\binance\raw\spot\daily\klines\{SYMBOL}\{INTERVAL}\
```

Keep all three files when available:

```text
{SYMBOL}-{INTERVAL}-{PERIOD}.zip
{SYMBOL}-{INTERVAL}-{PERIOD}.zip.CHECKSUM
{SYMBOL}-{INTERVAL}-{PERIOD}.csv
```

## Current Scope

Current location:

```text
D:\rust\nuubot\workspace\data
```

Tracked symbols:

```text
BNBUSDT
BTCUSDT
DOGEUSDT
ETHUSDT
HYPERUSDT
LINKUSDT
PAXGUSDT
SOLUSDT
TRUMPUSDT
```

Tracked intervals:

```text
1m
15m
1h
4h
1d
```

## Current Inventory

Inventory as of 2026-07-01. Ranges are based on local Binance ZIP filenames.
Each range means monthly files are present through 2026-05 and daily files fill
2026-06-01 through 2026-06-30.

BTCUSDT

```text
1m:  2017-08 to 2026-06-30
15m: 2017-08 to 2026-06-30
1h:  2017-08 to 2026-06-30
4h:  2017-08 to 2026-06-30
1d:  2017-08 to 2026-06-30
```

ETHUSDT

```text
1m:  2017-08 to 2026-06-30
15m: 2017-08 to 2026-06-30
1h:  2017-08 to 2026-06-30
4h:  2017-08 to 2026-06-30
1d:  2017-08 to 2026-06-30
```

BNBUSDT

```text
1m:  2017-11 to 2026-06-30
15m: 2017-11 to 2026-06-30
1h:  2017-11 to 2026-06-30
4h:  2017-11 to 2026-06-30
1d:  2017-11 to 2026-06-30
```

DOGEUSDT

```text
1m:  2019-07 to 2026-06-30
15m: 2019-07 to 2026-06-30
1h:  2019-07 to 2026-06-30
4h:  2019-07 to 2026-06-30
1d:  2019-07 to 2026-06-30
```

LINKUSDT

```text
1m:  2019-01 to 2026-06-30
15m: 2019-01 to 2026-06-30
1h:  2019-01 to 2026-06-30
4h:  2019-01 to 2026-06-30
1d:  2019-01 to 2026-06-30
```

SOLUSDT

```text
1m:  2020-08 to 2026-06-30
15m: 2020-08 to 2026-06-30
1h:  2020-08 to 2026-06-30
4h:  2020-08 to 2026-06-30
1d:  2020-08 to 2026-06-30
```

PAXGUSDT

```text
1m:  2020-08 to 2026-06-30
15m: 2020-08 to 2026-06-30
1h:  2020-08 to 2026-06-30
4h:  2020-08 to 2026-06-30
1d:  2020-08 to 2026-06-30
```

TRUMPUSDT

```text
1m:  2025-01 to 2026-06-30
15m: 2025-01 to 2026-06-30
1h:  2025-01 to 2026-06-30
4h:  2025-01 to 2026-06-30
1d:  2025-01 to 2026-06-30
```

HYPERUSDT

```text
1m:  2025-04 to 2026-06-30
15m: 2025-04 to 2026-06-30
1h:  2025-04 to 2026-06-30
4h:  2025-04 to 2026-06-30
1d:  2025-04 to 2026-06-30
```

These Binance spot klines are local historical data for assets that are
tradable as Hyperliquid perps.

Notes:

- `HYPEUSDT` has no Binance public-data archive as of 2026-07-01.
- `XAUTUSDT` has Binance data but is not in the Hyperliquid perp universe as of
  2026-07-01. Do not add it unless explicitly asked.
- PAXG is gold-backed by Paxos, so XAUT is not required just to identify PAXG as
  gold-linked.
- Do not add symbols, intervals, markets, or futures data unless explicitly
  asked.

## Monthly Update

Binance publishes daily files the next day. Monthly files are expected at the
first Monday of the next month.

At the start of each month:

1. Check the previous month's monthly ZIP for every tracked symbol and interval.
2. If the monthly ZIP exists, download the ZIP and `.CHECKSUM`, verify SHA256,
   then extract the CSV with overwrite.
3. If the monthly ZIP does not exist yet, update the previous month's daily
   files through the latest available date.
4. Keep daily files for the latest partial month. Do not waste time rechecking
   old missing history unless asked.

## PowerShell Pattern

Check one monthly file:

```powershell
$symbol='BTCUSDT'
$interval='1m'
$month='2026-06'
$url="https://data.binance.vision/data/spot/monthly/klines/$symbol/$interval/$symbol-$interval-$month.zip"
Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 30
```

Download, verify, and extract one file:

```powershell
$dir="D:\rust\nuubot\workspace\data\binance\raw\spot\monthly\klines\$symbol\$interval"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$zip=Join-Path $dir "$symbol-$interval-$month.zip"
$sum=Join-Path $dir "$symbol-$interval-$month.zip.CHECKSUM"
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 60
Invoke-WebRequest -Uri "$url.CHECKSUM" -OutFile $sum -UseBasicParsing -TimeoutSec 60
$expected=((Get-Content -LiteralPath $sum -Raw).Trim() -split '\s+')[0].ToUpperInvariant()
$actual=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToUpperInvariant()
if($expected -ne $actual){ throw "checksum mismatch: $zip" }
Expand-Archive -LiteralPath $zip -DestinationPath $dir -Force
```

For daily files, use the daily URL pattern and replace `$month` with a date like
`2026-06-30`.

## After Updating

Inventory the latest month:

```powershell
$root='D:\rust\nuubot\workspace\data\binance\raw\spot\daily\klines'
Get-ChildItem -LiteralPath $root -Filter '*-2026-06-*.zip' -File -Recurse |
  Group-Object DirectoryName |
  Select-Object Name,Count
```

Checksum verification must pass before the update is considered done.
