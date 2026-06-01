# FAHRPLAN.md

> Phasenplan für die Entwicklung von AIMA (AI Media Analysis System).
> Single Source of Truth für den Projektstand. Änderungen nur per PR mit Phasen-Abschluss-Ritual.

---

## Leitlinien

- **Bottom-to-Top.** Erst Infrastruktur, dann Verträge, dann Module, dann UI.
- **Vertikale Scheiben ab Phase 3.** Backend + Worker + ggf. Frontend + Tests + Doku gemeinsam.
- **MVP endet nach Phase 8** (Personen-Ansicht + Reporting). Alles darüber hinaus ist Nachschärfung oder Post-MVP.
- **DSGVO by Design.** In jeder Phase mitgedacht, nicht nachträglich angeflanscht.
- **Vertragsdateien sind heilig.** Änderungen an `backend/backends/base.py`, `backend/shared/types.py`, `backend/shared/errors.py` und der Alembic-Baseline erfordern explizite User-Freigabe.
- **Benutzersteuerung ist absolut.** AIMA startet niemals selbstständig ML-Aufgaben. Jeder RunPod-Call wird ausschließlich durch eine explizite Benutzeraktion ausgelöst. Keine Watch-Folder, kein Scheduling, kein Auto-Trigger. Details in KONZEPT §4.3.
- **Post-MVP-Features bleiben unberührt.** Siehe Post-MVP-Sperre am Ende dieser Datei.

---

## 🗺️ Meilensteine im Überblick

| Phase | Name | Status | Tag |
| --- | --- | --- | --- |
| 0 | Repo-Setup & Konventionen | ✅ erledigt | `v0.0.0` |
| 1 | Infrastruktur-Gerüst | offen | `v0.1.0` |
| 2 | Backend-Verträge & DB-Schema | offen | `v0.2.0` |
| 3 | Erster RunPod-Handler + Pipeline-Durchstich (NSFW) | offen | `v0.3.0` |
| 4 | Personen-Erkennung + Re-ID | offen | `v0.4.0` |
| 5 | Objekterkennung + Batch-Pipeline | offen | `v0.5.0` |
| 6 | Optionale Module (Kontext, Bildbeschreibung) + Fusion | offen | `v0.6.0` |
| 7 | Frontend-Grundgerüst + Projekt-/Medien-/Jobverwaltung | offen | `v0.7.0` |
| 8 | Personen-Ansicht + Reporting **(MVP-Ende)** | offen | `v0.8.0` |
| 9 | Härtung: Monitoring, Backup, Sicherheit | offen | `v0.9.0` |
| 10 | Personen-Merge/Split | offen | `v0.10.0` |
| 11 | Admin-Schemaerweiterung | offen | `v0.11.0` |
| — | Produktionsreife | — | `v1.0.0` |

---

## Phase 0 — Repo-Setup & Konventionen

**Ziel:** Der leere Raum, in dem ab Phase 1 gearbeitet wird, existiert und hat Regeln.

**Umfang:**

- Repo-Struktur: `backend/`, `frontend/`, `docker/`, `docs/`, `scripts/`
- `pyproject.toml` mit `uv` als Paketmanager, Python 3.12
- Linter/Formatter: `ruff` + `ruff format`, Konfiguration in `pyproject.toml`
- Typecheck: `mypy` strict
- Pre-Commit-Hooks: `ruff`, `ruff format`, `mypy`, `commitizen` (für Conventional Commits)
- Conventional Commits erzwungen
- GitHub Actions CI: `lint`, `format-check`, `typecheck`, `test`, `commit-check`
- Branch-Schutz auf `main`: kein Direct-Push, PR-Pflicht, CI muss grün
- Frontend-Skelett: `package.json` mit Vite, React, TypeScript strict, ESLint, Prettier
- `.gitignore`, `.env.example`, `LICENSE`, `README.md`-Stub, `CHANGELOG.md` mit `[Unreleased]`
- `CLAUDE.md` und `KONZEPT.md` aus der aktuellen Spec abgeleitet
- PR-Template und Issue-Template
- `scripts/bootstrap-runpod.py` als Skelett (CLI-Gerüst, Modul-Konstanten, Help-Text, `--create-all`/`--teardown-all`/`--status`-Flags ohne Implementierung; Vollausbau in Phase 3)

