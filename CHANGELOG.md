# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `load` now reports batch count (`in N batch(es) of M`) and accepts
  `--verbose`/`-v` for per-batch insert progress.

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
