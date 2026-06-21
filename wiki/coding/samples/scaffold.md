---
title: scaffold samples
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [coding, samples, scaffold]
---

# scaffold samples

## rules

- A scaffold sample must be a valid runnable Python file.
- The user and AI must be able to observe what the program does or should do.
- Comments state intent.
- Logs are not 1:1 with code.
- Logs verify ordering, clarify intent, and add reminders.
- Logs can expand into multiple implementation lines.
- Keep the log when it anchors design intent.
- Logs are not mandatory code to paste into every implementation.
- Use logs only when they help the AI or user verify the loop.
- Keep logs sparse. Do not flood the file.

## async object file

```python
from dataclasses import dataclass

from core.logger import logger


log = logger("workspace/logs/runtime.log")


@dataclass
class WorkOutput:
    value: float
    message: str


class Thing:
    def __init__(self) -> None:
        self.config = None
        self.account = None
        self.webserver = None

    async def init(self) -> None:
        # load config
        log.debug("load config")
        self.config = await load_config()
        if not pydantic_check(self.config):
            raise ValueError("invalid config")

        # init account
        log.debug("load account")
        self.account = Account(self.config)
        await self.account.init()

        # init webserver
        log.debug("load webserver")
        self.webserver = Webserver(self.config)
        await self.webserver.init()

    async def start(self) -> None:
        # start account
        log.debug("connect to Hyperliquid using async_hyperliquid")
        await self.account.start()

        # start webserver
        log.debug("start server at localhost:1234")
        await self.webserver.start()

    async def loop(self) -> None:
        # run work
        while True:
            log.info("get BBO ticks via /info")
            output = await self.work()
            await self.webserver.publish(output)

    async def stop(self) -> None:
        # stop webserver
        log.debug("stop webserver in reverse order")
        await self.webserver.stop()

        # stop account
        log.debug("stop account")
        await self.account.stop()

    # key functions

    async def work(self) -> WorkOutput:
        # load account state
        log.debug("load account per config")
        account_state = await self.account.state()

        # evaluate exits
        log.debug("eval stop loss exit")

        # evaluate entries
        log.debug("eval stop loss entry")

        # build output
        log.debug("output account balance and position")
        return await self.format_output(account_state)

    # helpers

    async def format_output(self, account_state: AccountState) -> WorkOutput:
        # format fields
        log.debug("format output one row per item")
        return WorkOutput(
            value=account_state.value,
            message="ok",
        )
```
