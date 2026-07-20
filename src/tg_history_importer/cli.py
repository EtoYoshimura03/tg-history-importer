"""Command-line interface (Typer).

Commands:
    init-db   Create the tables on a target database.
    load      Parse a Telegram JSON export and load it into a target database.

Targets:
    --to sqlite --db ./chat.db
    --to postgres --dsn postgresql+psycopg://user:pass@host/db   (or TG_IMPORTER_DSN)
"""

from __future__ import annotations

import getpass
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from . import db as dbmod
from .parser import parse_export, resolve_export_path

app = typer.Typer(
    add_completion=False,
    help="Import Telegram chat exports (JSON) into PostgreSQL or SQLite.",
)


def _build_engine(target: str, dsn: Optional[str], db_path: Optional[str]):
    try:
        return dbmod.build_engine(target, dsn=dsn, db_path=db_path)
    except ValueError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)


@app.command("version")
def version_cmd() -> None:
    """Print the version and exit."""
    typer.echo(__version__)


@app.command("init-db")
def init_db_cmd(
    to: str = typer.Option(..., "--to", help="Target database: sqlite | postgres"),
    dsn: Optional[str] = typer.Option(
        None, "--dsn", envvar="TG_IMPORTER_DSN", help="PostgreSQL connection string"
    ),
    db: Optional[str] = typer.Option(None, "--db", help="SQLite file path"),
) -> None:
    """Create the messages and import_logs tables if they do not exist."""
    engine = _build_engine(to, dsn, db)
    dbmod.init_db(engine)
    typer.secho(f"Tables ensured on target '{to}'.", fg=typer.colors.GREEN)


@app.command("load")
def load_cmd(
    path: str = typer.Argument(
        ..., help="Path to the export folder (ChatExport_...) or a result.json file."
    ),
    to: str = typer.Option(..., "--to", help="Target database: sqlite | postgres"),
    dsn: Optional[str] = typer.Option(
        None, "--dsn", envvar="TG_IMPORTER_DSN", help="PostgreSQL connection string"
    ),
    db: Optional[str] = typer.Option(None, "--db", help="SQLite file path"),
    export_date: Optional[str] = typer.Option(
        None,
        "--export-date",
        help="YYYY-MM-DD; overrides folder-name / mtime detection.",
    ),
    batch_size: int = typer.Option(1000, "--batch-size", help="Insert batch size."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print per-batch insert progress."
    ),
) -> None:
    """Load a Telegram JSON export (dedup by chat_id + message_id)."""
    json_path = resolve_export_path(path)
    typer.echo(f"Parsing {json_path} ...")
    parsed = parse_export(json_path, export_date_override=export_date)

    engine = _build_engine(to, dsn, db)
    dbmod.init_db(engine)

    existing = dbmod.fetch_existing_message_ids(engine, parsed.chat_id)
    to_insert = [r for r in parsed.rows if r["message_id"] not in existing]
    skipped_by_id = len(parsed.rows) - len(to_insert)
    service_new = sum(1 for r in to_insert if r["message_type"] == "service")

    file_path = Path(json_path)
    file_size = file_path.stat().st_size if file_path.exists() else None

    # Insert the log row first so messages can reference it (FK import_id);
    # counters are filled in now and inserted_rows/errors are updated after.
    log_id = dbmod.insert_import_log(
        engine,
        loaded_at=datetime.now(timezone.utc),
        export_date=parsed.export_date,
        actor=getpass.getuser(),
        hostname=socket.gethostname(),
        source_path=str(file_path.resolve()),
        db_target=to,
        export_chat_id=parsed.chat_id,
        export_chat_name=parsed.chat_name,
        export_chat_type=parsed.chat_type,
        export_file_name=file_path.name,
        export_file_size=file_size,
        export_max_date_unixtime=parsed.max_date_unixtime,
        prepared_rows=len(to_insert),
        inserted_rows=0,
        skipped_by_id=skipped_by_id,
        service_rows=service_new,
        errors_count=0,
        errors_preview=None,
    )

    for r in to_insert:
        r["import_id"] = log_id

    n_batches = (len(to_insert) + batch_size - 1) // batch_size if to_insert else 0

    def _on_batch(batch_index: int, n: int, done: int, total: int) -> None:
        typer.echo(f"  batch {batch_index}/{n}: {done}/{total} rows inserted")

    errors_count = 0
    errors_preview = None
    inserted = 0
    try:
        inserted = dbmod.insert_messages(
            engine,
            to_insert,
            batch_size=batch_size,
            on_batch=_on_batch if verbose else None,
        )
    except Exception as e:  # noqa: BLE001 - record any insert failure in the log
        errors_count = 1
        errors_preview = f"{type(e).__name__}: {e}"

    dbmod.update_import_log(
        engine,
        log_id,
        inserted_rows=inserted,
        errors_count=errors_count,
        errors_preview=errors_preview,
    )

    typer.echo("")
    typer.secho("Import finished", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"  Chat:               {parsed.chat_name} (id={parsed.chat_id})")
    typer.echo(f"  Messages in export: {parsed.total_messages}")
    typer.echo(f"  Prepared rows:      {len(to_insert)}")
    typer.echo(f"  Inserted rows:      {inserted} (in {n_batches} batch(es) of {batch_size})")
    typer.echo(f"    of which service: {service_new}")
    typer.echo(f"  Skipped duplicates: {skipped_by_id}")
    typer.echo(f"  Export date:        {parsed.export_date}")
    typer.echo(f"  Import log id:      {log_id}")
    typer.echo(f"  Errors:             {errors_count}")

    if errors_count:
        typer.secho(f"Error: {errors_preview}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
