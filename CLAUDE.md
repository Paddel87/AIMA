# CLAUDE.md

> Gedächtnis und Nord-Stern für jede Claude-Code-Session in diesem Repository.
> Lies diese Datei **zuerst**. Wenn sie widerspricht, was du im Code siehst, hat der Code recht – dann aktualisiere diese Datei am Ende der Session.
>
> **Ausnahme:** Die Vertragsdateien (siehe §3) und die Architektur-Grundentscheidungen in [KONZEPT.md](KONZEPT.md) haben Vorrang vor dem Code. Wenn der Code ihnen widerspricht, ist der Code falsch – frag zurück, statt zu „harmonisieren".

---

## 1. Was ist dieses Projekt?

**AIMA – AI Media Analysis System** – modulares, KI-gestütztes Medienanalysesystem zur automatisierten Erkennung, Wiedererkennung, Kontextbewertung und semantischen Zusammenführung von Bild- und Videoinhalten. Primärer Anwendungsfall: Aufklärung von Vorfällen, bei denen im Unternehmens-Intranet sexuell explizite Materialien von Mitarbeitenden hochgeladen werden.

- **Markenname:** `AIMA` (nur in UI-Texten)
- **Technischer Name:** `aima` (snake_case in Code und Ordnern)
- **Lizenz:** proprietär, privates Repo auf GitHub: `Paddel87/AIMA`
- **Primärsprache (Kommunikation & Doku):** Deutsch
- **Entwicklungsmodell:** Vision-Driven Development mit autonomer KI-Implementierung. Spezifikation und Verträge sind der Input, aus dem Code entsteht.

## 2. Aktueller Stand

**Single Source of Truth für Status:** [FAHRPLAN.md](FAHRPLAN.md) → „🗺️ Meilensteine im Überblick".

Wenn du Stand brauchst:

```bash
git log --oneline -5
git tag --sort=-creatordate | head -3
grep -A 15 "## 🗺️" FAHRPLAN.md
```

Aktueller Release-Tag und die zugehörige Phase gelten als „erledigt". Alles darüber hinaus ist offen.

## 3. Wie du hier arbeitest

### Grundprinzipien (aus [FAHRPLAN.md](FAHRPLAN.md) §Leitlinien)

- **Bottom-to-Top.** Erst Infrastruktur, dann Verträge, dann Module, dann UI. Keine vorgezogenen Kür-Features.
- **Vertikale Scheiben ab Phase 3.** Backend + Worker + ggf. Frontend + Tests + Doku gemeinsam.
- **MVP vor Kür.** Der MVP endet nach Phase 8 (Personen-Ansicht + Reporting). Alles darüber hinaus ist Härtung oder Post-MVP.
- **DSGVO by Design.** In _jeder_ Phase mitdenken – nicht anhängen.
- **Namenskonvention strikt einhalten.** `AIMA` ausschließlich in UI-Text, `aima` in Code/Ordnern.

### Vertragsdateien (heilig)

Folgende Dateien legen die Verträge fest, gegen die alles andere programmiert wird. **Änderungen nur mit expliziter User-Freigabe.** Wenn der Code einer dieser Dateien widerspricht, ist der Code falsch – frag zurück.

- `backend/shared/types.py` – geteilte Datenklassen (`Frame`, `Detection`, `PersonEmbedding`, …)
- `backend/shared/errors.py` – Fehlerhierarchie mit Retry-Semantik
- `backend/backends/base.py` – `AnalysisBackend`-ABC
- Alembic-Baseline-Migration (`backend/db/alembic/versions/0001_*.py`)

### Tech-Stack (fest verdrahtet – siehe [KONZEPT.md](KONZEPT.md))

- **Backend:** Python 3.12 + FastAPI + Celery + Redis + SQLAlchemy + Alembic (strict mypy)
- **Frontend:** React + Vite + TypeScript (strict) + React Query (Serverstate) + Zustand (UI-State)
- **DB:** PostgreSQL 16 + pgvector (Extensions: `pgvector`, `pgcrypto`)
- **Auth:** JWT, zwei Rollen (Admin / Analyst)
- **Analyse-Backends:** RunPod Serverless (sensible Module), Google AI Studio und xAI / Grok (nur Kontextanalyse und Bildbeschreibung)
- **Paketmanager Python:** `uv` (nicht poetry, nicht pip-tools)
- **Linter/Formatter:** `ruff` + `ruff format`
- **Typecheck:** `mypy --strict`
- **Tests:** `pytest` + `testcontainers-python` (Unit + Integration), `playwright` (E2E ab Phase 7)
- **Pre-Commit:** `pre-commit` (Python-Ökosystem), Commits via `commitizen`

### Entwicklungs-Workflow (Pflicht)

Detailliert in [CONTRIBUTING.md](CONTRIBUTING.md). Kernregeln:

1. **Branch-Präfixe:** `feature/`, `fix/`, `docs/`, `chore/`, `refactor/`, `test/`.
2. **Commits:** Conventional Commits (erzwungen via `commitizen` pre-commit-Hook und CI). Erlaubte Typen: `feat, fix, docs, chore, refactor, test, build, ci, perf, revert, style`.
3. **Kein Direct-Push auf `main`.** Alles läuft über PR mit grüner CI.
4. **Squash-Merge für Phasen-Abschluss-PRs**, damit auf `main` pro Phase genau ein Commit entsteht. Sonst normaler Merge.
5. **CI muss grün sein:** `lint` (ruff), `format-check` (ruff format), `typecheck` (mypy strict), `test` (pytest), `commit-check` (commitizen), `docker-build` (backend + worker + frontend).
6. **Pre-Commit-Hooks** feuern lokal. Nicht mit `--no-verify` umgehen.

