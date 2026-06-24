from __future__ import annotations

import argparse
import json
from pathlib import Path

from nuubot.config import Config
from nuubot.datastore import Datastore


def main() -> None:
    args = parse_args()
    config = Config(Path("workspace/config/config.toml")).load()
    store = Datastore(config)

    # Open the bot catalog.
    store.init()
    try:
        store.start()
        run_command(store, args)
    finally:
        # Close the bot catalog.
        store.stop()


def run_command(store: Datastore, args: argparse.Namespace) -> None:
    if args.command == "create":
        row = store.create_bot(Path(args.file))
        print_json({"bot_id": row.bot_id, "status": row.status})
        return
    if args.command == "delete":
        store.delete_bot(args.bot_id)
        print_json({"bot_id": args.bot_id, "deleted": True})
        return
    if args.command == "clone":
        row = store.clone_bot(args.bot_id)
        print_json({"bot_id": row.bot_id, "status": row.status})
        return
    if args.command == "view":
        print_json(store.view_bot(args.bot_id))
        return
    if args.command == "ping":
        print_json(store.ping(args.bot_id))
        return
    if args.command == "stop":
        row = store.command(args.bot_id, "stop")
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
