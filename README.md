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

> The examples use the bare `tg-history-importer` command, which is available
> once the package is installed **on your PATH** — inside an activated
> virtualenv, or via a global install (`pipx install .`). If you use **uv**
> without activating the venv, prefix every command with `uv run`, e.g.
> `uv run tg-history-importer load ...`. (Activate instead with
> `.venv\Scripts\activate` on Windows, `source .venv/bin/activate` on Unix.)

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
| `--copy-media` | load | copy media files into a managed store |
| `--media-dir` | load | store location (or `TG_IMPORTER_MEDIA_DIR` env) |
| `--verbose` / `-v` | load | print per-batch insert progress |

Copy media into a managed store while importing:

```bash
tg-history-importer load ./ChatExport_2026-07-18 --to sqlite --db ./chat.db \
  --copy-media --media-dir ./media_store
```

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
- **Media metadata** is always stored: the relative path, name, size, MIME,
  type, dimensions and duration; the files themselves stay in the export folder.
- **Media files** are copied only with **`--copy-media`**. Each file (and its
  thumbnail) is copied into a store addressed by **sha256**
  (`<store>/ab/<sha256>.<ext>` — at most 256 shard folders), so identical files
  (repeated stickers/gifs)
  are stored once. The row then also carries `media_sha256`, `stored_path` and
  `stored_thumbnail_path`. Store location: `--media-dir` /
  `TG_IMPORTER_MEDIA_DIR`, else the OS per-user data dir (`platformdirs`:
  `%LOCALAPPDATA%` on Windows, `~/Library/Application Support` on macOS,
  `~/.local/share` on Linux). Files referenced but not present on disk are
  counted as *missing* and skipped.
- **What the store is for right now.** It is a **backend/archive**, not a
  browse-by-hand folder: files are named by hash and spread across shard folders,
  so the only link from a message to its file lives in the database. Its current
  value is exactly the three things above — **durability** (media survives
  deleting the export folder), **deduplication**, and a **precise DB→file link**
  a program can resolve. Human-friendly retrieval (pull a chat's media into a
  readable folder) is a planned *media management* step — see the Roadmap.
- **Media is copied only for newly-inserted messages** (the same dedup as above).
  Consequences of re-running `--copy-media`:
  - *Media folder deleted, DB kept* → media is **not** restored: every message is
    a duplicate, so nothing is re-inserted and nothing is re-copied. To rebuild
    the store, recreate the rows too (drop the DB / re-import the chat).
  - *DB deleted, media folder kept* → works fine: rows are re-inserted and each
    already-present file is reused via hash (counted as *deduplicated*), with
    `stored_path` set correctly. No duplication on disk.
- **Export date vs load date** are stored separately (`import_logs.export_date`
  vs `loaded_at`) — they legitimately differ. Export date is detected from the
  `ChatExport_YYYY-MM-DD` folder name, else `--export-date`, else file mtime.

## Schema

`messages`: `id, chat_id, chat_name, chat_type, message_id, message_type,
action, user_id, user_name, from_id_raw, message, date, date_unixtime, edited,
reply_to_message_id, reply_to_text, forwarded_from, media_type, mime_type,
file_path, file_name, file_size, thumbnail, duration_seconds, width, height,
media_sha256, stored_path, stored_thumbnail_path, import_id` — unique on
`(chat_id, message_id)`. The `media_sha256` / `stored_*` columns are filled only
when importing with `--copy-media`.

`import_logs`: `id, loaded_at, export_date, actor, hostname, source_path,
db_target, export_chat_id, export_chat_name, export_chat_type, export_file_name,
export_file_size, export_max_date_unixtime, prepared_rows, inserted_rows,
skipped_by_id, service_rows, media_copied, media_deduplicated, media_missing,
errors_count, errors_preview`.

`chat_type` mirrors the export's top-level type — `personal_chat` (a 1:1
dialog), `bot_chat`, `private_group`, `public_supergroup`, `private_channel`,
etc. Filter dialogs with `WHERE chat_type = 'personal_chat'`.

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

### ✅ v0.1.0 — first release
- [x] CLI (`load` / `init-db`)
- [x] JSON export → PostgreSQL & SQLite
- [x] `messages` + `import_logs`, dedup, service events, media metadata

### 🚧 v0.2.0 — media store
- [ ] `--copy-media`: copy files into a managed store
- [ ] content-addressed by hash (dedup identical media)
- [ ] cross-platform default location (`platformdirs`)

### 📦 Next — standalone binary
- [ ] package the CLI as a single executable (PyInstaller / Nuitka) so a
      **non-programmer can run it and get the console** without installing Python
- [ ] per-OS builds (Windows / Linux / macOS) attached to GitHub Releases

### 🗺️ Later
- [ ] **Media management** — export a chat's/user's media into a readable folder
      by filters (chat / user / date), with original file names; and other media
      ops. Turns the content-addressed store into something usable by hand.
- [ ] HTML export support
- [ ] MySQL / SQL Server targets
- [ ] streaming parser for very large exports
- [ ] optional S3 / object-storage backend
- [ ] verified Linux & macOS support
- [ ] query/export layer — pull messages by user (`user_id` / `user_name`) or
      chat, with date-range, sorting and filters, written to a file (backend
      for the GUI)
- [ ] GUI — import an export file, search/compile by user or chat, export results

### 🏁 v1.0.0 — stable
- [ ] feature-complete & stable

**Order:** media store (0.2.0) → standalone binary → media management /
HTML / more DBs → cross-platform → query/export layer → GUI.

## Versioning

[SemVer](https://semver.org): `0.1.X` = fixes, `0.X.0` = features,
`X.0.0` = the first stable line. See [CHANGELOG.md](CHANGELOG.md).

## License

[GNU GPLv3](LICENSE). Derivatives must remain open under the same license.