**Akzeptanzkriterien:**

- `git clone` + `uv sync` + `npm install` funktioniert auf einem frischen System
- CI läuft grün auf einem Trivial-PR (z. B. Typo in README)
- Conventional Commits werden lokal (pre-commit) und in CI (commit-check) erzwungen
- Branch-Schutz auf `main` aktiv und getestet

**Was explizit nicht zu Phase 0 gehört:**

- Docker-Compose-Konfiguration (Phase 1)
- Jeglicher Fachcode (Phase 2+)

---

## Phase 1 — Infrastruktur-Gerüst

**Ziel:** Die Laufzeitumgebung steht. Noch kein Fachcode, aber alle Container reden miteinander.

**Umfang:**

- `docker-compose.yml` für lokale Entwicklung: Postgres 16 mit pgvector, Redis 7, FastAPI-Skeleton, Celery-Worker-Skeleton, Nginx-Reverse-Proxy
- Separate Dockerfiles in `docker/` für API, Worker, Frontend
- Health-Checks und Restart-Policies für alle Services
- Alembic initialisiert (noch leere Baseline-Migration)
- `.env.example` vollständig, Secrets-Handling via Docker Compose `env_file`
- FastAPI liefert `/health` zurück, Celery-Worker akzeptiert eine Dummy-Task
- Basis-Logging strukturiert als JSON
- README mit Schnellstart-Anleitung

**Akzeptanzkriterien:**

- `docker compose up` startet alle Services ohne Fehler
- `curl http://localhost/health` antwortet mit 200
- Celery-Worker verbindet sich mit Redis und verarbeitet eine Test-Task
- Alembic-Baseline-Migration existiert, ist leer, aber gültig (`alembic upgrade head` läuft durch)
- Postgres hat `pgvector`-Extension aktiviert

**Was explizit nicht zu Phase 1 gehört:**

- Fachliche Datenmodelle (Phase 2)
- Authentifizierung (Phase 2)
- RunPod-Integration (Phase 3)

---

## Phase 2 — Backend-Verträge & DB-Schema

**Ziel:** Die Verträge und das Datenmodell stehen. Die KI weiß ab hier, wogegen sie programmiert.

**Umfang:**

- **Vertragsdateien** (ab jetzt nur mit User-Freigabe änderbar):
  - `backend/shared/types.py`: `Frame`, `Detection`, `PersonEmbedding`, `AnalysisRequest`, `AnalysisResult`, `JobStatus`, …
  - `backend/shared/errors.py`: `RetriableError`, `TerminalError`, `RateLimitError`, `BackendUnavailableError`, …
  - `backend/backends/base.py`: `AnalysisBackend`-ABC mit Methoden `analyze()`, `health_check()`, Retry-Semantik im Docstring
- Alembic-Baseline-Migration mit allen Tabellen aus KONZEPT §5, inklusive `cooccurrences` mit `first_seen`/`last_seen`
- SQLAlchemy-ORM-Modelle gespiegelt zur Migration
- pgvector-Spalte für Embeddings (Entscheidung in dieser Phase: Spalte in `persons` oder eigene `person_embeddings`-Tabelle)
- JWT-Authentifizierung: Login-Endpoint, Token-Validierung, User-Modelle, zwei Rollen (Admin/Analyst)
- Audit-Log-Infrastruktur (Schreiben funktioniert, wird ab Phase 3 genutzt)
- Unit-Tests gegen die Verträge und das Schema (Testcontainers für Postgres)

**Akzeptanzkriterien:**

