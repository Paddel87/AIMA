# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

## [0.2.1-alpha] - 2024-12-19

### Entfernt

- **Lokale GPU-Unterstützung:**
  - Vollständige Entfernung der lokalen GPU-Integration aus der Systemarchitektur
  - Löschung der `LOKALE_GPU_INTEGRATION.md` Dokumentation
  - Entfernung lokaler GPU-Referenzen aus allen Medienanalyse-Modulen (Audio, Bild, Video)
  - Aktualisierung der GPU-Provider-Strategie auf reine Cloud-GPU-Architektur
  - Vereinfachung der Entscheidungskriterien für GPU-Anbieterauswahl
  - Fokussierung auf RunPod, Vast.ai und große Cloud-Anbieter (AWS, GCP, Azure)

## [0.2.0-alpha] - 2024-12-19

### Hinzugefügt

- **User Management Service (Phase 1.2 - Iteration 1.2):**
  - Vollständige Implementierung des User Management Moduls gemäß UMSETZUNGSKONZEPT.md
  - FastAPI-basierte REST-API mit umfassenden Authentifizierungs- und Autorisierungsfunktionen
  - JWT-basierte Authentifizierung mit Access- und Refresh-Tokens
  - Rollen-basierte Zugriffskontrolle (RBAC) mit Admin-, User- und Guest-Rollen
  - PostgreSQL-Datenbankintegration mit Alembic-Migrationen
  - Redis-basiertes Session-Management
  - Umfassende Admin-API für Benutzerverwaltung, Systemstatistiken und Audit-Logging
  - Docker-basierte Entwicklungsumgebung mit PostgreSQL, Redis, RabbitMQ
  - Monitoring-Integration mit Prometheus und Grafana
  - Passwort-Reset-Funktionalität und Sicherheitsfeatures
  - Strukturiertes Logging und Health-Check-Endpunkte
  - Vollständige API-Dokumentation über FastAPI's automatische OpenAPI-Integration

## [0.1.0-alpha] - 2024-07-30

### Hinzugefügt

- **Projektinitialisierung und konzeptionelle Dokumentation:**
  - Erstellung der grundlegenden Ordnerstruktur für die Dokumentation.
  - Ausarbeitung von Kerndokumenten, die die Systemarchitektur, Workflows und technische Konzepte definieren. Dazu gehören:
    - `DATENBANKARCHITEKTUR.md`: Definition der Datenbankstrategie (PostgreSQL, MongoDB, Milvus).
    - `MEDIENWORKFLOW.md`: Beschreibung des gesamten Medienverarbeitungsprozesses.
    - `PIPELINE_KONZEPT.md`: Detaillierung der Analyse-Pipeline.
    - `UI_KONZEPT.md`: Entwurf der Benutzeroberfläche und Interaktionsprinzipien.
    - `TRANSAKTIONSKONZEPT_SAGA.md`: Konzept für verteilte Transaktionen.
    - `SERVICE_DISCOVERY.md`: Konzept für die Dienstfindung in der Microservice-Architektur.
    - `EVENT_ORDERING_KONZEPT.md`: Sicherstellung der Ereignisreihenfolge.
    - `CIRCUIT_BREAKER_KONZEPT.md`: Implementierung des Circuit Breaker Patterns.
    - `PRAEDIKTIVE_SKALIERUNG.md`: Konzept zur prädiktiven Skalierung von Ressourcen.
    - `CHECKPOINT_MECHANISMUS.md`: Mechanismus zur Sicherung langlaufender Prozesse.
    - `UMSETZUNGSKONZEPT.md`: Detaillierter, iterativer Plan für die Implementierung des AIMA-Systems, inklusive des Grundprinzips der autonomen, dokumentenbasierten Arbeitsweise der KI.
  - Archivierung initialer Brainstorming- und Unklarheiten-Dokumente (`UNKLARHEITEN.md`, `FEHLENDE_TEILBEREICHE.md`).