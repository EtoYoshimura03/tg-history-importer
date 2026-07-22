# AGENTS.md — hints for AI agents working on this repo

> This file is for AI coding agents (Claude, Cursor, …). Humans: read
> [README.md](README.md) first — it explains what the tool does and how to use
> it. This file only adds machine-oriented working rules.

## What this project is

A standalone CLI that imports Telegram chat exports (`result.json`) into
PostgreSQL or SQLite. It is a spin-off / rewrite of an internal Telegram bot's
importer, decoupled from BigQuery and aiogram. Two output tables: `messages`
and `import_logs`.

## Map

- `src/tg_history_importer/parser.py` — pure functions: export JSON → list of
  row dicts. No DB, no I/O side effects beyond reading the file. Start here for
  any "how is field X handled" question.
- `src/tg_history_importer/models.py` — SQLAlchemy Core table definitions. The
  single source of truth for the schema.
- `src/tg_history_importer/db.py` — engine construction, `init_db`, dedup query,
  batched inserts. Dialect-agnostic on purpose.
- `src/tg_history_importer/media.py` — managed media store (`--copy-media`):
  sha256 content-addressing, dedup, copy. **All media filesystem I/O lives
  here**, not in `parser.py`.
- `src/tg_history_importer/cli.py` — Typer commands `load` / `init-db` /
  `version`. Wires parser + media + db together.
- `tests/` — pytest; `tests/fixtures/sample_result.json` is the canonical tiny
  export used by tests.

## Running

- Recommended dev flow is **uv**: `uv venv --python 3.12`,
  `uv pip install -e ".[dev,postgres]"`, `uv run pytest`.
- The `tg-history-importer` console command only exists on PATH inside an
  activated venv or a global install. When giving the maintainer a command,
  prefix it with `uv run` (e.g. `uv run tg-history-importer load ...`) unless
  the venv is known to be activated.

## Rules

- **One schema, all dialects.** Do not fork the schema per database. Add columns
  in `models.py` only; both SQLite and PostgreSQL get them via `create_all`.
- **Dedup is `(chat_id, message_id)`.** Preserve the UNIQUE constraint and the
  Python-side "fetch existing ids → filter → insert" flow. It gives exact
  counts and avoids dialect-specific UPSERT. Do not switch to `ON CONFLICT`
  without a reason.
- **Time comes from `date_unixtime` (UTC).** Never trust the human `date` field
  for storage — it is the exporter's local time.
- **Media metadata is always stored; files are copied only with `--copy-media`**
  (see `media.py`: sha256 content-addressing, dedup, thumbnails). Default store
  location is `platformdirs` user data dir; overridable via `--media-dir` /
  `TG_IMPORTER_MEDIA_DIR`. Handle permission errors with a clear message.
- **Both message and service rows are stored** (`message_type` + `action`).
  Don't drop service events.
- **Keep parser side-effect-free** so it stays unit-testable without a database.
  Media file I/O belongs in `media.py`, invoked from `cli.py` — never in
  `parser.py`.
- **Keep insert-row keys uniform.** Every row dict from `parser.py` must carry
  the same keys (the batched `insert(messages)` compiles from the first row).
  New nullable columns get a `None` default in the parser's row dict.

## Conventions

- Python 3.10+. Type hints with `from __future__ import annotations`.
- Match existing docstring/comment density and style when editing.
- Add/adjust tests in `tests/` for any parser change; keep the fixture minimal.
- SemVer + Keep-a-Changelog: user-visible changes go in `CHANGELOG.md` under
  `## [Unreleased]`.
- **No copy-paste placeholders in commands.** When giving the maintainer a
  command to run, never use fillers that could be pasted verbatim (`<...>`,
  `...` inside a path, `<paste_here>`). Use the real value when known, or an
  UPPERCASE marker that cannot be mistaken for valid input (`PASTE_TOKEN_HERE`,
  `__REPLACE_ME__`). Windows paths with spaces must be double-quoted.

## Git — IMPORTANT

The maintainer performs **all** git write operations: creating branches,
commits, tags, pushes, merges. An agent must **not** run `git commit`,
`git push`, `git tag`, `git merge`, or create branches. Make the edits, leave a
clean working tree, and report status. If a new branch is needed, ask the
maintainer to create it and provide the name.

## Don't-break list

- The `messages(chat_id, message_id)` uniqueness (dedup correctness).
- `import_logs.export_date` being separate from `loaded_at`.
- Reading exports as UTF-8 (Cyrillic content is common).
