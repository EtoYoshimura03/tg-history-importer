"""Managed media store: copy export media into a content-addressed store.

Files referenced by an export live under the export folder (e.g.
``video_files/...``, ``photos/...``). With ``--copy-media`` we copy them into a
store addressed by sha256, so identical files (repeated stickers/gifs) are
stored once, and references survive even if the export folder is deleted.

This module does all the filesystem I/O — ``parser.py`` stays side-effect-free.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import platformdirs

APP_NAME = "tg-history-importer"


def resolve_store_dir(media_dir: str | None) -> Path:
    """Where the media store lives.

    Explicit ``--media-dir`` / ``TG_IMPORTER_MEDIA_DIR`` wins; otherwise the
    OS-standard per-user data dir (``platformdirs``), which is writable without
    admin rights and works the same when the app ships as a binary.
    """
    if media_dir:
        return Path(media_dir).expanduser()
    return Path(platformdirs.user_data_dir(APP_NAME)) / "media"


def ensure_store(store_dir: Path) -> None:
    """Create the store dir, raising a clear error on permission problems."""
    try:
        store_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(
            f"Cannot create media store at {store_dir}: {e}. "
            f"Pass --media-dir (or set TG_IMPORTER_MEDIA_DIR) to a writable path."
        ) from e


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def store_file(src: Path, store_dir: Path) -> tuple[str, str, bool]:
    """Copy ``src`` into the content-addressed store.

    Layout: ``<store>/<h0h1>/<sha256><ext>`` — single-level sharding by the first
    two hex chars, so there are at most 256 shard folders regardless of how many
    files are stored (git-style). Returns ``(sha256, path_relative_to_store,
    was_new)``. If a file with the same hash already exists it is not copied
    again (``was_new=False``) — this is the dedup.
    """
    digest = _hash_file(src)
    rel = Path(digest[:2]) / f"{digest}{src.suffix}"
    dest = store_dir / rel
    was_new = not dest.exists()
    if was_new:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)  # copy2 preserves mtime
    return digest, rel.as_posix(), was_new


@dataclass
class CopyStats:
    copied: int = 0
    deduplicated: int = 0
    missing: int = 0
    errors: int = 0
    error_samples: list[str] = field(default_factory=list)


def _copy_one(
    row: dict,
    src_key: str,
    base_dir: Path,
    store_dir: Path,
    stats: CopyStats,
    *,
    sha_key: str | None,
    dest_key: str,
) -> None:
    rel = row.get(src_key)
    if not rel:
        return
    src = base_dir / rel
    if not src.is_file():
        stats.missing += 1
        return
    try:
        digest, stored_rel, was_new = store_file(src, store_dir)
    except OSError as e:
        stats.errors += 1
        if len(stats.error_samples) < 5:
            stats.error_samples.append(f"{rel}: {e}")
        return
    if was_new:
        stats.copied += 1
    else:
        stats.deduplicated += 1
    if sha_key:
        row[sha_key] = digest
    row[dest_key] = stored_rel


def copy_media_for_rows(
    rows: list[dict], base_dir: Path, store_dir: Path
) -> CopyStats:
    """Copy each row's media file and thumbnail into the store, annotating the
    row with ``media_sha256`` / ``stored_path`` / ``stored_thumbnail_path``.

    ``base_dir`` is the folder the export's relative paths resolve against
    (the folder containing ``result.json``). Rows are mutated in place. Counters
    aggregate over both main files and thumbnails.
    """
    stats = CopyStats()
    for row in rows:
        _copy_one(
            row, "file_path", base_dir, store_dir, stats,
            sha_key="media_sha256", dest_key="stored_path",
        )
        _copy_one(
            row, "thumbnail", base_dir, store_dir, stats,
            sha_key=None, dest_key="stored_thumbnail_path",
        )
    return stats
