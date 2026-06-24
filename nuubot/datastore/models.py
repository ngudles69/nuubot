from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BotRow(Base):
    __tablename__ = "bot"

    bot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    config_json: Mapped[str] = mapped_column(Text)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stopped_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CommandRow(Base):
    __tablename__ = "command"

    command_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, index=True)
    command: Mapped[str] = mapped_column(String(32), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer)
    claimed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
