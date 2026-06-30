from __future__ import annotations

from datetime import datetime
from typing import Any

from nuubot.core.dtypes import Bar


def format_ms(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def format_bar(bar: Bar) -> str:
    return f"[o:{bar.open} h:{bar.high} l:{bar.low} c:{bar.close} v:{bar.volume} closed:{str(bar.closed).lower()}]"


def format_bbo(data: dict[str, Any]) -> str:
    bbo = data.get("bbo")
    if not isinstance(bbo, list) or len(bbo) < 2:
        return str(data)
    bid = bbo[0]
    ask = bbo[1]
    return f"[bid:{bid.get('px')} bid_sz:{bid.get('sz')} bid_n:{bid.get('n')} ask:{ask.get('px')} ask_sz:{ask.get('sz')} ask_n:{ask.get('n')}]"
