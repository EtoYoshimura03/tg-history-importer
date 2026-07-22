"""tg-history-importer — import Telegram chat exports into PostgreSQL or SQLite."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: the version declared in pyproject.toml, read from
    # the installed package metadata. Bump the number only in pyproject.toml.
    __version__ = version("tg-history-importer")
except PackageNotFoundError:  # running from source without an install
    __version__ = "0.0.0+dev"

