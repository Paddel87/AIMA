# KONZEPT.md

> Systemspezifikation und Konzeptdokument für AIMA (AI Media Analysis System).
> **Architektur-Grundentscheidungen in diesem Dokument sind verbindlich.** Änderungen nur mit expliziter User-Freigabe.
>
> Version 0.2 — Konzeptphase. Stand: April 2026.
>
> Der FAHRPLAN ([FAHRPLAN.md](FAHRPLAN.md)) legt fest, in welcher Reihenfolge die hier beschriebenen Komponenten umgesetzt werden. KONZEPT beantwortet das _Was_, FAHRPLAN das _Wann_.

---

## 1. Projektziel

AIMA ist ein modulares, KI-gestütztes Medienanalyse- und Auswertungssystem zur automatisierten Erkennung, Wiedererkennung, Kontextbewertung und semantischen Zusammenführung von Bild- und Videoinhalten. Das System unterstützt Nutzer dabei, große Mengen visueller Medien effizient auszuwerten, Zusammenhänge zu erkennen und Analyseergebnisse nachvollziehbar aufzubereiten.

Primärer Anwendungsfall ist die Identifizierung und Re-Identifizierung von Personen, die im Unternehmens-Intranet sexuell explizite Materialien von sich hochladen und damit für andere Mitarbeiterinnen und Mitarbeiter eine unangenehme Situation hervorrufen. AIMA unterstützt dabei die zuständigen Stellen mit technischen Mitteln bei der Aufklärung solcher Vorkommnisse.

## 2. Ausgangssituation

Die manuelle Sichtung und Bewertung größerer Medienmengen ist zeitintensiv, fehleranfällig und bei wiederkehrenden Mustern nur eingeschränkt skalierbar. Einzelne KI-Modelle können zwar Teilaufgaben lösen, liefern jedoch isolierte Einzelergebnisse.

Benötigt wird ein Gesamtsystem, das diese Einzelergebnisse entgegennimmt, vereinheitlicht, logisch zusammenführt, zeitlich und inhaltlich einordnet und in verwertbarer Form bereitstellt.

## 3. Systemarchitektur

### 3.1 Überblick

AIMA ist als mehrschichtiges System konzipiert, das auf einem VPS (Virtual Private Server) betrieben wird. Alle Komponenten laufen als Docker-Container und werden über Docker Compose orchestriert.

| Schicht       | Komponente                | Technologie       |
| ------------- | ------------------------- | ----------------- |
| Präsentation  | Weboberfläche             | React             |
| API           | REST-Backend              | Python / FastAPI  |
| Verarbeitung  | Job-Worker                | Celery            |
| Warteschlange | Message Broker            | Redis             |
| Persistenz    | Datenbank                 | PostgreSQL        |
| Deployment    | Container-Orchestrierung  | Docker Compose    |
| Webserver     | Reverse Proxy             | Nginx             |

### 3.2 Backend-Schicht (Analyse-Backends)

AIMA unterstützt drei austauschbare Analyse-Backends, die über ein abstraktes Interface angebunden sind:

| Backend          | Einsatz                                                         | Datenschutz                             |
| ---------------- | --------------------------------------------------------------- | --------------------------------------- |
| RunPod           | Gesichtserkennung, Re-ID, Objekte, NSFW — alle sensiblen Module | Kontrollierte Umgebung, DSGVO-konform   |
| Google AI Studio | Kontextanalyse, Bildbeschreibung (optional)                     | Externe Server — nur unkritische Daten  |
| xAI / Grok       | Alternativ-Backend für Kontext und Beschreibung                 | Externe Server — nur unkritische Daten  |

Sensible Inhalte (Gesichter, explizite Bilder) werden ausschließlich über RunPod verarbeitet. Externe APIs erhalten niemals Rohmediendaten mit Personenbezug.

RunPod wird **ausschließlich im Serverless-Modus** betrieben. Persistente Pods sind ausdrücklich nicht vorgesehen. Details siehe §8.1 und §11.1.

## 4. Analysepipeline

