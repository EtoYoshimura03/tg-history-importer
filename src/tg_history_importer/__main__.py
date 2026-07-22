"""Entry point for `python -m tg_history_importer` and the PyInstaller build.

Uses an absolute import so it works both as a module and as the script passed
to PyInstaller (relative imports would break when run as a top-level script).
"""

from __future__ import annotations

from tg_history_importer.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