- `alembic upgrade head` läuft durch auf frischer DB
- Alle ORM-Modelle laden, `mypy strict` grün
- ABC kann als `FakeBackend` implementiert werden, der Vertrag ist testbar
- Login mit Testuser liefert gültiges JWT
- Unit-Test-Abdeckung für `backend/shared/` und `backend/backends/base.py` bei 100 %

**Was explizit nicht zu Phase 2 gehört:**

- Echtes RunPod-Backend (Phase 3)
- Medien-Import-Endpunkte (Phase 3)

---

## Phase 3 — Erster RunPod-Handler + Pipeline-Durchstich (NSFW)

**Ziel:** Die erste vollständige vertikale Scheibe. Ein Bild wird hochgeladen, landet im Storage, wird von Celery aufgegriffen, per RunPod analysiert, das Ergebnis landet in der DB. Kein Frontend, alles per API.

**Modulauswahl:** **NSFW-Klassifikation** zuerst, weil einfachstes Modul: nur Bild rein, Label raus, keine Person-Merge-Logik, keine Embedding-Komplexität.

**Umfang:**

- Medien-Import-Endpunkt: `POST /api/media`, speichert Datei unter `storage/uploads/`, legt `media_files`-Eintrag an
- Job-Endpunkt: `POST /api/jobs`, startet Celery-Task
- Celery-Pipeline: Medienvorverarbeitung (nur Bild, noch kein Video), Aufruf des NSFW-Backends, Ergebnis in `detections` schreiben
- **NSFW-Handler als separates Docker-Projekt** (Entscheidung in dieser Phase: Unterordner `runpod-handlers/nsfw/` oder eigenes Repo), basierend auf `runpod/base`, `linux/amd64`
- Handler wird manuell gebaut und zu GHCR gepusht
- **`scripts/bootstrap-runpod.py` vollständig implementieren** (Phase-0-Skelett ausbauen): Provisionierungs-Sequenz Volume → Template → Endpoint via REST/GraphQL-API; Idempotenz per Namens-Konvention (zweiter Lauf erkennt existierende Endpoints und legt nichts doppelt an); Tear-down-Sequenz Drain → Endpoint → Template → Volume; `--create-all`/`--create <modul>`/`--teardown-all`/`--teardown <modul>`/`--status`; Skalierungsparameter aus KONZEPT §11.1; expliziter User-Agent; saubere Fehlerbehandlung mit Best-Effort-Rollback bei Teilfehlern
- Erster echter Endpoint wird mit `bootstrap-runpod.py --create nsfw` angelegt; Endpoint-ID wandert in `.env`
- `RunPodBackend`-Implementierung des ABC aus Phase 2, mit Request-ID, Retry-Logik, Cold-Start-Toleranz, Base64-Payload
- Job-Status-Endpunkt: `GET /api/jobs/{id}`
- End-to-End-Test mit Testcontainers gegen ein Fake-RunPod-Backend
- Integrationstest gegen echten RunPod-Staging-Endpoint

**Akzeptanzkriterien:**

- Bild hochladen, Job starten, Ergebnis abfragen funktioniert per curl
- Echter RunPod-Call mit echtem Handler funktioniert gegen Staging-Endpoint
- Fake-Backend-Tests decken Erfolg, Retry, Timeout, Terminal-Fehler ab
- Audit-Log füllt sich mit Upload- und Job-Einträgen
- NSFW-Ergebnis ist mit Konfidenz und Bounding Box in `detections` persistiert
- `bootstrap-runpod.py --create nsfw` legt einen Endpoint sauber an; zweiter Lauf ist No-Op (Idempotenz); `--teardown nsfw` räumt vollständig auf (Volume, Template, Endpoint)

**Was explizit nicht zu Phase 3 gehört:**

- Video-Frame-Extraktion (Phase 4)
- Andere Module (Phase 4+)
- Frontend (Phase 7)

---

## Phase 4 — Personen-Erkennung + Re-ID

**Ziel:** Das fachlich anspruchsvollste Modulpaar läuft.

**Umfang:**

