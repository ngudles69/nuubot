from __future__ import annotations

from time import monotonic
from typing import Any

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header, Static

from nuubot.datastore import BotRow
from nuubot.nuubot import Nuubot, nuubot_setup
from nuubot.server.sweepmgr import SweepManager, sweepmgr_setup


class NuubotTui(App[None]):
    CSS = """
    #title {
        padding: 0 1;
        text-style: bold;
    }
    #hint {
        color: $text-muted;
        padding: 0 1;
    }
    #detail {
        height: 9;
        padding: 1;
        border: solid $primary;
    }
    DataTable {
        height: 1fr;
    }
    """
    BINDINGS = [
        ("s", "show_sweeps", "Sweeps"),
        ("b", "show_bots", "Bots"),
        ("escape", "show_home", "Back"),
        ("enter", "select", "Open"),
        ("r", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.bot: Nuubot | None = None
        self.sweepmgr: SweepManager | None = None
        self.screen_name = "home"
        self.row_keys: list[str] = []
        self.prefix = ""
        self.prefix_ts = 0.0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="title")
        yield Static("", id="hint")
        yield DataTable(id="table")
        yield Static("", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self.bot = nuubot_setup()
        self.sweepmgr = sweepmgr_setup(self.bot)
        self.action_show_home()

    def on_unmount(self) -> None:
        if self.bot is not None:
            self.bot.stop()

    @property
    def table(self) -> DataTable:
        return self.query_one("#table", DataTable)

    @property
    def detail(self) -> Static:
        return self.query_one("#detail", Static)

    def action_show_home(self) -> None:
        self.screen_name = "home"
        self.set_title("Nuubot")
        self.set_hint("Press s for sweeps, b for bots, Enter to open, q to quit.")
        self.set_table(("key", "menu"), [("s", "sweeps"), ("b", "bots")], ["s", "b"])
        self.detail.update("Select a menu.")

    def action_show_sweeps(self) -> None:
        self.screen_name = "sweeps"
        self.set_title("Sweeps")
        self.set_hint("Digits jump by sweep id prefix. Enter opens details. r refreshes. Esc returns home.")
        rows = self.sweep_rows()
        self.set_table(("id", "status", "progress", "win/loss", "pf", "ev", "updated"), rows, [str(row[0]) for row in rows])
        self.detail.update("Select a sweep.")

    def action_show_bots(self) -> None:
        self.screen_name = "bots"
        self.set_title("Bots")
        self.set_hint("Digits jump by bot id prefix. Enter opens details. r refreshes. Esc returns home.")
        rows = self.bot_rows()
        self.set_table(("id", "status", "updated"), rows, [str(row[0]) for row in rows])
        self.detail.update("Select a bot.")

    def action_refresh(self) -> None:
        if self.screen_name == "sweeps":
            self.action_show_sweeps()
        elif self.screen_name == "bots":
            self.action_show_bots()
        else:
            self.action_show_home()

    def action_select(self) -> None:
        selected = self.selected_key()
        if selected is None:
            return
        if self.screen_name == "home":
            if selected == "s":
                self.action_show_sweeps()
            elif selected == "b":
                self.action_show_bots()
        elif self.screen_name == "sweeps":
            self.show_sweep_detail(int(selected))
        elif self.screen_name == "bots":
            self.detail.update(f"bot_id={selected}\nBot actions are not wired yet.")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_select()
        event.stop()

    def on_key(self, event) -> None:
        char = event.character
        if char is None:
            return
        if self.screen_name in {"sweeps", "bots"} and char.isdigit():
            self.jump_prefix(char)
            event.stop()

    def jump_prefix(self, char: str) -> None:
        now = monotonic()
        self.prefix = char if now - self.prefix_ts > 0.8 else self.prefix + char
        self.prefix_ts = now
        for index, key in enumerate(self.row_keys):
            if key.startswith(self.prefix):
                self.table.move_cursor(row=index, column=0)
                self.detail.update(f"jump: {self.prefix}")
                return
        self.detail.update(f"no id starts with {self.prefix}")

    def selected_key(self) -> str | None:
        if not self.row_keys:
            return None
        row = self.table.cursor_coordinate.row
        if row < 0 or row >= len(self.row_keys):
            return None
        return self.row_keys[row]

    def set_title(self, value: str) -> None:
        self.query_one("#title", Static).update(value)

    def set_hint(self, value: str) -> None:
        self.query_one("#hint", Static).update(value)

    def set_table(self, columns: tuple[str, ...], rows: list[tuple[Any, ...]], keys: list[str]) -> None:
        table = self.table
        table.clear(columns=True)
        table.cursor_type = "row"
        self.row_keys = keys
        for column in columns:
            table.add_column(column)
        for key, row in zip(keys, rows, strict=True):
            table.add_row(*row, key=key)
        table.focus()

    def sweep_rows(self) -> list[tuple[object, ...]]:
        if self.sweepmgr is None:
            raise RuntimeError("sweep manager missing")
        rows = self.sweepmgr.list()["sweeps"]
        return [
            (
                row["sweep_id"],
                row["status"],
                row["progress"],
                row["win_loss"],
                row["profit_factor"],
                row["ev"],
                row["updated_at"],
            )
            for row in rows
        ]

    def bot_rows(self) -> list[tuple[object, ...]]:
        if self.bot is None or self.bot.datastore is None:
            raise RuntimeError("nuubot datastore missing")
        if self.bot.datastore.dbroot is None:
            raise RuntimeError("datastore DB root missing")
        bot_rows = []
        for path in sorted(self.bot.datastore.dbroot.glob("*_bot_*.db")):
            rows = self.bot.datastore.select(path, BotRow)
            if rows:
                row = rows[0]
                bot_rows.append((row.bot_id, row.status, row.updated_at.isoformat() if row.updated_at else ""))
        return bot_rows

    def show_sweep_detail(self, sweep_id: int) -> None:
        if self.sweepmgr is None:
            raise RuntimeError("sweep manager missing")
        metrics = self.sweepmgr.metrics(sweep_id)
        lines = [
            f"sweep_id={metrics['sweep_id']} status={metrics['status']} progress={metrics['progress']}",
            f"runs={metrics['sweeprun_count']} win_loss={metrics['win_loss']} pf={metrics['profit_factor']} ev={metrics['ev']}",
            f"signals={metrics['signal_count']} positions={metrics['position_count']} orders={metrics['order_count']} fills={metrics['fill_count']}",
            f"db={metrics['db_path']}",
            f"report: ./report.sh {sweep_id}",
        ]
        self.detail.update("\n".join(lines))


def main() -> None:
    NuubotTui().run()
