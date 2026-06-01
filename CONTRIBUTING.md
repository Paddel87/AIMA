# CONTRIBUTING.md

> Workflow-Regeln für die Arbeit an AIMA. Gilt für jede Session — egal ob Mensch oder Claude Code.
> CLAUDE.md ist der Nord-Stern, FAHRPLAN.md hält den Status, KONZEPT.md die Architektur. Diese Datei hier regelt das **Wie**: Setup, Branches, Commits, CI, PRs, Phasen-Abschluss.

---

## 1. Einmaliges Setup

Erstmalige Einrichtung des Repos auf einem frischen System:

```bash
# Repo klonen
git clone git@github.com:Paddel87/AIMA.git
cd aima

# Python-Umgebung (uv)
uv sync

# Frontend-Abhängigkeiten
cd frontend && npm install && cd ..

# Pre-Commit-Hooks installieren (Pflicht)
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg

# .env aus Vorlage anlegen, lokale Werte eintragen
cp .env.example .env

# Smoketest: alles grün?
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

**Toolchain-Voraussetzungen** (lokale Versionen):

- `python` ≥ 3.12
- `uv` (aktuelle Version)
- `node` ≥ 20 + `npm` ≥ 10
- `docker` + `docker compose` v2
- `gh` (GitHub CLI, für Tag- und Release-Workflow)

Fehlende Tools vor Arbeitsbeginn installieren, nicht nachträglich. Claude Code prüft Toolchain automatisch, bevor Scaffolding-Tasks beginnen (siehe CLAUDE.md §4).

## 2. Täglicher Workflow

Jede Arbeitssession beginnt mit dem Stand-Check:

```bash
git status
git log --oneline -5
git pull --rebase
```

Dann in einen Branch wechseln oder einen neuen anlegen:

```bash
git checkout -b feature/<kurzer-slug>
```

**Nie direkt auf `main` arbeiten.** Pushes auf `main` sind durch Branch-Schutz blockiert.

## 3. Branches

| Präfix       | Zweck                                                        |
| ------------ | ------------------------------------------------------------ |
| `feature/`   | Neue Funktion (in der aktuellen Phase vorgesehen)            |
| `fix/`       | Bugfix                                                       |
| `docs/`      | Nur Dokumentation                                            |
| `chore/`     | Infrastruktur, Abhängigkeiten, Aufräumen                     |
| `refactor/`  | Umbau ohne Verhaltensänderung                                |
| `test/`      | Nur Tests ergänzt oder geändert                              |

Branch-Namen **klein, kebab-case, ohne Umlaute**: `feature/runpod-nsfw-handler`, `fix/jwt-expiry`.

Ein Branch = ein Thema. Große Phasen-Branches sind erlaubt (z. B. `feature/phase-3-nsfw-pipeline`), enthalten dann aber die komplette vertikale Scheibe in einem Rutsch.

## 4. Commits

**Conventional Commits sind Pflicht.** Durchgesetzt lokal via `commitizen` pre-commit-Hook und in CI.

**Format:**

```
<type>(<optional-scope>): <kurze Beschreibung im Imperativ>

<optional: längerer Body>

<optional: BREAKING CHANGE: <Beschreibung>>
<optional: Refs: #<issue-nummer>>
```

**Erlaubte Typen:**

| Typ        | Wofür                                                        |
| ---------- | ------------------------------------------------------------ |
| `feat`     | Neue Funktion                                                |
| `fix`      | Bugfix                                                       |
| `docs`     | Nur Dokumentation                                            |
| `chore`    | Routine-Aufgaben, Abhängigkeits-Updates, Config              |
| `refactor` | Umbau ohne Verhaltensänderung                                |
| `test`     | Tests                                                        |
| `build`    | Build-System, Docker, Dependencies (funktional)              |
| `ci`       | CI-Konfiguration                                             |
| `perf`     | Performance-Änderung                                         |
| `revert`   | Revert eines früheren Commits                                |
| `style`    | Formatierung, Whitespace (keine inhaltlichen Änderungen)     |

**Beispiele:**

```
feat(backends): add RunPodBackend with retry-aware error handling

