"""Interactive guided menu, shown when the app is launched with no command.

Aimed at non-programmers: choose an action with the arrow keys and answer simple
prompts, instead of typing command-line flags. It keeps the console open (a
double-clicked binary no longer flashes and closes). Advanced users can still
pass subcommands directly, e.g. ``tg-history-importer load ... --to sqlite``.

Built on ``questionary`` (prompt_toolkit) so paste (Ctrl+V / right-click), line
editing, path completion and arrow-key menus work regardless of the Windows
console host. All real work is delegated to ``cli.perform_load`` /
``cli.perform_init_db`` — a single implementation shared with the CLI.

``questionary``'s ``.ask()`` returns ``None`` when the user cancels (Ctrl+C /
Esc); every prompt checks for that and backs out gracefully.
"""

from __future__ import annotations

import questionary

from . import __version__


def _ask_target() -> tuple[str, str | None, str | None] | None:
    """Prompt for the target DB. Returns (to, dsn, db) or None if cancelled."""
    target = questionary.select(
        "Target database:",
        choices=["SQLite (file)", "PostgreSQL"],
    ).ask()
    if target is None:
        return None
    if target.startswith("PostgreSQL"):
        dsn = questionary.text(
            "PostgreSQL connection string (blank = use TG_IMPORTER_DSN env):"
        ).ask()
        return "postgres", (dsn or None), None
    db = questionary.path(
        "SQLite file path (created if it doesn't exist):", default="chat.db"
    ).ask()
    if db is None:
        return None
    return "sqlite", None, db


def _do_import() -> None:
    from .cli import perform_load  # lazy import avoids an import cycle

    path = questionary.path("Path to the export folder or result.json:").ask()
    if not path:
        return

    target = _ask_target()
    if target is None:
        return
    to, dsn, db = target

    copy_media = questionary.confirm(
        "Copy media files into a managed store?", default=False
    ).ask()
    media_dir = None
    if copy_media:
        media_dir = (
            questionary.path("Media store folder (blank = default location):").ask()
            or None
        )
    export_date = (
        questionary.text("Export date override YYYY-MM-DD (blank = auto):").ask()
        or None
    )

    print()
    try:
        perform_load(
            path=path,
            to=to,
            dsn=dsn,
            db=db,
            export_date=export_date,
            copy_media=copy_media,
            media_dir=media_dir,
        )
    except Exception as e:  # keep the menu alive on any failure
        print(f"\nImport failed: {type(e).__name__}: {e}")
    print()


def _do_init_db() -> None:
    from .cli import perform_init_db

    target = _ask_target()
    if target is None:
        return
    to, dsn, db = target

    print()
    try:
        perform_init_db(to=to, dsn=dsn, db=db)
    except Exception as e:
        print(f"\nFailed: {type(e).__name__}: {e}")
    print()


def run_wizard() -> None:
    print(f"tg-history-importer {__version__} — interactive mode\n")
    while True:
        action = questionary.select(
            "What do you want to do?",
            choices=[
                questionary.Choice("Import a chat export", value="import"),
                questionary.Choice("Create database tables only", value="init"),
                questionary.Choice("Show version", value="version"),
                questionary.Choice("Exit", value="exit"),
            ],
        ).ask()

        if action in (None, "exit"):
            break
        if action == "import":
            _do_import()
        elif action == "init":
            _do_init_db()
        elif action == "version":
            print(f"{__version__}\n")

    print("Bye.")
