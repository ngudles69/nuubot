from __future__ import annotations

import argparse

from nuubot import nuubot_setup
from nuubot.datastore import Datastore


def main() -> None:
    args = parse_args()
    if args.command == "tui":
        from nuubot.cli.tui import main as tui_main
        tui_main()
        return
    if args.command == "report":
        from nuubot.cli.sweeps.report import print_report
        print_report(args.sweep_id)
        return
    nuubot = nuubot_setup()
    try:
        run_command(nuubot.datastore, args)
    finally:
        nuubot.stop()


def run_command(store: Datastore, args: argparse.Namespace) -> None:
    _ = store
    raise RuntimeError(f"{args.command} is not wired to BotManager yet")


def parse_args() -> argparse.Namespace:
    """Parse CLI command arguments."""

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

    sub.add_parser("tui")

    report = sub.add_parser("report")
    report.add_argument("sweep_id", type=int)

    return parser.parse_args()
