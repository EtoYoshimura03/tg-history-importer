# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Path inputs (export path, SQLite `--db`, `--media-dir`) now tolerate
  surrounding quotes, so Windows "Copy as path" values work as-is in both the
  CLI and the interactive menu.
- `load` and `init-db` now print the **absolute SQLite file path** they use, so
  it's clear where a relative `--db` (e.g. the default `chat.db`) is created.
  The file, its parent folders and tables are all created automatically.
- **Interactive mode**: running with no command (e.g. a double-clicked binary)
  opens a guided menu (import / init-db / version) that prompts for inputs and
  keeps the console open. Passing a subcommand still runs directly. Load/init-db
  logic factored into `perform_load` / `perform_init_db`, shared by CLI + wizard.
  Built on `questionary` (new dependency): arrow-key menus, path completion and
  working paste (Ctrl+V / right-click) in any Windows console host.
- **Standalone binary**: `python -m tg_history_importer` entry point plus a
  PyInstaller build and a `.github/workflows/release.yml` that builds Windows /
  Linux / macOS executables on each `v*` tag and attaches them to the GitHub
  Release. New optional dependency group `build` (`pip install .[build]`).
- **Managed media store** (`--copy-media`): copies each media file and its
  thumbnail into a content-addressed store (sha256, sharded), deduplicating
  identical files. Location via `--media-dir` / `TG_IMPORTER_MEDIA_DIR`, else the
  OS per-user data dir (`platformdirs`). New columns: `messages.media_sha256`,
  `stored_path`, `stored_thumbnail_path`; `import_logs.media_copied`,
  `media_deduplicated`, `media_missing`. Missing files are counted and skipped.
- `load` now reports batch count (`in N batch(es) of M`) and accepts
  `--verbose`/`-v` for per-batch insert progress.
- Chat type captured from the export: `messages.chat_type` and
  `import_logs.export_chat_type` (e.g. `personal_chat` for a 1:1 dialog vs
  `public_supergroup`). Filter dialogs with `WHERE chat_type = 'personal_chat'`.

### Docs
- README: note that the `tg-history-importer` command needs an activated venv
  or `uv run` prefix; checklist-style Roadmap.

## [0.1.0] - unreleased

First release.

### Added
- CLI (`tg-history-importer`) with `load`, `init-db` and `version` commands.
- Import of Telegram Desktop JSON exports (`result.json`).
- Targets: **SQLite** (file) and **PostgreSQL** (via SQLAlchemy).
- Two tables: `messages` and `import_logs`.
- Both regular messages and service events stored (`message_type` + `action`).
- Media **metadata** captured (path, name, size, MIME, type, duration, size).
- Dedup by `(chat_id, message_id)` — safe to re-run on overlapping exports.
- Export date detection (folder name / `--export-date` / file mtime), stored
  separately from load time.
- Parser unit tests + fixture.

[Unreleased]: https://github.com/EtoYoshimura03/tg-history-importer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/EtoYoshimura03/tg-history-importer/releases/tag/v0.1.0