- Video-Frame-Extraktion: Keyframe-basiert (Entscheidung aus KONZEPT §11.3 in dieser Phase final)
- Personenerkennung-Handler (DeepFace + ArcFace), gleicher Aufbau wie NSFW-Handler
- Re-ID-Logik: Embeddings in pgvector, Ähnlichkeitssuche, `persons`-Eintrag anlegen oder zuordnen
- `cooccurrences` werden automatisch beim Personen-Fund gepflegt (inkl. `first_seen`/`last_seen`)
- Äußere Merkmale (Haarfarbe, Körperbau, geschätztes Alter, Geschlecht, Kleidung) werden soweit möglich gespeichert
- Endpoints für Personenerkennung und Re-ID via `bootstrap-runpod.py --create persons --create reid` provisioniert

**Akzeptanzkriterien:**

- Video mit mehreren Personen wird analysiert, Personen werden re-identifiziert
- `cooccurrences` enthält korrekte `first_seen`/`last_seen` nach mehreren Jobs
- Integrationstest mit realem Testvideo (ohne echte Mitarbeiterdaten) läuft durch
- Re-ID-Schwellenwert ist konfigurierbar und dokumentiert

**Was explizit nicht zu Phase 4 gehört:**

- Objekterkennung (Phase 5)
- Personen-Merge/Split durch Analysten (Phase 10)

---

## Phase 5 — Objekterkennung + Batch-Pipeline

**Ziel:** Objekte werden Personen zugeordnet. Die Pipeline kann mehrere Module parallel fahren.

**Umfang:**

- Objekterkennung-Handler (YOLOv9), analog zu den vorherigen Handlern
- Endpoint für Objekterkennung via `bootstrap-runpod.py --create objects` provisioniert
- Objekte werden Personen zugeordnet mit Rolle (genutzt / angewendet / vorhanden)
- Batch-Logik: Frames pro Job modulweise gebündelt gegen Serverless-Endpoints (Cost-Optimierung)
- Erweiterte Pipeline: mehrere Module pro Job parallel, wo die Modulunabhängigkeit es erlaubt
- `person_objects` und `object_attributes` werden korrekt befüllt

**Akzeptanzkriterien:**

- Objekte werden Personen korrekt mit Rolle zugeordnet
- Batching reduziert die Anzahl Serverless-Requests messbar gegenüber Single-Request-Strategie
- Integrationstest zeigt parallele Modulausführung
- Kostenmessung pro Job ist nachvollziehbar (Grundlage für Phase 9)

---

## Phase 6 — Optionale Module + Semantische Fusion

**Ziel:** Die narrativen und semantischen Schichten, die Ergebnisse lesbar machen.

**Umfang:**

- Kontextanalyse-Backend: Google AI Studio als Primär-Implementierung, xAI als Alternativ-Backend
- Bildbeschreibung analog
- Rate-Limiting und Quota-Management worker-seitig
- Semantische-Fusion-Modul: aggregiert alle Einzelbefunde pro Person zur Textzusammenfassung nach KONZEPT §6.2
- Job-Konfiguration: Toggle pro optionalem Modul, systemweite Defaults in Einstellungen
- Sicherheitsschicht: automatisierte Prüfung, dass keine Gesichts- oder NSFW-Daten an externe APIs gehen

**Akzeptanzkriterien:**

- Job läuft mit und ohne optionale Module durch
- Semantische Zusammenfassung pro Person wird erzeugt und ist als KI-generiert markiert
- Rate-Limit-Test gegen Fake-External-API zeigt korrektes Backoff-Verhalten
- Automatisierter Test verifiziert, dass Gesichtsdaten nie an externe Backends gesendet werden

---

## Phase 7 — Frontend-Grundgerüst + Projekt-/Medien-/Jobverwaltung

**Ziel:** Die ersten drei UI-Seiten aus KONZEPT §7.2 sind nutzbar. Alles, was bisher per curl lief, hat eine Oberfläche.

**Umfang:**

