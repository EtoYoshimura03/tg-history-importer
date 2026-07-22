"""Media store tests. Run: `pip install -e .[dev] && pytest`."""

from __future__ import annotations

from pathlib import Path

from tg_history_importer.media import (
    copy_media_for_rows,
    ensure_store,
    resolve_store_dir,
    store_file,
)


def _blank_row(**over) -> dict:
    row = {
        "file_path": None,
        "thumbnail": None,
        "media_sha256": None,
        "stored_path": None,
        "stored_thumbnail_path": None,
    }
    row.update(over)
    return row


def test_resolve_store_dir_explicit(tmp_path):
    assert resolve_store_dir(str(tmp_path)) == Path(str(tmp_path))


def test_resolve_store_dir_default():
    default = resolve_store_dir(None)
    assert "tg-history-importer" in str(default)
    assert default.name == "media"


def test_store_file_dedup(tmp_path):
    store = tmp_path / "store"
    ensure_store(store)

    a = tmp_path / "a.bin"
    a.write_bytes(b"hello")
    sha1, rel1, new1 = store_file(a, store)
    assert new1 is True
    assert (store / rel1).exists()
    # single-level sharded layout: <h0h1>/<sha><ext>
    assert rel1.startswith(sha1[:2] + "/")
    assert rel1 == f"{sha1[:2]}/{sha1}.bin"

    # identical content in a different file -> same hash, not copied again
    b = tmp_path / "b.bin"
    b.write_bytes(b"hello")
    sha2, rel2, new2 = store_file(b, store)
    assert (sha2, rel2) == (sha1, rel1)
    assert new2 is False


def test_copy_media_for_rows(tmp_path):
    base = tmp_path / "ChatExport_2026-07-19"
    (base / "video_files").mkdir(parents=True)
    (base / "video_files" / "clip.mp4").write_bytes(b"video-bytes")
    (base / "video_files" / "clip.mp4_thumb.jpg").write_bytes(b"thumb")

    store = tmp_path / "store"
    ensure_store(store)

    rows = [
        _blank_row(
            file_path="video_files/clip.mp4",
            thumbnail="video_files/clip.mp4_thumb.jpg",
        ),
        _blank_row(),  # a text message, no media
        _blank_row(file_path="video_files/missing.mp4"),  # referenced but absent
    ]
    stats = copy_media_for_rows(rows, base, store)

    assert stats.copied == 2  # main file + thumbnail
    assert stats.missing == 1
    assert rows[0]["media_sha256"] is not None
    assert rows[0]["stored_path"] is not None
    assert rows[0]["stored_thumbnail_path"] is not None
    assert (store / rows[0]["stored_path"]).exists()
    assert (store / rows[0]["stored_thumbnail_path"]).exists()
    # untouched rows stay clean
    assert rows[1]["stored_path"] is None
    assert rows[2]["stored_path"] is None
