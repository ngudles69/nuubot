from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nuubot import Nuubot
from nuubot.core.config import load_botrun_config
from nuubot.datastore import BotRow, CommandRow, Datastore


CONFIGURED = "configured"
PENDING = "pending"


def main() -> None:
    args = parse_args()
    nuubot = Nuubot().setup()
    try:
        run_command(nuubot.datastore, args)
    finally:
        # Close the bot catalog.
        nuubot.stop()


def run_command(store: Datastore, args: argparse.Namespace) -> None:
    if args.command == "create":
        row = create_bot(store, Path(args.file))
        print_json({"bot_id": row.bot_id, "status": row.status})
        return
    if args.command == "delete":
        delete_bot(store, args.bot_id)
        print_json({"bot_id": args.bot_id, "deleted": True})
        return
    if args.command == "clone":
        row = clone_bot(store, args.bot_id)
        print_json({"bot_id": row.bot_id, "status": row.status})
        return
    if args.command == "view":
        print_json(view_bot(store, args.bot_id))
        return
    if args.command == "ping":
        print_json(ping_bot(store, args.bot_id))
        return
    if args.command == "stop":
        row = add_command(store, args.bot_id, "stop")
        print_json({"command_id": row.command_id, "status": row.status})
        return
    if args.command == "start":
        raise RuntimeError("start is not wired to runtime yet")
    raise RuntimeError(f"unsupported command: {args.command}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="nuubot-cli")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("-f", "--file", required=True)

    delete = sub.add_parser("delete")
    delete.add_argument("bot_id", type=int)

    clone = sub.add_parser("clone")
    clone.add_argument("bot_id", type=int)

    start = sub.add_parser("start")
    start.add_argument("bot_id", type=int)

    stop = sub.add_parser("stop")
    stop.add_argument("bot_id", type=int)

    view = sub.add_parser("view")
    view.add_argument("bot_id", type=int, nargs="?")

    ping = sub.add_parser("ping")
    ping.add_argument("bot_id", type=int)

    return parser.parse_args()


def print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def create_bot(store: Datastore, config_path: Path) -> BotRow:
    bot_config = load_botrun_config(config_path)
    row = BotRow(
        status=CONFIGURED,
        config_json=bot_config.model_dump_json(indent=2),
        pid=None,
        run_token=None,
        started_at=None,
        last_seen_at=None,
        stopped_at=None,
    )
    with store.session() as session:
        session.add(row)
        session.commit()
        return row


def delete_bot(store: Datastore, bot_id: int) -> None:
    with store.session() as session:
        row = require_bot(session, bot_id)
        if row.status != CONFIGURED:
            raise RuntimeError(f"delete requires status={CONFIGURED}, got {row.status}")
        session.delete(row)
        session.commit()


def clone_bot(store: Datastore, bot_id: int) -> BotRow:
    with store.session() as session:
        source = require_bot(session, bot_id)
        row = BotRow(
            status=CONFIGURED,
            config_json=source.config_json,
            pid=None,
            run_token=None,
            started_at=None,
            last_seen_at=None,
            stopped_at=None,
        )
        session.add(row)
        session.commit()
        return row


def view_bot(store: Datastore, bot_id: int | None = None) -> list[dict[str, Any]]:
    with store.session() as session:
        if bot_id is None:
            rows = session.scalars(select(BotRow).order_by(BotRow.bot_id)).all()
        else:
            rows = [require_bot(session, bot_id)]
        return [bot_to_json(row) for row in rows]


def add_command(store: Datastore, bot_id: int, command: str, payload: dict[str, Any] | None = None) -> CommandRow:
    with store.session() as session:
        require_bot(session, bot_id)
        row = CommandRow(
            bot_id=bot_id,
            command=command,
            payload_json=json.dumps(payload or {}, sort_keys=True),
            status=PENDING,
            command_ts=now_ms(),
        )
        session.add(row)
        session.commit()
        return row


def ping_bot(store: Datastore, bot_id: int) -> dict[str, Any]:
    with store.session() as session:
        row = require_bot(session, bot_id)
        return {
            "bot_id": row.bot_id,
            "status": row.status,
            "pid": row.pid,
            "run_token": row.run_token,
            "last_seen_at": row.last_seen_at,
        }


def require_bot(session: Session, bot_id: int) -> BotRow:
    row = session.get(BotRow, bot_id)
    if row is None:
        raise RuntimeError(f"bot not found: {bot_id}")
    return row


def bot_to_json(row: BotRow) -> dict[str, Any]:
    return {
        "bot_id": row.bot_id,
        "status": row.status,
        "config": json.loads(row.config_json),
        "pid": row.pid,
        "run_token": row.run_token,
        "started_at": row.started_at,
        "last_seen_at": row.last_seen_at,
        "stopped_at": row.stopped_at,
    }


def now_ms() -> int:
    return int(time.time() * 1000)
