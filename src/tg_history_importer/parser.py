"""Parse a Telegram Desktop JSON export (``result.json``) into flat rows.

The export top level looks like::

    {"name": "...", "type": "...", "id": 123, "messages": [ ... ]}

Each element of ``messages`` is either:

- ``"type": "message"`` — a regular message (text and/or media), fields
  ``from`` / ``from_id`` / ``text`` / media keys (``file``, ``photo``, ...).
- ``"type": "service"`` — a system event (join, leave, pin, call, title
  change, ...), fields ``actor`` / ``actor_id`` / ``action``.

Both kinds are normalized into the same row dict (see ``models.messages``).
Time is taken from ``date_unixtime`` (reliable UTC); the human ``date`` field
is the exporter's local time and is intentionally ignored.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Telegram Desktop names the export folder "ChatExport_YYYY-MM-DD".
EXPORT_DATE_RE = re.compile(r"ChatExport_(\d{4}-\d{2}-\d{2})")
_DIGITS_RE = re.compile(r"(\d+)")


def normalize_chat_id(chat_id: int) -> int:
    """Strip the Bot API ``-100`` supergroup prefix, matching the exporter's id.

    Exports usually already carry the normalized (positive) id, but a leading
    ``-100`` is stripped defensively so ids line up across sources.
    """
    s = str(chat_id)
    if s.startswith("-100"):
        return int(s[4:])
    return chat_id


def _parse_from_id(raw: Any) -> tuple[int | None, str | None]:
    """Return ``(numeric_id, raw_string)`` from a from_id/actor_id value.

    Handles ``"user480642587"`` and ``"channel123"`` (numeric part extracted)
    as well as bare ints. Returns ``(None, None)`` for missing values.
    """
    if raw is None:
        return None, None
    if isinstance(raw, int):
        return raw, str(raw)
    if isinstance(raw, str):
        m = _DIGITS_RE.search(raw)
        return (int(m.group(1)) if m else None), raw
    return None, None


def _extract_plain_text(text_field: Any) -> str:
    """Flatten Telegram's ``text`` (str | list[str | {"text": ...}]) to a str."""
    if isinstance(text_field, str):
        return text_field
    if isinstance(text_field, list):
        parts: list[str] = []
        for item in text_field:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return ""


def _parse_unixtime(ts: Any) -> datetime | None:
    if ts is None or ts == "":
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _to_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@dataclass
class ParseResult:
    chat_id: int
    chat_name: str
    rows: list[dict]
    total_messages: int  # length of the raw "messages" array
    service_rows: int  # how many of `rows` are service events
    max_date_unixtime: int | None
    export_date: datetime | None


def resolve_export_path(path: str | Path) -> Path:
    """Accept a folder (``ChatExport_...``) or a ``result.json`` file directly."""
    p = Path(path)
    if p.is_dir():
        candidate = p / "result.json"
        if not candidate.exists():
            raise FileNotFoundError(f"result.json not found in folder: {p}")
        return candidate
    if not p.exists():
        raise FileNotFoundError(f"Export path does not exist: {p}")
    return p


def detect_export_date(json_path: Path, override: str | None = None) -> datetime | None:
    """Determine the export date, in priority order.

    1. ``override`` (``--export-date YYYY-MM-DD``);
    2. a "ChatExport_YYYY-MM-DD" pattern in the folder or file name;
    3. the file's modification time (last-resort fallback).
    """
    if override:
        return datetime.strptime(override, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    for part in (json_path.parent.name, json_path.name):
        m = EXPORT_DATE_RE.search(part)
        if m:
            return datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    try:
        return datetime.fromtimestamp(json_path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _build_reply_index(messages: list[dict]) -> dict[int, str]:
    """Map message id -> plain text, so replies can carry the quoted text.

    NOTE: only messages inside *this* file are indexed. If history was exported
    across several files, a reply pointing to another file resolves to None.
    """
    idx: dict[int, str] = {}
    for msg in messages:
        mid = msg.get("id")
        if isinstance(mid, int):
            idx[mid] = _extract_plain_text(msg.get("text", ""))
    return idx


def parse_export(
    json_path: str | Path, export_date_override: str | None = None
) -> ParseResult:
    json_path = Path(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chat_id_raw = data.get("id")
    if not isinstance(chat_id_raw, int):
        raise ValueError(f"Export 'id' must be an int, got: {chat_id_raw!r}")
    chat_id = normalize_chat_id(chat_id_raw)
    chat_name = data.get("name") or ""

    messages = data.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("Export field 'messages' must be a list.")

    reply_index = _build_reply_index(messages)

    rows: list[dict] = []
    seen_ids: set[int] = set()
    service_rows = 0
    max_dt: int | None = None

    for msg in messages:
        mtype = msg.get("type")
        if mtype not in ("message", "service"):
            continue

        mid = msg.get("id")
        if not isinstance(mid, int):
            continue
        # Dedup within the file (defensive; ids are unique per export).
        if mid in seen_ids:
            continue
        seen_ids.add(mid)

        if mtype == "service":
            from_name = msg.get("actor")
            from_raw = msg.get("actor_id")
            action = msg.get("action")
            service_rows += 1
        else:
            from_name = msg.get("from")
            from_raw = msg.get("from_id")
            action = None

        user_id, from_id_raw = _parse_from_id(from_raw)

        raw_ts = msg.get("date_unixtime")
        ts_int = _to_int_or_none(raw_ts)
        if ts_int is not None and (max_dt is None or ts_int > max_dt):
            max_dt = ts_int

        # Media: regular files use "file"; photos use "photo".
        file_path = msg.get("file") or msg.get("photo")
        file_size = msg.get("file_size")
        if file_size is None and msg.get("photo") is not None:
            file_size = msg.get("photo_file_size")
        media_type = msg.get("media_type")
        if media_type is None and msg.get("photo") is not None:
            media_type = "photo"

        reply_to = msg.get("reply_to_message_id")
        reply_to_id = reply_to if isinstance(reply_to, int) else None
        reply_to_text = reply_index.get(reply_to) if isinstance(reply_to, int) else None

        rows.append(
            {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "message_id": mid,
                "message_type": mtype,
                "action": action,
                "user_id": user_id,
                "user_name": from_name,
                "from_id_raw": from_id_raw,
                "message": _extract_plain_text(msg.get("text", "")),
                "date": _parse_unixtime(raw_ts),
                "date_unixtime": ts_int,
                "edited": _parse_unixtime(msg.get("edited_unixtime")),
                "reply_to_message_id": reply_to_id,
                "reply_to_text": reply_to_text,
                "forwarded_from": msg.get("forwarded_from"),
                "media_type": media_type,
                "mime_type": msg.get("mime_type"),
                "file_path": file_path,
                "file_name": msg.get("file_name"),
                "file_size": _to_int_or_none(file_size),
                "thumbnail": msg.get("thumbnail"),
                "duration_seconds": _to_int_or_none(msg.get("duration_seconds")),
                "width": _to_int_or_none(msg.get("width")),
                "height": _to_int_or_none(msg.get("height")),
            }
        )

    return ParseResult(
        chat_id=chat_id,
        chat_name=str(chat_name),
        rows=rows,
        total_messages=len(messages),
        service_rows=service_rows,
        max_date_unixtime=max_dt,
        export_date=detect_export_date(json_path, export_date_override),
    )
