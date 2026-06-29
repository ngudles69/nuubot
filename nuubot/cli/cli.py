from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nuubot import nuubot_setup
from nuubot.core.config import load_botrun_config
from nuubot.core.dtypes import Mode
from nuubot.datastore import BotCatalogRow, BotRow, Datastore


CONFIGURED = "configured"


def main() -> None:
    args = parse_args()
    nuubot = nuubot_setup()
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
        raise RuntimeError("stop is not wired to Ray actor commands yet")
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


def create_bot(store: Datastore, config_path: Path) -> BotCatalogRow:
    bot_config = load_botrun_config(config_path)
    sequence_name = bot_sequence_name(bot_config.runtime.mode)
    bot_id = store.next_sequence(sequence_name)
    db_path = store.server_path.parent / f"{sequence_name}_{bot_id}.db"
    store.init_bot(db_path)
    with store.session(db_path) as session:
        session.merge(BotRow(
            bot_key="bot",
            status=CONFIGURED,
            config_json=bot_config.model_dump_json(indent=2),
        ))
        session.commit()
    row = BotCatalogRow(
        bot_id=bot_id,
        exec_network=bot_exec_network(bot_config.runtime.mode),
        db_path=db_path.as_posix(),
        status=CONFIGURED,
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


def clone_bot(store: Datastore, bot_id: int) -> BotCatalogRow:
    with store.session() as session:
        source = require_bot(session, bot_id)
        source_exec_network = source.exec_network
        source_db_path = source.db_path
    with store.session(Path(source_db_path)) as source_session:
        source_bot = source_session.get(BotRow, "bot")
        if source_bot is None:
            raise RuntimeError(f"source bot DB missing bot row: {bot_id}")
        config_json = source_bot.config_json
    config_data = json.loads(config_json)
    sequence_name = bot_sequence_name(Mode(config_data["runtime"]["mode"]))
    new_bot_id = store.next_sequence(sequence_name)
    db_path = store.server_path.parent / f"{sequence_name}_{new_bot_id}.db"
    store.init_bot(db_path)
    with store.session(db_path) as bot_session:
        bot_session.merge(BotRow(bot_key="bot", status=CONFIGURED, config_json=config_json))
        bot_session.commit()
    row = BotCatalogRow(
        bot_id=new_bot_id,
        exec_network=source_exec_network,
        db_path=db_path.as_posix(),
        status=CONFIGURED,
        run_token=None,
        started_at=None,
        last_seen_at=None,
        stopped_at=None,
    )
    with store.session() as session:
        session.add(row)
        session.commit()
        return row


def view_bot(store: Datastore, bot_id: int | None = None) -> list[dict[str, Any]]:
    with store.session() as session:
        if bot_id is None:
            rows = session.scalars(select(BotCatalogRow).order_by(BotCatalogRow.bot_id)).all()
        else:
            rows = [require_bot(session, bot_id)]
        return [bot_to_json(row) for row in rows]


def ping_bot(store: Datastore, bot_id: int) -> dict[str, Any]:
    with store.session() as session:
        row = require_bot(session, bot_id)
        return {
            "bot_id": row.bot_id,
            "status": row.status,
            "actor_id": row.actor_id,
            "run_token": row.run_token,
            "last_seen_at": row.last_seen_at,
        }


def require_bot(session: Session, bot_id: int) -> BotCatalogRow:
    row = session.get(BotCatalogRow, bot_id)
    if row is None:
        raise RuntimeError(f"bot not found: {bot_id}")
    return row


def bot_to_json(row: BotCatalogRow) -> dict[str, Any]:
    return {
        "bot_id": row.bot_id,
        "exec_network": row.exec_network,
        "db_path": row.db_path,
        "status": row.status,
        "actor_id": row.actor_id,
        "run_token": row.run_token,
        "started_at": row.started_at,
        "last_seen_at": row.last_seen_at,
        "stopped_at": row.stopped_at,
    }


def bot_sequence_name(mode: Mode) -> str:
    if mode == Mode.MAINNET:
        return "mainnet_bot"
    if mode == Mode.TESTNET:
        return "testnet_bot"
    if mode == Mode.SIMNET:
        return "simnet_bot"
    if mode == Mode.BACKTEST:
        return "backtest_bot"
    raise RuntimeError(f"unsupported bot mode for catalog create: {mode}")


def bot_exec_network(mode: Mode) -> str:
    if mode == Mode.MAINNET:
        return "mainnet"
    if mode == Mode.TESTNET:
        return "testnet"
    if mode in {Mode.SIMNET, Mode.BACKTEST}:
        return "simnet"
    raise RuntimeError(f"unsupported bot mode for catalog create: {mode}")
