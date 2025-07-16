# AIMA System - API Mapping

Dieses Dokument dient als zentrale Referenz für alle API-Endpunkte innerhalb des AIMA-Systems. Es konsolidiert die Informationen aus den verschiedenen Konzeptdokumenten und beschreibt die Schnittstellen der einzelnen Module.

## 1. API-Grundlagen

- **Architektur**: Das System nutzt eine Microservice-Architektur. Die Kommunikation erfolgt primär über REST-APIs und GraphQL.
- **Gateway**: Ein API-Gateway (z.B. Kong oder Traefik) dient als zentraler Eingangspunkt für alle Anfragen. Es ist verantwortlich für Routing, Authentifizierung (JWT/OAuth 2.0), Rate Limiting und die Bereitstellung einer öffentlichen Swagger/OpenAPI-Dokumentation.
- **Versionierung**: APIs werden semantisch versioniert, um Abwärtskompatibilität zu gewährleisten.

## 2. Modul-spezifische API-Endpunkte

### 2.1 Core Infrastructure Modules

#### User Management Module
- **Technologie**: REST API
- **Endpunkte**:
  - `POST /api/users/register`: Registriert einen neuen Benutzer.
  - `POST /api/users/login`: Authentifiziert einen Benutzer und gibt ein JWT-Token zurück.
  - `POST /api/users/logout`: Beendet die Sitzung eines Benutzers.
  - `GET /api/users/me`: Ruft das Profil des aktuellen Benutzers ab.
  - `PUT /api/users/me`: Aktualisiert das Profil des aktuellen Benutzers.
  - `GET /api/users/{user_id}`: Ruft die Daten eines bestimmten Benutzers ab (Admin-Zugriff).

#### Configuration Management Module
- **Technologie**: REST API
- **Endpunkte**:
  - `GET /api/config`: Ruft die gesamte Systemkonfiguration ab.
  - `GET /api/config/{key}`: Ruft einen spezifischen Konfigurationswert ab.
  - `PUT /api/config/{key}`: Aktualisiert einen Konfigurationswert (Admin-Zugriff).

### 2.2 Media & Data Layer Modules

#### Media Lifecycle Management Module
- **Technologie**: REST API & WebSockets
- **Endpunkte**:
  - `POST /api/media/upload`: Lädt eine neue Mediendatei hoch.
  - `GET /api/media`: Ruft eine Liste der Mediendateien ab (mit Paginierung und Filterung).
  - `GET /api/media/{media_id}`: Ruft die Metadaten einer spezifischen Mediendatei ab.
  - `DELETE /api/media/{media_id}`: Löscht eine Mediendatei.
  - `WS /api/media/upload/progress`: WebSocket zur Überwachung des Upload-Fortschritts.

#### Data Abstraction & Persistence Module
- **Technologie**: GraphQL
- **Endpunkt**: `/graphql`
- **Beschreibung**: Stellt eine flexible Schnittstelle für komplexe Abfragen auf den verbundenen Datenbanken (PostgreSQL, MongoDB, Milvus) bereit. Dies wird hauptsächlich von der Benutzeroberfläche genutzt.
- **Beispiel-Queries (aus `BENUTZEROBERFLAECHE_UND_INTERAKTION.md`):
  - `query GetMediaLibrary(...)`: Ruft die Medienbibliothek ab.
  - `query GetDossierDetails(...)`: Ruft die Details eines Dossiers ab.
- **Beispiel-Mutations**:
  - `mutation CreateDossier(...)`: Erstellt ein neues Dossier.
  - `mutation UpdateDossier(...)`: Aktualisiert ein bestehendes Dossier.

### 2.3 Analysis & Fusion Modules

#### Job Management Module
- **Technologie**: REST API
- **Endpunkte**:
  - `POST /api/jobs`: Erstellt einen neuen Analyse-Job.
  - `GET /api/jobs`: Ruft eine Liste der Jobs ab.
  - `GET /api/jobs/{job_id}`: Ruft den Status und die Details eines spezifischen Jobs ab.
  - `POST /api/jobs/{job_id}/cancel`: Bricht einen laufenden Job ab.

#### GPU Orchestration Module
- **Technologie**: REST API
- **Endpunkte**:
  - `GET /api/gpus/instances`: Ruft eine Liste der verfügbaren und aktiven GPU-Instanzen ab.
  - `POST /api/gpus/instances`: Startet eine neue GPU-Instanz (interner Gebrauch).
  - `DELETE /api/gpus/instances/{instance_id}`: Terminiert eine GPU-Instanz (interner Gebrauch).

#### Cost Estimation API (Teil des Job Management)
- **Technologie**: REST API
- **Präfix**: `/api/cost`
- **Endpunkte (aus `KOSTENSCHAETZUNG.md`):
  - `POST /api/cost/estimate`: Schätzt die Kosten für einen Job basierend auf der Konfiguration.
  - `GET /api/cost/pricing`: Ruft die aktuellen Preislisten für Ressourcen ab (Admin-Zugriff).
  - `PUT /api/cost/pricing/{category}`: Aktualisiert die Preislisten (Admin-Zugriff).

### 2.4 Mobile API

- **Technologie**: REST API (optimiert für mobile Clients)
- **Beschreibung**: Eine dedizierte API für mobile Clients mit optimierten Endpunkten.
- **Beispiel-Controller (aus `BENUTZEROBERFLAECHE_UND_INTERAKTION.md`):
  - `authenticate(username, password, device_id)`: Authentifiziert einen mobilen Benutzer.
  - `get_recent_dossiers(user_id, limit)`: Ruft eine optimierte Liste der letzten Dossiers ab.