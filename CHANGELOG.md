# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), und das Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

Bis `v1.0.0` gilt: Jede Phase aus dem [FAHRPLAN](FAHRPLAN.md) entspricht einem Minor-Release (`v0.N.0`). `v1.0.0` markiert den produktionsreifen Abschluss von Phase 11.

---

## [Unreleased]

### Added

- **Phase 0 — Repo-Setup & Konventionen:** uv-basiertes Python-Projekt (`pyproject.toml`, `uv.lock`), Python 3.12.
- Tooling: ruff (Lint + Format), mypy strict (mit `pydantic.mypy`), pytest, commitizen.
- Pre-Commit-Hooks (ruff, ruff format, mypy, commitizen) als `local`-Hooks über `uv run`.
- GitHub-Actions-CI: `lint`, `format-check`, `typecheck`, `test`, `commit-check`, `docker-build` (mit Guard bis Phase 1).
- Vertragsdateien an ihren Zielpfaden: `backend/shared/types.py`, `backend/shared/errors.py`, `backend/backends/base.py` (unverändert übernommen).
- Setup-Smoke-Test für die Importierbarkeit der Verträge (`tests/`).
- Frontend-Skelett: Vite + React + TypeScript (strict), ESLint (Flat-Config) + Prettier.
- `scripts/bootstrap-runpod.py` als CLI-Skelett (Vollausbau in Phase 3).
- Projektdateien: `.gitignore`, `.gitattributes` (LF-Normierung), `.env.example`, `LICENSE` (proprietär), PR- und Issue-Templates.

### Changed

- (noch nichts)

### Fixed

- (noch nichts)

### Removed

- Alter Prototyp: `aima/`-Python-Code, altes `frontend/`-React-Setup, `requirements.txt`.

---

<!--
Vorlage für neue Versions-Abschnitte beim Phasen-Abschluss:

## [v0.N.0] — YYYY-MM-DD — Phase N: <Titel>

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Removed
- ...
-->
