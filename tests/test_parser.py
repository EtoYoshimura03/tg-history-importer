"""Parser tests. Run: `pip install -e .[dev] && pytest`."""

from __future__ import annotations

from pathlib import Path

from tg_history_importer.parser import (
    detect_export_date,
    normalize_chat_id,
    parse_export,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_result.json"


def test_normalize_chat_id():
    assert normalize_chat_id(-1002281106395) == 2281106395
    assert normalize_chat_id(2281106395) == 2281106395


def test_parse_counts():
    r = parse_export(FIXTURE)
    assert r.chat_id == 2281106395
    assert r.chat_name == "Test Chat"
    assert len(r.rows) == 4
    assert r.total_messages == 4
    assert r.service_rows == 1
    assert r.max_date_unixtime == 1784296343


def test_service_row():
    r = parse_export(FIXTURE)
    svc = next(x for x in r.rows if x["message_type"] == "service")
    assert svc["action"] == "create_group"
    assert svc["user_id"] == 480642587
    assert svc["user_name"] == "Jhon Doe"


def test_media_row_metadata():
    r = parse_export(FIXTURE)
    media = next(x for x in r.rows if x["message_id"] == 4)
    assert media["media_type"] == "animation"
    assert media["file_path"] == "video_files/1781.gif.mp4"
    assert media["file_name"] == "1781.gif.mp4"
    assert media["file_size"] == 16193
    assert media["duration_seconds"] == 1
    assert media["width"] == 320
    assert media["height"] == 180


def test_reply_text_resolution():
    r = parse_export(FIXTURE)
    reply = next(x for x in r.rows if x["message_id"] == 3)
    assert reply["reply_to_message_id"] == 2
    assert reply["reply_to_text"] == "Hello world"
    # list-form text is flattened
    assert reply["message"] == "Hi @jhondoe"


def test_export_date_override():
    d = detect_export_date(FIXTURE, override="2026-07-18")
    assert d is not None
    assert (d.year, d.month, d.day) == (2026, 7, 18)
