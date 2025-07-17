# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

## [0.3.1-alpha] - 2025-07-18

### Behoben

- **🚨 Kritisches Build-Problem gelöst:**
  - Lösung des Problems fehlgeschlagener Builds durch vergessene Dependency-Installation
  - Integration isolierter Services in zentrale `docker-compose.yml`
  - Eliminierung von Port-Konflikten zwischen Services
  - Implementierung robuster Bottom-to-Top Build-Strategie

### Hinzugefügt

- **🏗️ Robuste Build-Infrastruktur:**
  - `build.ps1`: PowerShell-Skript für Windows mit umfassenden Health-Checks
  - `build.sh`: Bash-Skript für Linux/macOS mit farbigem Output
  - `Makefile`: Vereinfachte Build-Befehle (`make build`, `make status`, `make health`)
  - `BUILD_FIX_DOCUMENTATION.md`: Detaillierte Dokumentation des Problems und der Lösung

- **🌐 API Gateway Integration:**
  - Traefik-Integration für Service-Discovery und Load-Balancing
  - Automatisches Routing für User Management (`/api/v1/users`)
  - Automatisches Routing für Configuration Management (`/api/v1/config`)
  - Zentrale Eingangsschnittstelle über Port 8080

- **📊 Erweiterte Service-Integration:**
  - User Management Service vollständig in Haupt-docker-compose integriert
  - Configuration Management Service vollständig in Haupt-docker-compose integriert
  - Einheitliche Umgebungsvariablen und Infrastruktur-Nutzung
  - Explizite Service-Dependencies mit `depends_on`

### Geändert

- **📋 Aktualisierte Dokumentation:**
  - `README.md`: Umfassender Schnellstart-Guide mit Build-Anweisungen
  - Service-Endpoints-Tabelle mit allen verfügbaren URLs
  - Troubleshooting-Guides und nützliche Befehle
  - Entwicklungsstatus auf "Foundation Services aktiv" aktualisiert

- **🔧 Verbesserte Build-Prozesse:**
  - Systematische Health-Checks für PostgreSQL, Redis, RabbitMQ
  - Warteschleifen zwischen Service-Starts für Stabilität
  - Umfassende Fehlerbehandlung und Logging
  - Automatische Cleanup-Funktionen vor Build-Start

### Technische Details

- **Service-Ports:**
  - User Management: `8001:8000` (Container-intern Port 8000)
  - Configuration Management: `8002:8002`
  - API Gateway (Traefik): `8080:8080`
  - Alle Infrastruktur-Services beibehalten

- **Dependency-Hierarchie:**
  ```
  Infrastructure (PostgreSQL, Redis, RabbitMQ) → 
  User Management → 
  Configuration Management
  ```

- **Health-Check-Endpoints:**
  - User Management: `http://localhost:8001/api/v1/health/`
  - Configuration Management: `http://localhost:8002/health`
  - API Gateway Dashboard: `http://localhost:8080`

## [0.3.0-alpha] - 2025-07-17

### Geändert

- **Configuration Management Service (Phase 1.2 - Kritische Reparatur):**
  - Vollständige Überarbeitung des Configuration Management Service nach Bottom-to-Top-Prinzip
  - Implementierung einer robusten Startup-Sequenz mit graceful initialization
  - Verbesserung der Dockerfile mit Multi-Stage-Build für erhöhte Sicherheit und Performance
  - Optimierung der Service-Dependencies mit Fallback-Mechanismen
  - Implementierung umfassender Health-Checks und Monitoring
  - Hinzufügung fehlender Imports und Stabilisierung der Service-Architektur
  - Anpassung an das überarbeitete UMSETZUNGSKONZEPT.md mit Bottom-to-Top-Entwicklungsphilosophie

- **Systemarchitektur:**
  - Überarbeitung des UMSETZUNGSKONZEPT.md mit neuer Bottom-to-Top-Entwicklungsphilosophie
  - Klassifizierung des Configuration Management Service als kritisch instabil
  - Definition klarer Dependency-Hierarchien und Validierungskriterien
  - Etablierung des User Management Service als Vorbild für stabile Service-Entwicklung

## [0.2.1-alpha] - 2024-12-19

### Geändert

- **Framework-Architektur:**
  - Wechsel von Kubernetes zu Docker-only Betriebskonzept
  - Vereinfachung der Infrastruktur durch Fokussierung auf Docker Compose
  - Reduzierung der Komplexität und Betriebskosten
  - Anpassung der Deployment-Strategie für kleinere bis mittlere Workloads

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