# tg-history-importer

Import **Telegram chat exports** into a real SQL database — **PostgreSQL** or
**SQLite** — with a full audit log of every import run.

Point it at a Telegram Desktop export (`result.json`) and it fills two tables:

- **`messages`** — one row per message *and* per service event (joins, pins,
  calls, …), including media metadata.
- **`import_logs`** — one row per import run: what was loaded, when, from where,
  how many rows, and any errors.

> Status: **v0.1.0** — first release. JSON export → PostgreSQL / SQLite,
> metadata-only for media. See the [Roadmap](#roadmap).

---

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/EtoYoshimura03/tg-history-importer.git
cd tg-history-importer

# SQLite only:
pip install -e .

# with PostgreSQL support:
pip install -e .[postgres]
```

This installs a `tg-history-importer` command.

## Get a Telegram export

In **Telegram Desktop**: open the chat → ⋮ → **Export chat history** →
format **JSON (machine-readable)** → export. You get a folder like
`ChatExport_2026-07-18/` containing `result.json` and media subfolders
(`photos/`, `video_files/`, `voice_messages/`, …).

## Usage

**SQLite** (a single local file, zero setup):

```bash
tg-history-importer load ./ChatExport_2026-07-18 --to sqlite --db ./chat.db
```

**PostgreSQL** (local or remote):

```bash
export TG_IMPORTER_DSN="postgresql+psycopg://user:pass@localhost:5432/tg_history"
tg-history-importer load ./ChatExport_2026-07-18 --to postgres
# or pass it explicitly:
tg-history-importer load ./result.json --to postgres --dsn "postgresql://user:pass@host/db"
```

You can pass either the **export folder** or the **`result.json`** file directly.

Create the tables without importing:

```bash
tg-history-importer init-db --to sqlite --db ./chat.db
```

### Options

| Option | Applies to | Meaning |
|---|---|---|
| `--to` | all | `sqlite` or `postgres` |
| `--db` | sqlite | path to the `.db` file (created if missing) |
| `--dsn` | postgres | connection string (or `TG_IMPORTER_DSN` env) |
| `--export-date` | load | `YYYY-MM-DD`; override date detection |
| `--batch-size` | load | insert batch size (default 1000) |

## How it works

- **Time** is taken from `date_unixtime` (reliable UTC). The human `date` field
  in the export is the exporter's *local* time and is ignored.
- **All timestamps are stored in UTC.** On PostgreSQL they are timezone-aware
  (`timestamptz`), so a client like DBeaver shows them converted to your local
  zone. On SQLite there is no timezone type, so the same UTC value is stored as
  plain text with no offset — a value like `01:22:22` is UTC, not local time.
- **Dedup**: rows are unique on `(chat_id, message_id)`. Re-importing the same
  (or an overlapping) export inserts only new messages; duplicates are counted
  and skipped. Safe to run repeatedly.
- **Service events** (`type: "service"`) are stored too, with `message_type =
  'service'` and the event name in `action`. Filter them out any time with
  `WHERE message_type = 'message'`.
- **Media** in v1 is **metadata-only**: the relative path, name, size, MIME,
  type, dimensions and duration are stored; the files themselves are left in the
  export folder. Copying media into a managed store is planned (see Roadmap).
- **Export date vs load date** are stored separately (`import_logs.export_date`
  vs `loaded_at`) — they legitimately differ. Export date is detected from the
  `ChatExport_YYYY-MM-DD` folder name, else `--export-date`, else file mtime.

## Schema

`messages`: `id, chat_id, chat_name, message_id, message_type, action, user_id,
user_name, from_id_raw, message, date, date_unixtime, edited,
reply_to_message_id, reply_to_text, forwarded_from, media_type, mime_type,
file_path, file_name, file_size, thumbnail, duration_seconds, width, height,
import_id` — unique on `(chat_id, message_id)`.

`import_logs`: `id, loaded_at, export_date, actor, hostname, source_path,
db_target, export_chat_id, export_chat_name, export_file_name, export_file_size,
export_max_date_unixtime, prepared_rows, inserted_rows, skipped_by_id,
service_rows, errors_count, errors_preview`.

## Development

With plain **pip**:

```bash
pip install -e .[dev,postgres]
pytest
```

With **[uv](https://docs.astral.sh/uv/)** (optional, faster — recommended):

```bash
uv venv                                # create .venv
uv pip install -e ".[dev,postgres]"    # install deps
uv run pytest                          # run tests (no manual venv activation)
```

`uv` reads this project's standard `pyproject.toml` — nothing project-specific
to configure. It never becomes a requirement for end users; `pip install` keeps
working.

Layout: `src/tg_history_importer/` — `parser.py` (export → rows), `models.py`
(SQLAlchemy schema), `db.py` (engine, dedup, inserts), `cli.py` (Typer).

Branching: **GitHub Flow** — `main` is always releasable; work on `feature/*`
branches via PR. Releases are **git tags** following **SemVer** (`v0.1.0`).
A read-only mirror is kept on
[Codeberg](https://codeberg.org/EtoOwl/tg-history-importer).

## Roadmap

- **0.2.0** — copy media into a managed local store (`--copy-media`), content-
  addressed by hash, cross-platform default location.
- **0.x** — HTML export support; MySQL / SQL Server targets; streaming parser
  for very large exports; optional S3/object-storage backend.
- **Cross-platform** — verified Linux & macOS support (paths, media store,
  tested installs). Prerequisite for the GUI below.
- **Query/export layer** — CLI command to pull messages by user
  (`user_id` / `user_name`) or by chat, with **date-range**, **sorting** and
  **filters**, written out to a file (CSV/JSON). Includes `chat_name` +
  `chat_id` per row. This is the backend the GUI builds on.
- **GUI (after cross-platform)** — desktop app that:
  - picks an export file from disk and imports it (wraps `load`);
  - searches / compiles messages by user or chat, with date filter, sorting
    and column filters;
  - exports the result of a user/chat query to a file.
- **1.0.0** — when the feature set is complete and stable.

**Order:** media store (0.2.0) → HTML / more DBs → cross-platform →
query/export layer → GUI. The media store lands **before** the query/export
backend and the GUI.

## Versioning

[SemVer](https://semver.org): `0.1.X` = fixes, `0.X.0` = features,
`X.0.0` = the first stable line. See [CHANGELOG.md](CHANGELOG.md).

## License

[GNU GPLv3](LICENSE). Derivatives must remain open under the same license.