- React + Vite + TypeScript strict, React Query für Serverstate, Zustand für UI-State
- API-Client aus OpenAPI-Schema generiert
- Authentifizierung (Login, JWT-Handling, Logout, Rollen-Gating)
- Seitennavigation (YouTube-Studio-Stil, KONZEPT §7.1)
- Seiten: Dashboard (Minimalfassung), Projekte, Medienbibliothek, Analysejobs
- Thumbnail-Generierung für Frame-Vorschauen (Lazy Loading)
- Job-Konfigurations-UI mit Modul-Toggles
- Dark-Mode-Entscheidung getroffen und umgesetzt

**Akzeptanzkriterien:**

- Nutzer kann sich einloggen, Projekt anlegen, Medien hochladen, Job starten, Job-Status sehen
- E2E-Test mit Playwright deckt diesen Ablauf ab
- Rollen-Gating funktioniert: Analyst sieht keine Admin-Funktionen

---

## Phase 8 — Personen-Ansicht + Reporting (MVP-Ende)

**Ziel:** Das Kernversprechen der Spec ist eingelöst. Analyst sieht alle erkannten Personen mit Zusammenfassung, kann Berichte erzeugen.

**Umfang:**

- Personen-Seite mit Detailansicht nach KONZEPT §6.1
- Semantische Zusammenfassung angezeigt, als KI-generiert markiert, mit Backend-Hinweis
- Ko-Vorkommen als einfache Liste (nicht als Graph — das ist Post-MVP)
- Berichte-Seite: JSON- und PDF-Export
- Audit-Log-Ansicht für Admins
- Einstellungsseite: Backend-Konfiguration, Standardmodule, Nutzerverwaltung

**Akzeptanzkriterien:**

- Analyst kann eine Person öffnen, alle Fundstellen mit Frame-Vorschau sehen, Zusammenfassung lesen, Bericht generieren
- Exportierter PDF-Bericht ist sinnvoll lesbar und enthält die zentralen Daten
- E2E-Test über gesamten Flow: Upload → Job → Personen-Ansicht → Bericht
- Admin kann Audit-Log filtern und einsehen

**MVP-Abschluss:** Tag `v0.8.0` mit GitHub-Release-Notes, die den Funktionsumfang klar benennen.

---

## Phase 9 — Härtung: Monitoring, Backup, Sicherheit

**Ziel:** Das System ist betriebsreif. Post-MVP, aber notwendig vor `v1.0.0`.

**Umfang:**

- Monitoring: Prometheus + Grafana oder Uptime Kuma (Entscheidung in der Phase)
- Backup-Strategie: Postgres-Dumps, Medien-Backup, Restore-Test dokumentiert
- Nginx-Härtung: Rate Limiting, Request-Size-Limits, Security Headers, Timeouts
- Fehlerbenachrichtigung: E-Mail oder Webhook bei Job-Fehlern, Backend-Ausfall
- Log-Aggregation: Loki oder Datei-Rotation
- RunPod-Kostenerfassung pro Job in `jobs`-Tabelle (Feld `cost_usd`)
- Storage-Management: Quota, Cleanup verwaister Frames, Speicher-Alarm

**Akzeptanzkriterien:**

- Simulierter Komplettausfall eines Services wird erkannt und alarmiert
- Restore aus Backup auf frische Instanz funktioniert (Test dokumentiert)
- Security-Header-Check zeigt keine gravierenden Lücken
- Kostenübersicht pro Job ist in Admin-UI sichtbar

---

## Phase 10 — Personen-Merge/Split

**Ziel:** Analyst kann Re-ID-Fehler korrigieren. Datenintegrität bleibt gewahrt.

**Umfang:**

- Personen-Merge: Analyst führt zwei Personen-IDs zusammen, Konsequenzen für `detections`, `person_detections`, `person_objects`, `cooccurrences` sind definiert und dokumentiert
- Personen-Split: Analyst trennt fälschlich zusammengefasste Detektionen, neue Person entsteht
- Beide Operationen vollständig im Audit-Log
- UI für Merge/Split in der Personen-Ansicht
- Idempotenz: Merge zweier bereits zusammengeführter Personen ist No-Op, kein Datenverlust