### Phasen-Abschluss-Ritual

Jede Phase endet mit:

1. **Akzeptanzkriterien grün** (aus FAHRPLAN, funktional + nicht-funktional lokal verifizieren).
2. **Doku aktualisiert:** CHANGELOG unter `[Unreleased]`, FAHRPLAN-Status-Spalte, README-Statusbadges, KONZEPT bei konzeptionellen Änderungen.
3. **PR mit grüner CI → Squash-Merge auf `main`.**
4. **Tag `v0.N.0`** (annotiert, mit Release-Notes) + GitHub-Release.
5. **Diese Datei (`CLAUDE.md`) aktualisieren**, falls sich Konventionen oder Stand geändert haben.

### Was du **nicht** tust

- Features über die aktuelle Phase hinaus implementieren, ohne den User zu fragen.
- Vertragsdateien (siehe oben) ohne explizite User-Freigabe ändern.
- Post-MVP-Features berühren (FAHRPLAN §Post-MVP-Sperre):
  - Graph-Visualisierung der Ko-Vorkommen
  - Face-Search über eigenes Referenzbild
  - Mehrmandantenfähigkeit
  - Programmatische Endpoint-Verwaltung durch AIMA zur Laufzeit
  - Alternative Backends jenseits RunPod / Google AI / xAI
- Gesichts- oder NSFW-Daten an externe APIs (Google AI, xAI) senden. Sensible Module laufen ausschließlich über RunPod.
- Code-Pfade einbauen, die ML-Jobs (RunPod-Calls) ohne explizite Benutzeraktion auslösen. **AIMA startet keine ML-Aufgaben autonom** (siehe KONZEPT §4.3). Keine Watch-Folder, keine Cron-Jobs, kein Auto-Trigger nach Upload, keine kaskadierenden Auto-Starts, keine Auto-Reanalyse nach Modell-Update. Erlaubt sind nur Retries innerhalb eines bereits vom Nutzer gestarteten Jobs.
- RunPod-Endpoints zur Laufzeit erstellen, ändern oder löschen. Endpoints werden manuell in der RunPod-Console angelegt, die IDs liegen in `.env`.
- RunPod-Handler-Images im AIMA-Repo bauen. Handler sind separate Docker-Projekte (eigenes Unterverzeichnis oder eigenes Repo, Entscheidung in Phase 3).
- Echte personenbezogene Daten in Tests, Seeds oder Commits. Testdaten sind synthetisch oder aus lizenzfreien Quellen.
- Den Paketmanager wechseln (`uv` ist Konsens).
- Direkt auf `main` committen.
- `.env` oder sonstige Geheimnisse committen (nur `.env.example` pflegen).
- Pre-Commit-Hooks mit `--no-verify` umgehen.
- Persistente RunPod-Pods verwenden (Serverless ist fest, siehe KONZEPT §8.1).

## 4. Vor jedem größeren Schritt

1. `git status && git log --oneline -5` – wo stehen wir?
2. `head -40 FAHRPLAN.md` – welche Phase ist dran?
3. `head -30 CHANGELOG.md` – was steht unter `[Unreleased]`?
4. Gegen Vertragsdateien und KONZEPT verifizieren, ob der geplante Schritt konsistent ist.
5. Plan mit dem User abstimmen, **bevor** du scaffoldest oder große Änderungen beginnst.

Bei Umgebungs-abhängigen Tasks (Scaffolding, CI, Docker, RunPod): **Toolchain vorab prüfen** (`which python uv docker gh`, `uv --version`, `gh auth status`). Fehlende Tools als eine einzige Liste präsentieren, bevor du loslegst.

## 5. Projekt-Kompass

| Wofür steht...                            | Datei                                    |
| ----------------------------------------- | ---------------------------------------- |
| Projektidee, Architektur, Datenmodell     | [KONZEPT.md](KONZEPT.md)                 |
| Phasen-Plan + Meilensteine + Status       | [FAHRPLAN.md](FAHRPLAN.md)               |
| Änderungshistorie                         | [CHANGELOG.md](CHANGELOG.md)             |
| Entwickler-Workflow                       | [CONTRIBUTING.md](CONTRIBUTING.md)       |
| Schnellstart & Projektüberblick           | [README.md](README.md)                   |
| Datenbank-Init                            | [backend/db/README.md](backend/db/README.md) |
| RunPod-Handler (separat)                  | [runpod-handlers/README.md](runpod-handlers/README.md) |

## 6. Kommunikationsstil

- Deutsch, knapp, auf den Punkt.
- Vor dem Implementieren kurz Plan skizzieren und Freigabe einholen.
- Tool-Outputs nicht narrieren – nur Ergebnisse/Entscheidungen melden.
- Fehler direkt mit Ursache und Fix erklären, nicht wortreich drum herumreden.
- Bei Unsicherheit fragen, statt raten. Besonders wenn Vertragsdateien oder KONZEPT betroffen sein könnten.

---

_Wenn du diese Datei nicht gelesen hast, hast du die Aufgabe noch nicht verstanden. Lies sie, dann fang an._
