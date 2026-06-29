"""Schemas are for table schemas.

Table fields use three visual columns:

    name : Mapped[type] = mapped_column(...)

Use minimum visual widths: 20 characters for names and 20 characters for types.
If one field exceeds those widths, let that one row exceed them. Do not widen
the rest of the block to match it.

Order fields as: key, Hyperliquid ids, parent ids, required fields, optional
fields. Parent ids are plain columns. Do not use database foreign keys.

All timestamp fields are UTC by default.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


# Server Tables

class ServerSequenceRow(Base):
    __tablename__ = "server_sequence"

    name                : Mapped[str]          = mapped_column(String(64), primary_key=True)
    value               : Mapped[int]          = mapped_column(BigInteger, default=0)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ServerStateRow(Base):
    __tablename__ = "server_state"

    key                 : Mapped[str]          = mapped_column(String(128), primary_key=True)
    value_json          : Mapped[str]          = mapped_column(Text, default="{}")

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class BotCatalogRow(Base):
    __tablename__ = "bot_catalog"

    bot_id              : Mapped[int]          = mapped_column(BigInteger, primary_key=True)
    exec_network        : Mapped[str]          = mapped_column(String(32), index=True)
    db_path             : Mapped[str]          = mapped_column(Text)
    status              : Mapped[str]          = mapped_column(String(32), index=True, default="configured")
    actor_id            : Mapped[str | None]   = mapped_column(Text, nullable=True)
    run_token           : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    started_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    last_seen_at        : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    stopped_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    error_code          : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    error_text          : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SweepCatalogRow(Base):
    __tablename__ = "sweep_catalog"

    sweep_id            : Mapped[int]          = mapped_column(BigInteger, primary_key=True)
    db_path             : Mapped[str]          = mapped_column(Text)
    status              : Mapped[str]          = mapped_column(String(32), index=True, default="configured")
    started_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    last_seen_at        : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    stopped_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    error_code          : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    error_text          : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SweeprunCatalogRow(Base):
    __tablename__ = "sweeprun_catalog"

    sweeprun_id         : Mapped[int]          = mapped_column(BigInteger, primary_key=True)
    sweep_id            : Mapped[int | None]   = mapped_column(BigInteger, nullable=True, index=True)
    db_path             : Mapped[str]          = mapped_column(Text)
    status              : Mapped[str]          = mapped_column(String(32), index=True, default="configured")
    started_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    last_seen_at        : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    stopped_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    error_code          : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    error_text          : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ExchangeMetaRow(Base):
    __tablename__ = "exchange_meta"
    __table_args__ = (UniqueConstraint("symbol", "kind"),)

    meta_id             : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol              : Mapped[str]          = mapped_column(String(64), index=True)
    kind                : Mapped[str]          = mapped_column(String(16), index=True)
    asset_id            : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    exchange_index      : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    max_leverage        : Mapped[int | None]   = mapped_column(Integer, nullable=True)
    size_decimals       : Mapped[int | None]   = mapped_column(Integer, nullable=True)
    price_decimals      : Mapped[int | None]   = mapped_column(Integer, nullable=True)
    is_delisted         : Mapped[bool]         = mapped_column(Boolean, default=False)
    is_canonical        : Mapped[bool | None]  = mapped_column(Boolean, nullable=True)
    raw_json            : Mapped[str]          = mapped_column(Text, default="{}")
    fetched_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# Command Table

class CommandRow(Base):
    __tablename__ = "command"

    command_id          : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    command             : Mapped[str]          = mapped_column(String(32), index=True)
    status              : Mapped[str]          = mapped_column(String(32), index=True, default="pending")
    payload_json        : Mapped[str]          = mapped_column(Text, default="{}")
    command_ts          : Mapped[int]          = mapped_column(BigInteger)
    result_json         : Mapped[str | None]   = mapped_column(Text, nullable=True)
    error_code          : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    error_text          : Mapped[str | None]   = mapped_column(Text, nullable=True)
    claimed_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    completed_at        : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# Bots Tables

class BotRow(Base):
    __tablename__ = "bot"

    bot_key             : Mapped[str]          = mapped_column(String(16), primary_key=True, default="bot")
    status              : Mapped[str]          = mapped_column(String(32), index=True, default="configured")
    config_json         : Mapped[str]          = mapped_column(Text, default="{}")
    state_json          : Mapped[str]          = mapped_column(Text, default="{}")
    # running/execution fields
    actor_id            : Mapped[str | None]   = mapped_column(Text, nullable=True)
    run_token           : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    started_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    last_seen_at        : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    stopped_at          : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    error_code          : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    error_text          : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AccountRow(Base):
    __tablename__ = "account"

    account_id          : Mapped[str]          = mapped_column(String(64), primary_key=True)
    role                : Mapped[str]          = mapped_column(String(32), index=True, default="")
    name                : Mapped[str]          = mapped_column(String(64), index=True, default="")
    exec_network        : Mapped[str]          = mapped_column(String(32), index=True, default="")
    status              : Mapped[str]          = mapped_column(String(32), index=True, default="configured")
    config_json         : Mapped[str]          = mapped_column(Text, default="{}")
    state_json          : Mapped[str]          = mapped_column(Text, default="{}")

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ExchangeMetaSnapshotRow(Base):
    __tablename__ = "exchange_meta_snapshot"
    __table_args__ = (UniqueConstraint("symbol", "kind"),)

    meta_id             : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol              : Mapped[str]          = mapped_column(String(64), index=True)
    kind                : Mapped[str]          = mapped_column(String(16), index=True)
    asset_id            : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    exchange_index      : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    max_leverage        : Mapped[int | None]   = mapped_column(Integer, nullable=True)
    size_decimals       : Mapped[int | None]   = mapped_column(Integer, nullable=True)
    price_decimals      : Mapped[int | None]   = mapped_column(Integer, nullable=True)
    is_delisted         : Mapped[bool]         = mapped_column(Boolean, default=False)
    is_canonical        : Mapped[bool | None]  = mapped_column(Boolean, nullable=True)
    raw_json            : Mapped[str]          = mapped_column(Text, default="{}")
    fetched_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    snapshotted_at      : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# Sweeps Tables

class SweepRow(Base):
    __tablename__ = "sweeps"

    sweep_id            : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    sweep_desc          : Mapped[str]          = mapped_column(Text)
    config_json         : Mapped[str]          = mapped_column(Text)
    results_json        : Mapped[str]          = mapped_column(Text, default="{}")
    status              : Mapped[str]          = mapped_column(String(32), default="configured", index=True)
    sweeprun_count      : Mapped[int]          = mapped_column(Integer, default=0)
    error_code          : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    error_text          : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SweeprunRow(Base):
    __tablename__ = "sweepruns"
    __table_args__ = (UniqueConstraint("sweep_id", "sweeprun_index"),)

    sweeprun_id         : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    sweep_id            : Mapped[int]          = mapped_column(Integer, index=True)
    sweeprun_index      : Mapped[int]          = mapped_column(Integer)
    config_json         : Mapped[str]          = mapped_column(Text)
    results_json        : Mapped[str]          = mapped_column(Text, default="{}")
    status              : Mapped[str]          = mapped_column(String(32), default="configured", index=True)
    error_code          : Mapped[str | None]   = mapped_column(String(64), nullable=True)
    error_text          : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# Ledger Tables

class PositionRow(Base):
    __tablename__ = "position"

    # key
    position_id         : Mapped[int]          = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # parent ids
    account_id          : Mapped[str]          = mapped_column(Text, index=True)

    # required fields
    symbol              : Mapped[str]          = mapped_column(Text)
    status              : Mapped[str]          = mapped_column(String(32), index=True)

    # accounting
    side                : Mapped[str | None]   = mapped_column(Text, nullable=True)
    current_sz          : Mapped[str]          = mapped_column(Text, default="0")
    max_abs_sz          : Mapped[str]          = mapped_column(Text, default="0")
    avg_entry_px        : Mapped[str | None]   = mapped_column(Text, nullable=True)
    avg_exit_px         : Mapped[str | None]   = mapped_column(Text, nullable=True)
    mark_px             : Mapped[str | None]   = mapped_column(Text, nullable=True)
    entry_cash          : Mapped[str]          = mapped_column(Text, default="0")
    exit_cash           : Mapped[str]          = mapped_column(Text, default="0")
    open_entry_cash     : Mapped[str]          = mapped_column(Text, default="0")
    entry_fee           : Mapped[str]          = mapped_column(Text, default="0")
    exit_fee            : Mapped[str]          = mapped_column(Text, default="0")
    total_fee           : Mapped[str]          = mapped_column(Text, default="0")
    gross_pnl           : Mapped[str]          = mapped_column(Text, default="0")
    realized_pnl        : Mapped[str]          = mapped_column(Text, default="0")
    unrealized_pnl      : Mapped[str]          = mapped_column(Text, default="0")
    net_pnl             : Mapped[str]          = mapped_column(Text, default="0")

    # timestamps
    opened_ts           : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    closed_ts           : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    last_update_ts      : Mapped[int]          = mapped_column(BigInteger)

    # optional fields
    exit_reason         : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # suggested fields from hcbot:
    # component
    # level
    # level_seq
    # meta1
    # meta2
    # meta3
    # meta_json


class OrderRow(Base):
    __tablename__ = "order"

    # key
    order_id            : Mapped[int]          = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Hyperliquid ids
    oid                 : Mapped[int | None]   = mapped_column(BigInteger, nullable=True, index=True)
    cloid               : Mapped[str | None]   = mapped_column(Text, nullable=True, index=True)

    # parent ids
    position_id         : Mapped[int]          = mapped_column(BigInteger, index=True)
    account_id          : Mapped[str]          = mapped_column(Text, index=True)

    # submitted / intent
    submit_cloid        : Mapped[str]          = mapped_column(Text, index=True)
    submit_ts           : Mapped[int]          = mapped_column(BigInteger)
    submit_coin         : Mapped[str]          = mapped_column(Text)
    submit_side         : Mapped[str]          = mapped_column(Text)
    submit_quantity     : Mapped[str]          = mapped_column(Text)
    submit_price        : Mapped[str]          = mapped_column(Text)
    submit_reduceonly   : Mapped[bool]         = mapped_column(Boolean)
    submit_type         : Mapped[str]          = mapped_column(Text)
    submit_trigger_price : Mapped[str | None]   = mapped_column(Text, nullable=True)
    submit_tif          : Mapped[str | None]   = mapped_column(Text, nullable=True)
    submit_tpsl         : Mapped[str | None]   = mapped_column(Text, nullable=True)
    submit_parent_cloid : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # exchange state
    status              : Mapped[str]          = mapped_column(String(32), default="planned", index=True)
    exchange_status     : Mapped[str | None]   = mapped_column(Text, nullable=True)
    terminal_reason     : Mapped[str | None]   = mapped_column(Text, nullable=True)
    filled_quantity     : Mapped[str]          = mapped_column(Text, default="0")
    remaining_quantity  : Mapped[str | None]   = mapped_column(Text, nullable=True)
    avg_fill_price      : Mapped[str | None]   = mapped_column(Text, nullable=True)
    fee                 : Mapped[str]          = mapped_column(Text, default="0")
    fill_count          : Mapped[int]          = mapped_column(Integer, default=0)
    first_fill_ts       : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    last_fill_ts        : Mapped[int | None]   = mapped_column(BigInteger, nullable=True)
    raw_json            : Mapped[str]          = mapped_column(Text, default="{}")
    error_text          : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # suggested fields from hcbot:
    # role
    # grouping
    # is_position_tpsl
    # is_trigger
    # frontend_order_type
    # trigger_condition
    # children_raw
    # frontend_raw
    # source
    # trade_terminal
    # slippage_px
    # slippage_cash
    # processed_fill_keys_json


class FillRow(Base):
    __tablename__ = "fill"

    # key
    fill_id             : Mapped[int]          = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Hyperliquid ids
    tid                 : Mapped[int | None]   = mapped_column(BigInteger, nullable=True, index=True)
    hash                : Mapped[str | None]   = mapped_column(Text, nullable=True, index=True)
    oid                 : Mapped[int | None]   = mapped_column(BigInteger, nullable=True, index=True)
    cloid               : Mapped[str | None]   = mapped_column(Text, nullable=True, index=True)

    # parent ids
    order_id            : Mapped[int]          = mapped_column(BigInteger, index=True)
    account_id          : Mapped[str]          = mapped_column(Text, index=True)

    # Hyperliquid fill fields
    coin                : Mapped[str]          = mapped_column(Text)
    side                : Mapped[str]          = mapped_column(Text)
    px                  : Mapped[str]          = mapped_column(Text)
    sz                  : Mapped[str]          = mapped_column(Text)
    time                : Mapped[int]          = mapped_column(BigInteger)
    fee                 : Mapped[str]          = mapped_column(Text)
    feeToken            : Mapped[str | None]   = mapped_column(Text, nullable=True)
    builderFee          : Mapped[str | None]   = mapped_column(Text, nullable=True)
    closedPnl           : Mapped[str | None]   = mapped_column(Text, nullable=True)
    crossed             : Mapped[bool | None]  = mapped_column(Boolean, nullable=True)
    dir                 : Mapped[str | None]   = mapped_column(Text, nullable=True)
    startPosition       : Mapped[str | None]   = mapped_column(Text, nullable=True)

    # optional fields
    raw_json            : Mapped[str]          = mapped_column(Text, default="{}")

    # standard tail fields
    notes               : Mapped[str]          = mapped_column(Text, default="")
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    # suggested fields from hcbot:
    # fill_key
    # is_complete
    # source
    # comment
