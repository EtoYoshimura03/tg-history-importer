"""Database access: engine construction, table creation, dedup and inserts.

Kept deliberately dialect-agnostic. v1 does dedup in Python (fetch existing
message ids, filter, plain insert) instead of relying on dialect-specific
UPSERT (``ON CONFLICT`` vs ``MERGE``). This is simple, exact (we know precise
prepared/inserted/skipped counts) and mirrors the original bot's approach.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.engine import Engine, make_url

from .models import import_logs, messages, metadata


def build_engine(
    target: str, dsn: str | None = None, db_path: str | None = None
) -> Engine:
    """Create a SQLAlchemy engine for the chosen target.

    - ``sqlite``   → requires ``db_path``; parent dirs are created.
    - ``postgres`` → requires ``dsn``; a bare ``postgresql://`` is upgraded to
      the psycopg (v3) driver.
    """
    target = target.lower()
    if target == "sqlite":
        if not db_path:
            raise ValueError("SQLite target requires --db <path>.")
        p = Path(db_path).expanduser()
        if p.parent and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(f"sqlite:///{p}")
    if target in ("postgres", "postgresql"):
        if not dsn:
            raise ValueError(
                "Postgres target requires --dsn (or the TG_IMPORTER_DSN env var)."
            )
        url = make_url(dsn)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        return create_engine(url)
    raise ValueError(f"Unknown target: {target!r} (use 'sqlite' or 'postgres').")


def init_db(engine: Engine) -> None:
    """Create ``messages`` and ``import_logs`` if they do not already exist."""
    metadata.create_all(engine)


def fetch_existing_message_ids(engine: Engine, chat_id: int) -> set[int]:
    """Return the set of message_ids already stored for this chat (for dedup)."""
    stmt = select(messages.c.message_id).where(messages.c.chat_id == chat_id)
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(stmt)}


def insert_import_log(engine: Engine, **fields: Any) -> int:
    """Insert a run row and return its generated id."""
    with engine.begin() as conn:
        result = conn.execute(insert(import_logs).values(**fields))
        return int(result.inserted_primary_key[0])


def update_import_log(engine: Engine, import_id: int, **fields: Any) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(import_logs).where(import_logs.c.id == import_id).values(**fields)
        )


def insert_messages(
    engine: Engine,
    rows: list[dict],
    batch_size: int = 1000,
    on_batch: Any = None,
) -> int:
    """Insert message rows in batches within a single transaction.

    Returns the number of rows inserted. Rows are expected to be pre-deduped
    (see ``fetch_existing_message_ids``).

    ``on_batch`` (optional) is called after each batch as
    ``on_batch(batch_index, n_batches, inserted_so_far, total)`` — used by the
    CLI to report progress.
    """
    if not rows:
        return 0
    inserted = 0
    total = len(rows)
    n_batches = (total + batch_size - 1) // batch_size
    with engine.begin() as conn:
        for batch_index, i in enumerate(range(0, total, batch_size), start=1):
            batch = rows[i : i + batch_size]
            conn.execute(insert(messages), batch)
            inserted += len(batch)
            if on_batch is not None:
                on_batch(batch_index, n_batches, inserted, total)
    return inserted