**Akzeptanzkriterien:**

- Merge und Split sind idempotent und vollständig im Audit-Log
- Testszenario: zwei Personen mergen, `cooccurrences` konsistent neu berechnet
- Testszenario: Person splitten, Embedding-Zuordnungen nachvollziehbar
- UI-Hinweis vor destruktiver Aktion mit Bestätigungsdialog

---

## Phase 11 — Admin-Schemaerweiterung

**Ziel:** Admin kann ohne Entwicklerhilfe neue Objekt-Attribute anlegen. Der `schema_suggestions`-Workflow läuft.

**Umfang:**

- Admin-UI für `schema_suggestions`: Genehmigen, Ablehnen, neue `attribute_definitions` anlegen
- KI-generierte Vorschläge aus der Pipeline landen in `schema_suggestions`
- Nach Genehmigung werden neue Attributwerte in `object_attributes` als Key-Value-Paare gespeichert
- Dynamische Darstellung neuer Attribute in Personen- und Objekt-Detailansichten (ohne Frontend-Redeploy)

**Akzeptanzkriterien:**

- Admin kann ohne Entwickler-Hilfe ein neues Objekt-Attribut anlegen und in der UI sehen
- Bereits existierende Daten bleiben unberührt bei Schemaerweiterung
- Ablehnung eines Vorschlags markiert diesen in `schema_suggestions` als abgelehnt, erneute Vorschläge werden nicht doppelt angelegt

**Nach Phase 11:** Tag `v1.0.0` — produktionsreifer Stand, vollständige Funktionsabdeckung der Spezifikation.

---

## Post-MVP-Sperre

Folgende Features werden auch dann nicht implementiert, wenn sie technisch in Reichweite wirken. Vor einer Umsetzung braucht es eine explizite Erweiterung dieses Fahrplans:

- **Graph-Visualisierung der Ko-Vorkommen** (über die einfache Liste hinaus)
- **Face-Search über eigenes Referenzbild** (Analyst lädt ein Foto hoch, System sucht in Datenbank)
- **Mehrmandantenfähigkeit** (mehrere Organisationen auf einer AIMA-Instanz)
- **Programmatische Endpoint-Verwaltung durch AIMA zur Laufzeit** — das einmalige Bootstrap-Skript (`scripts/bootstrap-runpod.py`) ist davon ausgenommen, aber: es ist ein Admin-Tool für die Kommandozeile, wird **nie vom AIMA-Backend zur Laufzeit aufgerufen** und hat keinen Trigger über die UI oder API.
- **Alternative Backends jenseits RunPod / Google AI / xAI**
- **Auto-Trigger-Features** (Watch-Folder, Scheduled Jobs, Auto-Reanalyse, kaskadierende Auto-Starts) — kollidieren mit der Grundregel „Benutzersteuerung ist absolut"
- **Laufzeit-Modellauswahl durch Endnutzer** (z. B. Modelle aus Civitai/HuggingFace zur Job-Zeit nachladen) — Modell-Versionen sind ans Docker-Image gebunden, das ist Audit-Voraussetzung

---

## Phasen-Abschluss-Ritual

Jede Phase endet mit:

1. **Akzeptanzkriterien grün** (aus diesem Dokument, funktional und nicht-funktional lokal verifiziert)
2. **Doku aktualisiert:**
   - `CHANGELOG.md` unter `[Unreleased]`
   - Status-Spalte in der Meilenstein-Tabelle oben
   - README-Statusbadges
   - KONZEPT bei konzeptionellen Änderungen
3. **PR mit grüner CI** → Squash-Merge auf `main` (ein Commit pro Phase)
4. **Tag `v0.N.0`** (annotiert, mit Release-Notes) + GitHub-Release
5. **`CLAUDE.md` aktualisieren**, falls sich Konventionen oder Stand geändert haben
