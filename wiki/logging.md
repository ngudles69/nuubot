---
title: logging
created: 2026-06-21
updated: 2026-06-21
type: wiki
status: active
tags: [logging, errors, readability]
---

# logging

## objective

Logs should explain what happened in a way the user can read quickly.

User readability is the priority. If the readable shape is unclear, ask the
user.

## format

Default module-level logging:

```python
from nuubot.core.logger import logger
log = logger("workspace/logs/runtime.log")
```

Every non-definition module uses module-level logging by default.

Do not embed loggers inside normal objects:

- no passing log objects through constructors by default.

Specific owner objects like bots, sweepruns, and sweeps may use class/object
level logs when they need their own output file.

Default module logs go to `workspace/logs/runtime.log`. This catches normal
runtime/module activity.

Module-level logging is permanent.

Modules are general by default. Keep them on `workspace/logs/runtime.log`.

For specific debugging, the module-level logger may temporarily point to its
own log file, for example `workspace/logs/risk.log`. Change the file target
back to the general runtime log when that debugging pass is done, unless the
design explicitly says the module needs permanent separate logging.

Standard log line format:

```text
2026-06-21 01:18:38,393 [ INFO] process_risk
2026-06-21 01:18:38,393 [DEBUG] results:
{
  "field": 112,
  "nested": {
    "field2": "abc"
  }
}
2026-06-21 01:18:38,393 [ INFO] next message
```

Standards:

- Pad log level to five characters inside brackets.
- Log the message on the timestamp line.

Recommendations:

- Put long structured JSON on the next line when it is easier to read.
- Pretty-print long JSON with indentation when useful.
- Keep short payloads inline when that is clearer, for example BBO snapshots.
- Let the code choose the readable shape.

## error path

Use cascading error logs.

Rule:

```text
The failing owner logs the specific cause.
Each caller logs only the consequence.
Everyone re-raises.
```

Soft rule: use the function name in the failing-owner error log when it helps
identify where the error occurred:

```python
except Exception as e:
    log.error(f"load_config error: {e}")
    raise
```

This usually identifies where the error occurred without adding custom error
classes.

Example:

```text
2026-06-21 01:18:38,393 [ERROR] load_config error: invalid account
2026-06-21 01:18:38,393 [ERROR] runtime aborted.
2026-06-21 01:18:38,393 [ERROR] sweeprun aborted.
2026-06-21 01:18:38,393 [ERROR] sweep aborted.
```

Example shape:

```python
async def sweeprun(path: Path) -> SweeprunResult:
    try:
        config = load_config(path)
        meta = await load_meta(config)
        accounts = await load_accounts(config)

        runtime = Runtime(config, meta, accounts)
        await runtime.init()
        await runtime.start()
        try:
            await runtime.loop()
        finally:
            await runtime.stop()

        return runtime.result

    except Exception:
        log.error("sweeprun aborted.")
        raise
```

Keep this plain. Do not add an error decorator unless repeated real code proves
the plain `try/except` shape is painful.