### 4.1 Ablauf

Jeder Analysejob durchläuft eine fünfstufige Pipeline:

- **Medienimport:** Bilddateien und Videodateien werden importiert und im System registriert.
- **Vorverarbeitung:** Videos werden in Frames zerlegt, Metadaten erfasst, Bilddaten normalisiert.
- **Analysemodule:** Mehrere Module laufen parallel und liefern Einzelbefunde.
- **Semantische Datenfusion:** Einzelbefunde werden zusammengeführt und ein Gesamtbild erzeugt.
- **Reporting:** Strukturierte Berichte und narrative Zusammenfassungen werden erzeugt.

Die Stufen 1, 2, 4 und 5 laufen **ausschließlich auf dem VPS** (CPU). Nur Stufe 3 — die eigentliche Modell-Inferenz — wird an RunPod ausgelagert und verursacht dort GPU-Sekunden. Die Pipeline-Orchestrierung ist so gebaut, dass ein RunPod-Endpoint erst aufgerufen wird, wenn der vollständige Payload (gebündelte Frames, fertig normalisiert) auf dem VPS bereitsteht. So fällt GPU-Zeit nur für die reine Inferenz an, nicht für Setup, Wartezeiten oder Pipeline-Logik.

### 4.2 Analysemodule

| Modul                | Funktion                                              | Backend                       | Optional |
| -------------------- | ----------------------------------------------------- | ----------------------------- | -------- |
| Personenerkennung    | Personen in Bildern und Videos erkennen               | RunPod / DeepFace + ArcFace   | Nein     |
| Re-Identifizierung   | Dieselbe Person über mehrere Frames hinweg erkennen   | RunPod                        | Nein     |
| Objekterkennung      | Gegenstände und deren Rolle erfassen                  | RunPod / YOLOv9               | Nein     |
| NSFW-Klassifikation  | Explizite Inhalte erkennen und kategorisieren         | RunPod / NudeNet              | Nein     |
| Kontextanalyse       | Szenen und Situationen einordnen                      | Google AI / xAI               | Ja       |
| Bildbeschreibung     | Narrative Beschreibung der Bildinhalte                | Google AI / xAI               | Ja       |
| Semantische Fusion   | Alle Befunde logisch zusammenführen                   | Intern                        | Nein     |

Die optionalen Module (Kontext, Bildbeschreibung) können pro Job aktiviert oder deaktiviert werden. In den Einstellungen kann eine systemweite Standardkonfiguration hinterlegt werden.

### 4.3 Auslösung von Analysen

