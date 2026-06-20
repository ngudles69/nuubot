---
title: object samples
created: 2026-06-20
updated: 2026-06-20
type: wiki
status: active
tags: [coding, samples, objects]
---

# object samples

## composing objects

Composing objects own and coordinate other project objects.

```python
from dataclasses import dataclass


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
        self.config = await load_config()

        # init account
        self.account = Account(self.config)
        await self.account.init()

        # init webserver
        self.webserver = Webserver(self.config)
        await self.webserver.init()

    async def start(self) -> None:
        # start account
        await self.account.start()

        # start webserver
        await self.webserver.start()

    async def loop(self) -> None:
        # run work
        while True:
            output = await self.work()
            await self.webserver.publish(output)

    async def stop(self) -> None:
        # stop webserver
        await self.webserver.stop()

        # stop account
        await self.account.stop()

    # key functions

    async def work(self) -> WorkOutput:
        # load account state
        account_state = await self.account.state()

        # build output
        return await self.format_output(account_state)

    # helpers

    async def format_output(self, account_state: AccountState) -> WorkOutput:
        # format work output
        return WorkOutput(
            value=account_state.value,
            message="ok",
        )
```

## primitive objects

Primitive objects are standalone. They depend only on libraries or plain inputs.

```python
@dataclass
class GridLevel:
    level: int
    price: float


class GridMath:
    def __init__(self, base: float, interval: float) -> None:
        self.base = base
        self.interval = interval

    async def price(self, level: int) -> float:
        return self.base * (1 + self.interval) ** level

    async def level(self, level: int) -> GridLevel:
        return GridLevel(
            level=level,
            price=await self.price(level),
        )
```

## creation

Create objects directly.

```python
obj = Thing()
await obj.init()
await obj.start()
```

## avoid

```python
obj = create_thing(...)


class GridPriceFactory:
    def create(self, config):
        return GridPriceCalculator(config)
```
