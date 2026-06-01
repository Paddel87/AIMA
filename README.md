# AIMA

**AI Media Analysis System** — modulares KI-gestütztes Medienanalyse- und Auswertungssystem zur automatisierten Erkennung, Wiedererkennung, Kontextbewertung und semantischen Zusammenführung von Bild- und Videoinhalten.

> **Projektstatus:** Phase 0 — Repo-Setup & Konventionen. Kein lauffähiger Code, nur Rahmen.
> Aktueller Tag: —
> Details siehe [FAHRPLAN.md](FAHRPLAN.md).

---

## Was ist das?

AIMA analysiert Bild- und Videomaterial mit mehreren spezialisierten KI-Modulen (Personenerkennung, Re-Identifizierung, Objekterkennung, NSFW-Klassifikation, Kontextanalyse, Bildbeschreibung) und führt die Einzelbefunde zu einem verwertbaren Gesamtbild zusammen. Vollständig browserbasiert, DSGVO-konform, für 2–3 gleichzeitige Nutzer ausgelegt.

Die Architektur in einem Satz: FastAPI + Celery + Redis + PostgreSQL auf einem VPS, React-Frontend, GPU-Analyse über RunPod Serverless, optionale externe APIs (Google AI Studio, xAI) für nicht-sensible Module.

Für das volle Bild → [KONZEPT.md](KONZEPT.md).

## Schnellstart

**Voraussetzungen:** Python ≥ 3.12, `uv`, Node ≥ 20, Docker + Compose v2, `gh`.

```bash
# Klonen und einrichten
git clone git@github.com:Paddel87/AIMA.git
cd aima
uv sync
cd frontend && npm install && cd ..
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
cp .env.example .env  # dann lokale Werte eintragen

# Lokale Laufzeitumgebung starten (ab Phase 1)
docker compose up

# Smoketest
uv run ruff check .
uv run mypy .
uv run pytest
```

Volle Setup-Anleitung → [CONTRIBUTING.md §1](CONTRIBUTING.md).

## Dokumentation

| Datei                              | Inhalt                                                       |
| ---------------------------------- | ------------------------------------------------------------ |
| [CLAUDE.md](CLAUDE.md)             | Nord-Stern für jede Claude-Code-Session — zuerst lesen       |
| [KONZEPT.md](KONZEPT.md)           | Architektur, Datenmodell, Systemgrenzen                      |
| [FAHRPLAN.md](FAHRPLAN.md)         | Phasenplan + Status + Akzeptanzkriterien                     |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setup, Branches, Commits, CI, PR- und Phasen-Ritual          |
| [CHANGELOG.md](CHANGELOG.md)       | Änderungshistorie nach Keep-a-Changelog                      |

## Stack

- **Backend:** Python 3.12, FastAPI, Celery, Redis, SQLAlchemy, Alembic
- **Frontend:** React, Vite, TypeScript, React Query, Zustand
- **Datenbank:** PostgreSQL 16 + pgvector
- **Auth:** JWT, Rollen Admin / Analyst
- **KI-Backends:** RunPod Serverless (sensible Module), Google AI Studio / xAI (nur optionale Kontextmodule)
- **Deployment:** Docker Compose auf VPS, Nginx als Reverse Proxy

## Entwicklungsmodell

Vision-Driven Development mit autonomer KI-Implementierung. Die Spezifikation und die Vertragsdateien sind der Input, aus dem Code entsteht. Details zur Arbeitsweise in [CLAUDE.md](CLAUDE.md).

## Lizenz

Proprietär. Kein Teil dieses Repositorys darf ohne explizite Zustimmung des Eigentümers kopiert, weitergegeben oder veröffentlicht werden.
