"""Database schema (SQLAlchemy Core).

One schema, all dialects. The same table definitions are created on PostgreSQL
and SQLite by switching the connection URL only. Two tables:

- ``messages``     — one row per exported message *or* service event.
- ``import_logs``  — one row per import run (audit trail).

Design notes:
- ``id`` is a surrogate autoincrement PK (INTEGER PRIMARY KEY on SQLite,
  identity/serial on PostgreSQL).
- Dedup key is the natural pair ``(chat_id, message_id)`` — a UNIQUE constraint
  guarantees the same message is never imported twice, across re-runs.
- Telegram IDs are large, hence BigInteger for chat/message/user ids.
- Timestamps are stored timezone-aware (UTC), parsed from ``date_unixtime``.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

import_logs = Table(
    "import_logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    # When this import ran (UTC).
    Column("loaded_at", DateTime(timezone=True), nullable=False),
    # When the export was produced (from folder name "ChatExport_YYYY-MM-DD",
    # --export-date, or file mtime). Kept SEPARATE from loaded_at on purpose:
    # export date and load date can differ.
    Column("export_date", DateTime(timezone=True), nullable=True),
    # Who/where ran the CLI (OS user + hostname). CLI analogue of the bot's
    # actor_user_id/command_chat_id.
    Column("actor", String(255), nullable=True),
    Column("hostname", String(255), nullable=True),
    Column("source_path", Text, nullable=True),
    Column("db_target", String(50), nullable=True),
    # Chat the export belongs to (normalized id, without the -100 prefix).
    Column("export_chat_id", BigInteger, nullable=True),
    Column("export_chat_name", String(1024), nullable=True),
    # Export type: personal_chat (1:1 dialog), public_supergroup, channel, ...
    Column("export_chat_type", String(32), nullable=True),
    Column("export_file_name", String(1024), nullable=True),
    Column("export_file_size", BigInteger, nullable=True),
    # Unixtime of the latest message in the export (how far history was pulled).
    Column("export_max_date_unixtime", BigInteger, nullable=True),
    # Row counters for this run.
    Column("prepared_rows", Integer, nullable=True),
    Column("inserted_rows", Integer, nullable=True),
    Column("skipped_by_id", Integer, nullable=True),
    Column("service_rows", Integer, nullable=True),
    Column("errors_count", Integer, nullable=True),
    Column("errors_preview", Text, nullable=True),
)

messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("chat_id", BigInteger, nullable=False),
    Column("chat_name", String(1024), nullable=True),
    # Chat kind from the export: personal_chat (1:1 dialog), public_supergroup,
    # private_group, channel, bot_chat, ... Filter dialogs with
    # WHERE chat_type = 'personal_chat'.
    Column("chat_type", String(32), nullable=True),
    Column("message_id", BigInteger, nullable=False),
    # "message" (regular) or "service" (join/leave/pin/call/...).
    Column("message_type", String(32), nullable=False),
    # Service action name (e.g. "join_group_by_link", "pin_message"); NULL for
    # regular messages.
    Column("action", String(128), nullable=True),
    Column("user_id", BigInteger, nullable=True),
    Column("user_name", String(1024), nullable=True),
    # Original from_id/actor_id string ("user123", "channel123") kept verbatim.
    Column("from_id_raw", String(128), nullable=True),
    Column("message", Text, nullable=True),
    Column("date", DateTime(timezone=True), nullable=True),
    Column("date_unixtime", BigInteger, nullable=True),
    Column("edited", DateTime(timezone=True), nullable=True),
    Column("reply_to_message_id", BigInteger, nullable=True),
    Column("reply_to_text", Text, nullable=True),
    Column("forwarded_from", String(1024), nullable=True),
    # --- Media metadata (v1: metadata only, files are NOT copied) ---
    Column("media_type", String(64), nullable=True),
    Column("mime_type", String(255), nullable=True),
    # Relative path as written in the export (e.g. "video_files/1781.mp4").
    Column("file_path", Text, nullable=True),
    Column("file_name", Text, nullable=True),
    Column("file_size", BigInteger, nullable=True),
    Column("thumbnail", Text, nullable=True),
    Column("duration_seconds", Integer, nullable=True),
    Column("width", Integer, nullable=True),
    Column("height", Integer, nullable=True),
    # Which import run brought this row in.
    Column("import_id", Integer, ForeignKey("import_logs.id"), nullable=True),
    UniqueConstraint("chat_id", "message_id", name="uq_messages_chat_message"),
    Index("ix_messages_chat_id", "chat_id"),
    Index("ix_messages_user_id", "user_id"),
    Index("ix_messages_date", "date"),
)