**AIMA startet niemals selbstständig ML-Aufgaben.** Jede Analyse — also jeder RunPod-Call — wird ausschließlich durch eine **explizite Benutzeraktion** ausgelöst (Klick auf „Analyse starten" in der UI oder ein expliziter API-Aufruf durch einen authentifizierten Nutzer). Es gibt keine automatischen Trigger.

Insbesondere existieren **nicht** und werden auch nicht ergänzt:

- Watch-Folder, die hochgeladene Medien automatisch analysieren
- Geplante Jobs (Cron, Scheduled Tasks), die ohne User-Aktion Analysen anstoßen
- Auto-Reanalyse nach Modell-Update, Konfigurationsänderung oder Systemneustart
- Kaskadierende Auto-Trigger („nach Job A startet automatisch Job B")
- Automatische Hintergrund-Indexierung ungewarteter Medien

Erlaubt und Teil der normalen Pipeline-Ausführung sind dagegen:

- Wiederholungsversuche (Retries) innerhalb eines bereits vom Nutzer gestarteten Jobs bei transienten Fehlern
- Vor- und Nachbereitungsschritte (Frame-Extraktion, Fusion, Reporting) als Teil eines vom Nutzer gestarteten Jobs
- Reine Status- und Health-Abfragen gegen RunPod (`/v2/{id}/health`), die keine Worker starten

Diese Festlegung gilt für alle Implementierungsphasen und ist nicht durch Konfiguration umgehbar.

## 5. Datenbankschema

### 5.1 Kernstruktur

Die Datenbank ist in PostgreSQL implementiert. Mediendateien werden nicht direkt gespeichert, sondern nur als Pfadverweise. Alle Befunde sind einer Quelldatei und einem Job zugeordnet.

| Tabelle                 | Inhalt                                                                      |
| ----------------------- | --------------------------------------------------------------------------- |
| `users`                 | Nutzerkonten, Rollen (Admin / Analyst), Authentifizierung                   |
| `projects`              | Projekte / Fälle, Zuordnung zu Nutzern                                      |
| `media_files`           | Importierte Dateien, Pfade, Metadaten (EXIF, Dateityp)                      |
| `jobs`                  | Analysejobs, Status, Backend, Modulkonfiguration, Zeitstempel               |
| `job_media`             | Zuordnung: welche Medien gehören zu welchem Job                             |
| `persons`               | Erkannte Personen, interne ID, visuelle Merkmale, Status, Notizen           |
| `detections`            | Einzelbefunde je Frame / Bild: Typ, Konfidenz, Bounding Box                 |
| `person_detections`     | Zuordnung von Personen zu Einzelbefunden mit Konfidenzwert                  |
| `person_objects`        | Gegenstände je Person: Klasse, Rolle (genutzt / angewendet / vorhanden)     |
| `object_attributes`     | Dynamische Attribute zu Gegenständen (Key-Value)                            |
| `attribute_definitions` | Admin-verwaltete Liste erlaubter Attribute und Datentypen                   |
| `cooccurrences`         | Ko-Vorkommen zweier Personen mit Häufigkeitszähler                          |
| `schema_suggestions`    | KI-generierte Vorschläge zur Schemaerweiterung                              |
| `reports`               | Erzeugte Berichte: JSON, Text, Dateipfad                                    |
| `audit_log`             | Vollständige Protokollierung aller Aktionen nach Nutzer und Zeitpunkt       |

### 5.2 Dynamische Erweiterbarkeit

Das Schema ist ohne Entwicklerbeteiligung durch einen Admin erweiterbar. Das System schreibt Erweiterungsvorschläge in die Tabelle `schema_suggestions`. Nach Admin-Genehmigung werden neue Einträge automatisch in `attribute_definitions` angelegt. Neue Attributwerte werden in `object_attributes` als Key-Value-Paare gespeichert — ohne Migrationen oder Schemaanpassungen.

## 6. Personenanalyse

### 6.1 Erfasste Daten je Person

Für jede erkannte Person werden folgende Informationen automatisch erfasst und semantisch zusammengeführt:

**Identität und Kennzahlen**

- Interne Personen-ID (systemgeneriert)
- Anzahl Funde gesamt
- Durchschnittlicher Konfidenzwert der Erkennung
- Erkennungsmodell (ArcFace / DeepFace)
- Datum des ersten Funds

**Äußere Merkmale (soweit erkennbar)**

- Haarfarbe, Körperbau, geschätztes Geschlecht, geschätztes Alter
- Typische Kleidung

**Fundstellen**

- Projekte, Dateien, Zeitstempel bei Videos
- Frame-Vorschau je Fundstelle
- NSFW-Kennzeichnung je Fund

**Gegenstände**

- Erkannte Objekte je Fundstelle mit Rolle: genutzt / angewendet / vorhanden
- Konfidenz und optionale Analyst-Bestätigung

**Soziale Verknüpfungen**

- Ko-Vorkommen mit anderen Personen über mehrere Medien hinweg

### 6.2 Semantische Zusammenfassung

Das System erzeugt pro Person eine KI-generierte Textzusammenfassung, die alle Einzelbefunde integriert. Beispiel: „Person 002 taucht ausschließlich in Projekt A auf, verteilt über 6 Medien im Zeitraum 04.–09.03.2026. In 5 von 6 Funden wurde expliziter Inhalt erkannt. Die Person erscheint in allen Funden allein. Typische Objekte sind Mobiltelefon und Spiegel."

Die Zusammenfassung ist explizit als KI-generiert gekennzeichnet und zeigt, welche Backends sie erzeugt haben. Sie ersetzt nicht die menschliche Endbewertung durch den Analysten.

## 7. Benutzeroberfläche

### 7.1 Designprinzip

Die UI ist vollständig browserbasiert und an das Konzept von YouTube Studio angelehnt: feste Seitennavigation, klarer Hauptbereich, keine versteckten Menüs. Alle Funktionen sind über die Weboberfläche zugänglich — keine Kommandozeile, keine direkten Datenbankzugriffe.

### 7.2 Seitenstruktur

| Seite            | Funktion                                                                    |
| ---------------- | --------------------------------------------------------------------------- |
| Dashboard        | Kennzahlen auf einen Blick, laufende Jobs, letzte Aktivität                 |
| Projekte         | Projekte anlegen, öffnen, verwalten                                         |
| Medienbibliothek | Medien importieren, durchsuchen, Vorschau                                   |
| Analysejobs      | Jobs starten mit Modulauswahl, Status verfolgen                             |
| Personen         | Alle erkannten Personen, Detailansicht mit Zusammenfassung                  |
| Berichte         | Erzeugte Berichte abrufen, exportieren (JSON, PDF)                          |
| Einstellungen    | Backends konfigurieren, Standardmodule, Nutzerverwaltung, Attribute         |

### 7.3 Job-Konfiguration

Beim Start eines Analysejobs wählt der Nutzer:

- Medien oder Projekt als Eingabe
- Aktive Analysemodule (Kernmodule immer aktiv, optionale Module per Toggle)
- Backend für optionale Module (Google AI oder xAI)

## 8. Betrieb

### 8.1 Infrastruktur

| Komponente          | Beschreibung                                                                                         |
| ------------------- | ---------------------------------------------------------------------------------------------------- |
| VPS                 | Zentraler Betriebsort aller Dienste                                                                  |
| Docker Compose      | Orchestrierung aller Container (API, Worker, Frontend, DB, Redis, Nginx)                             |
| RunPod (Serverless) | On-Demand GPU-Instanzen für rechenintensive Analysen — ausschließlich Serverless, keine persistenten Pods |
| Speicher            | Lokales Volume auf dem VPS für Mediendateien und Frames                                              |
| HTTPS               | Pflicht — kein unverschlüsselter Zugriff                                                             |

### 8.2 Nutzer und Rollen

| Rolle   | Rechte                                                                                      |
| ------- | ------------------------------------------------------------------------------------------- |
| Admin   | Vollzugriff: Nutzerverwaltung, API-Keys, Schemaerweiterung, alle Funktionen                 |
| Analyst | Projekte anlegen, Medien importieren, Jobs starten, Ergebnisse einsehen und kommentieren    |

Das System ist für 2–3 gleichzeitige Nutzer ausgelegt. Jobs werden über eine Celery-Queue serialisiert, um Kollisionen bei RunPod-Anfragen zu vermeiden.

## 9. Datenschutz und Sicherheit

- Alle Mitarbeiter haben der Verarbeitung ihrer Daten im Rahmen ihrer Anstellung zugestimmt (dokumentiert im Arbeitsvertrag oder einer Betriebsvereinbarung).
- Gesichtsdaten und explizite Inhalte werden ausschließlich über RunPod verarbeitet und verlassen nie eine unkontrollierte Umgebung.
- Alle Aktionen werden im Audit-Log protokolliert (Nutzer, Zeitpunkt, Aktion, betroffene Entität).
- Zugriff nur über HTTPS, Authentifizierung über JWT-Token.
- Keine dauerhaften öffentlichen Ports zur Datenbank.
- Löschkonzept: Medien und Analyseergebnisse sind getrennt löschbar, projektbezogen.
- AIMA trifft keine autonomen Tatsachenfeststellungen — alle Ergebnisse unterliegen menschlicher Plausibilitätskontrolle.
- AIMA startet keine autonomen Analysen — jeder ML-Job wird ausschließlich durch explizite Benutzeraktion ausgelöst (siehe §4.3). Keine Watch-Folder, kein Scheduling, kein Auto-Trigger.

## 10. Projektstruktur

| Verzeichnis              | Inhalt                                                         |
| ------------------------ | -------------------------------------------------------------- |
| `backend/api/`           | FastAPI-Backend: Routers, Services, Auth, Pydantic-Models      |
| `backend/worker/`        | Celery-Worker: Pipeline, Tasks, Analysemodule                  |
| `backend/worker/modules/`| Ein Modul pro Analysefunktion, alle erben von `base.py`        |
| `backend/backends/`      | RunPod, Google AI, xAI — alle implementieren dasselbe Interface|
| `backend/db/`            | SQLAlchemy ORM-Models, Alembic-Migrationen                     |
| `backend/shared/`        | Geteilte Datenklassen (`types.py`), Fehlerhierarchie (`errors.py`) |
| `frontend/`              | React-Weboberfläche                                            |
| `storage/`               | Mediendateien (`uploads/`) und extrahierte Frames (`frames/`)  |
| `docker/`                | Separate Dockerfiles für API, Worker, Frontend                 |
| `docker-compose.yml`     | Orchestrierung aller Dienste                                   |
| `.env.example`           | Konfigurationsvorlage (API-Keys, DB-URL, etc.)                 |
| `runpod-handlers/`       | RunPod-Handler als separate Docker-Projekte (ggf. eigenes Repo, Entscheidung in Phase 3) |

## 11. Offene Punkte und getroffene Festlegungen

Dieser Abschnitt bündelt die Design-Entscheidungen, die über die reine Architekturbeschreibung hinausgehen: was bereits entschieden ist, was vor Implementierungsbeginn entschieden werden muss, was in der Pipeline-Semantik noch auszuformulieren ist, und was für Frontend, Betrieb und Kosten noch festzulegen ist. Die Abarbeitung erfolgt phasenweise über den FAHRPLAN.

### 11.1 Getroffene Festlegungen

Folgende Entscheidungen wurden im Konzeptprozess getroffen und bilden die Grundlage für die Implementierung. Sie werden bei der nächsten Überarbeitung des Dokuments in die jeweils inhaltlich passenden Abschnitte (insbesondere §3.2 und §8.1) übernommen.

| Thema                          | Festlegung                                                                                                                      |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| RunPod-Betriebsmodus           | Ausschließlich Serverless — keine persistenten Pods                                                                             |
| Handler-Packaging              | Ein Docker-Image pro Analysemodul (Personen, Re-ID, Objekte, NSFW), basierend auf `runpod/base`, Plattform `linux/amd64`, Handler-Einstieg über das `runpod`-Python-SDK (Serverless-Worker-Teil, `runpod.serverless.start({"handler": fn})`) |
| Endpoint-Provisionierung       | Statisch — Endpoints werden einmalig in der RunPod-Console angelegt. Ihre IDs werden in der `.env`-Konfiguration des AIMA-Systems hinterlegt |
| Endpoint-Nutzung zur Laufzeit  | AIMA ruft ausschließlich `POST /v2/{ENDPOINT_ID}/run` auf und pollt anschließend `GET /v2/{ENDPOINT_ID}/status/{job_id}`. `/runsync` wird nicht verwendet, da der Endpoint nach ca. 60 s Wartezeit intern auf asynchrones Verhalten umschaltet und damit kein verlässliches synchrones Programmiermodell bietet. Keine dynamische Endpoint-Verwaltung durch AIMA. |
| RunPod-Client-Implementierung  | Eigener schlanker, `httpx`-basierter Wrapper in `backend/backends/runpod.py`. Das `runpod`-SDK wird auf der Client-Seite **nicht** verwendet, damit Retry-Strategie, Idempotenz (Request-ID), Cold-Start-Toleranz, Timeouts pro Modul und strukturiertes JSON-Logging explizit kontrolliert werden können. Status-Strings (`IN_QUEUE`, `IN_PROGRESS`, `COMPLETED`, `FAILED`) werden 1:1 von der RunPod-API übernommen. |
| Skalierungsparameter           | `workersMin: 0`, `workersMax: 1` (seriell passend zur Celery-Queue), `idleTimeout: 5s`, `flashboot: true`, `scalerType: "QUEUE_DELAY"`, `scalerValue: 4`, `allowedCudaVersions` modulspezifisch (z. B. `["12.9", "12.8"]`), `executionTimeoutMs` modulspezifisch zu bestimmen |
| Batch-Verhalten                | Frames werden pro Job modulweise gebündelt, um Cold Starts und Payload-Overhead zu minimieren **und sicherzustellen, dass GPU-Zeit nur für die eigentliche Inferenz anfällt, nicht für Pipeline-Setup oder Wartezeiten**. Konkret: Erst alle Frames eines Jobs durch Modul A, dann alle durch Modul B — nicht Frame-für-Frame durch alle Module. |
| HTTP-Client-Anforderungen      | Der `httpx`-Wrapper setzt einen expliziten `User-Agent`-Header (z. B. `aima-backend/<version>`). Cloudflare vor RunPod blockiert Pythons Default-User-Agent — ohne expliziten UA scheitern Aufrufe stillschweigend. |
| Embedding-Speicherung          | Embeddings werden zentral in der AIMA-Datenbank persistiert (Speichertechnologie noch offen — siehe §11.2) und nicht im RunPod-Worker gehalten |

### 11.2 Blocker — vor Implementierungsstart zu klären

Ohne diese Entscheidungen kann nicht sauber mit dem Coding begonnen werden.

| Punkt                         | Zu entscheiden                                                                                                           |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Image-Registry                | Docker Hub (privat) oder GitHub Container Registry — inklusive Credential-Handling für RunPod                            |
| Embedding-Persistenz          | `pgvector`-Extension in Postgres oder separate Vektor-DB (z. B. Qdrant) — betrifft Re-ID-Performance und Infrastruktur   |
| SQL-Migrationsbasis           | Initiales Alembic-Baseline-Schema; Konventionen für Folge-Migrationen                                                    |
| Backend-Interface             | Konkreter Python-ABC-Vertrag für `AnalysisBackend` — Methoden, Input-/Output-Typen, Fehlerklassen                        |
| Secrets-Management            | Ablageort für API-Keys (RunPod, Google AI, xAI): `.env`-Datei auf VPS, Docker Secrets oder externer Vault                |
| Payload-Übertragung an RunPod | Frames als Base64 im Request-Body vs. als Referenz auf externen Speicher (Presigned URL) — abhängig von RunPod-Payload-Limits und Frame-Größe |
| Execution-Timeouts je Modul   | Maximale Ausführungszeit pro Serverless-Request, um hängende Jobs zu begrenzen                                           |

### 11.3 Pipeline-Semantik — in der Konzeption zu ergänzen

Diese Punkte fehlen in der aktuellen Spezifikation und sollten vor oder während der Implementierung in die Abschnitte §4 und §6 eingearbeitet werden.

- **Fehlerverhalten in der Pipeline:** Verhalten bei Modulausfall (partielle Ergebnisse, Job-Abbruch, Skip mit Markierung); Retry-Strategie pro Backend (Anzahl, Backoff).
- **Cold-Start-Toleranz:** Längere Timeouts für den ersten Serverless-Request pro Modul und Session; kein Abbruch bei verzögerter erster Antwort.
- **Idempotenz und Retry:** Jeder Handler-Call mit Request-ID; Worker-Logik sicher wiederholbar, damit verlorene Serverless-Requests ohne Seiteneffekte erneut abgesetzt werden können.
- **Frame-Extraktion:** Feste FPS, Keyframe-Extraktion oder szenenbasiert — beeinflusst Speicherbedarf und Genauigkeit.
- **Personen-Merge und -Split:** Konzept für manuelle Korrektur doppelt erkannter oder fälschlich zusammengefasster Personen durch den Analysten, inklusive Konsequenzen für `detections`, `cooccurrences` und Audit.
- **Ko-Vorkommen mit Zeitdimension:** Ergänzung von `first_seen` und `last_seen` in der Tabelle `cooccurrences`, damit „regelmäßig zusammen" von „einmalig zusammen" unterscheidbar wird.
- **Job-Abbruch:** Verhalten bei Abbruch — laufende RunPod-Calls canceln oder auslaufen lassen, partielle Ergebnisse verwerfen oder behalten, Storage aufräumen.
- **Rate-Limiting gegenüber externen Backends:** Worker-seitige Begrenzer für Google AI und xAI wegen Quotas.

### 11.4 Frontend — Detailentscheidungen

- Komponentenstruktur und State-Management (Empfehlung: React Query für Serverstate, Zustand für lokalen UI-State)
- API-Client-Generierung aus OpenAPI-Schema (lohnt sich bei FastAPI fast immer)
- Pagination, Filter und Suche für große Personen- und Detection-Listen
- Darstellungskonzept für Frame-Vorschauen (Thumbnail-Generierung, Lazy Loading)
- Dark Mode / Theme — einmal entscheiden

### 11.5 Betrieb und Infrastruktur

- **Backup-Strategie:** Postgres-Dumps (Zeitplan, Aufbewahrung, Zielort); Medien-Backup separat wegen Volumengröße; Restore-Test-Prozess.
- **Monitoring:** Container-Health, Job-Queue-Tiefe, RunPod-Kosten, externe API-Fehlerraten; schlankes Setup via Prometheus + Grafana oder Uptime Kuma.
- **Log-Aggregation:** Strukturierte Container-Logs (JSON) an zentralem Ort (Loki oder Datei-Rotation).
- **Fehlerbenachrichtigung:** E-Mail oder Webhook bei Job-Fehlern, kritischen Systemfehlern, Backend-Ausfall.
- **Nginx-Härtung:** Rate Limiting, Request-Size-Limits (Uploads), Security Headers, Timeouts.
- **Health Checks und Restart-Policies** in Docker Compose.
- **Deployment-Prozess:** Manuell via `docker compose pull && up` oder CI/CD (z. B. GitHub Actions); Migrations-Ausführung bei Deployment.
- **Storage-Management:** Quota, Cleanup verwaister Frames nach Projektlöschung, Speicher-Alarm bei X % Füllstand.
- **Network Volume bei RunPod:** Fallback-Option, falls Image-Größen problematisch werden — aktuell nicht vorgesehen.

### 11.6 Kosten und Ressourcen

- **Kostendisziplin (GPU-Zeit nur für Inferenz):** GPU-Sekunden fallen ausschließlich während der RunPod-Calls in Pipeline-Stufe 3 an. Vor- und Nachbereitung (Frame-Extraktion, Normalisierung, Bündelung, Fusion, Reporting) sowie Wartezeit auf User-Aktion laufen ausnahmslos auf dem VPS. Der RunPod-Client setzt einen Endpoint-Call erst dann ab, wenn der vollständige Payload bereitsteht (siehe §4.1 und §4.3).
- **RunPod-Kostenerfassung pro Job:** `request_duration × $/Sekunde` sollte in `jobs` als Feld mitgeführt werden.
- **Batch-Größe pro Modul:** Wirkt direkt auf Kosten, da Serverless pro Sekunde abgerechnet wird — Default-Werte sind beim Tuning zu bestimmen.

## 12. Zusammenfassung

AIMA ist ein modulares, vollständig über eine Weboberfläche bedienbares KI-Analyse-System. Es kombiniert lokale GPU-Verarbeitung über RunPod (Serverless) für sensible Inhalte mit optionaler externer KI-Unterstützung für Kontextanalyse. Das System ist auf einem VPS mit Docker Compose betrieben, für 2–3 Nutzer ausgelegt, DSGVO-konform konzipiert und so modular aufgebaut, dass neue Analysemodule und Datenfelder ohne Entwicklerbeteiligung ergänzt werden können.
