# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

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
  - Archivierung initialer Brainstorming- und Unklarheiten-Dokumente (`UNKLARHEITEN.md`, `FEHLENDE_TEILBEREICHE.md`).