feat(db): add cooccurrences first_seen/last_seen columns

fix(worker): handle RunPod cold-start timeout without aborting job

docs(konzept): document Serverless-only decision in §3.2

chore(deps): bump fastapi to 0.115.x
```

**Bei Unsicherheit** `uv run cz commit` verwenden — startet einen Assistenten, der den Commit korrekt zusammenbaut.

**Breaking Changes** müssen markiert sein — entweder mit `!` nach dem Typ (`feat(shared)!: ...`) oder mit `BREAKING CHANGE:` im Body. Änderungen an den **Vertragsdateien** (siehe §6) sind standardmäßig breaking.

## 5. Pre-Commit-Hooks

Lokal feuern bei jedem Commit automatisch:

- `ruff` (Lint)
- `ruff format` (Format-Check)
- `mypy --strict` (Typecheck)
- `commitizen` (Commit-Message-Check)

**Regel:** Hooks nie mit `--no-verify` umgehen. Wenn ein Hook fehlschlägt, wird die Ursache behoben — nicht der Hook umgangen.

Falls ein Hook nach Dependency-Update hängenbleibt:

```bash
uv run pre-commit clean
uv run pre-commit install
uv run pre-commit run --all-files
```

## 6. Vertragsdateien — besonderer Schutz

Folgende Dateien sind **Verträge**. Änderungen daran brauchen explizite User-Freigabe im PR-Body und einen `BREAKING CHANGE`-Vermerk im Commit:

- `backend/shared/types.py`
- `backend/shared/errors.py`
- `backend/backends/base.py`
- `backend/db/alembic/versions/0001_*.py` (Baseline-Migration)

PRs, die diese Dateien anfassen, **müssen im Titel** den Präfix `[contract]` tragen, z. B.:

```
[contract] feat(shared)!: extend AnalysisRequest with request_id
```

Das macht sichtbar, dass der PR-Review besonders gründlich sein muss.

## 7. Pull Requests

**Öffnen:**

```bash
git push -u origin <branch-name>
gh pr create --fill
```

**Anforderungen an den PR:**

- **Titel** nach Conventional-Commit-Format (gleiche Regeln wie Commits; wird beim Squash-Merge zur `main`-Commit-Message)
- **Body** enthält:
  - Ziel des PRs (ein, zwei Sätze)
  - Betroffene FAHRPLAN-Phase (z. B. „Phase 3")
  - Akzeptanzkriterien-Abgleich, falls Phasen-Abschluss (Checkliste)
  - Bei Vertragsänderungen: Begründung + User-Freigabe als Zitat
- **CI grün** — siehe §8
- **Mindestens ein Review** (bei Solo-Projekt entfällt; bei Zuarbeit durch Claude Code: User-Freigabe im PR-Kommentar)

**Merge-Strategien:**

- **Squash-Merge für Phasen-Abschluss-PRs** → ein Commit pro Phase auf `main`
- **Normaler Merge** für Einzel-PRs innerhalb einer Phase (Merge-Commit)
- **Kein Rebase-Merge** (macht die Historie unübersichtlich)

## 8. CI

GitHub Actions führt bei jedem PR und Push auf `main` diese Jobs aus:

| Job            | Befehl                                          |
| -------------- | ----------------------------------------------- |
| `lint`         | `uv run ruff check .`                           |
| `format-check` | `uv run ruff format --check .`                  |
| `typecheck`    | `uv run mypy .`                                 |
| `test`         | `uv run pytest`                                 |
| `commit-check` | `uv run cz check --rev-range origin/main..HEAD` |
| `docker-build` | `docker compose build backend worker frontend`  |

**Alle Jobs müssen grün sein**, sonst ist der Merge blockiert. Rot bedeutet: Ursache beheben, neu pushen. Nicht „retry-bis-grün" spielen.

Failing Tests werden **nicht** gerade skippen oder xfail markieren — nur wenn der Skip-Grund fachlich begründbar ist (z. B. RunPod-Integrationstest ohne Credentials in CI).

## 9. Phasen-Abschluss-Ritual

Eine Phase aus dem FAHRPLAN gilt als abgeschlossen, wenn **alle fünf Schritte** erfolgt sind:

1. **Akzeptanzkriterien grün.** Jedes Kriterium aus dem entsprechenden FAHRPLAN-Abschnitt ist lokal nachweislich erfüllt — funktional **und** nicht-funktional.
2. **Dokumentation aktualisiert:**
   - `CHANGELOG.md` — Eintrag unter `[Unreleased]` nach Keep-a-Changelog-Format
   - `FAHRPLAN.md` — Status-Spalte der Phase auf „✅ erledigt" + Tag eintragen
   - `README.md` — Status-Badges aktualisieren (falls vorhanden)
   - `KONZEPT.md` — nur bei konzeptionellen Änderungen; §11-Eintrag als erledigt markieren, falls betroffen
   - `CLAUDE.md` — nur bei geänderten Konventionen oder geänderter „aktueller Phase"-Logik
3. **PR mit grüner CI → Squash-Merge auf `main`.** Ein Commit pro Phase. Commit-Message nach Format:
   ```
   feat(phase-N): <kurze Zusammenfassung der Phase>
   ```
4. **Annotierter Tag + GitHub Release:**
   ```bash
   git checkout main
   git pull
   git tag -a v0.N.0 -m "Phase N: <Titel>"
   git push origin v0.N.0
   gh release create v0.N.0 --title "Phase N — <Titel>" --notes-file .github/release-notes/v0.N.0.md
   ```
5. **Letzter Check:** `CLAUDE.md` aktualisieren, falls sich der „aktuelle Phase"-Hinweis oder eine Konvention geändert hat.

Zwischen Phasen-Abschlüssen darf `main` **keine offenen Nebenstränge** haben — alle Feature-Branches der Phase sind gemerged oder verworfen.

## 10. Was nicht committed wird

- **`.env` und jegliche Secrets** — weder Real- noch Staging-Werte. Nur `.env.example` ist versioniert.
- **API-Keys** (RunPod, Google AI, xAI) — liegen ausschließlich in `.env` und ggf. GitHub-Secrets für CI.
- **Echte personenbezogene Daten** — keine realen Gesichter, keine realen Mitarbeiterdaten, keine echten NSFW-Uploads. Testdaten sind synthetisch oder aus lizenzfreien Quellen.
- **Lokale Caches und Artefakte** — `storage/uploads/`, `storage/frames/`, `.venv/`, `node_modules/`, `dist/`, `__pycache__/`.
- **IDE-Ordner** außer gemeinsam vereinbarten (`.vscode/settings.json` mit Projekt-Einstellungen ist okay; persönliche `.idea/`-Einstellungen nicht).

`.gitignore` deckt diese Fälle ab — nichts Erwähntes soll trotzdem per `git add -f` erzwungen werden.

## 11. RunPod-Handler

Die RunPod-Handler sind **nicht Teil dieses Repos**. Sie liegen entweder unter `runpod-handlers/` als Git-Submodul oder in separaten Repos (Entscheidung fällt in FAHRPLAN-Phase 3).

Folgende Regeln gelten für die Schnittstelle:

- Images werden manuell gebaut und zur Registry gepusht — nie durch AIMAs CI.
- Endpoints werden manuell in der RunPod-Console angelegt. IDs landen in `.env`.
- AIMA ruft Endpoints nur auf (`/run`, `/runsync`), verwaltet sie aber nicht.

Änderungen am Handler-Vertrag (Input-/Output-Schema eines Moduls) erfordern synchrone Änderungen an `backend/shared/types.py` und damit User-Freigabe nach §6.

## 12. Bei Fragen

- **Konventionen unklar?** CLAUDE.md §3 und diese Datei.
- **Architekturfrage?** KONZEPT.md — ist die Frage dort beantwortet, gilt die Antwort; ist sie offen, steht sie in KONZEPT.md §11.
- **Was ist als Nächstes dran?** FAHRPLAN.md, nächste offene Phase.
- **Entscheidung fällig, die über eine Phase hinausgeht?** User fragen — nicht selbst entscheiden. Besonders bei Vertragsdateien (§6), Post-MVP-Features (CLAUDE.md §3) und DSGVO-relevanten Punkten.
