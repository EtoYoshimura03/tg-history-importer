"""End-to-end load test (parser -> db) against a temp SQLite file."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from tg_history_importer.cli import perform_load

FIXTURE = Path(__file__).parent / "fixtures" / "sample_result.json"


def test_perform_load_sqlite(tmp_path):
    db = tmp_path / "t.db"
    perform_load(path=str(FIXTURE), to="sqlite", dsn=None, db=str(db))

    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM messages")).scalar() == 4
        assert (
            conn.execute(text("SELECT COUNT(*) FROM messages WHERE chat_type='public_supergroup'")).scalar()
            == 4
        )
        inserted, service = conn.execute(
            text("SELECT inserted_rows, service_rows FROM import_logs")
        ).one()
        assert inserted == 4
        assert service == 1


def test_perform_load_accepts_quoted_path(tmp_path):
    # Windows "Copy as path" wraps the path in double quotes — must still work.
    db = tmp_path / "t.db"
    perform_load(path=f'"{FIXTURE}"', to="sqlite", dsn=None, db=f'"{db}"')

    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM messages")).scalar() == 4


def test_perform_load_dedup_on_reimport(tmp_path):
    db = tmp_path / "t.db"
    perform_load(path=str(FIXTURE), to="sqlite", dsn=None, db=str(db))
    # second run: everything is a duplicate, nothing new inserted
    perform_load(path=str(FIXTURE), to="sqlite", dsn=None, db=str(db))

    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM messages")).scalar() == 4
        assert conn.execute(text("SELECT COUNT(*) FROM import_logs")).scalar() == 2
