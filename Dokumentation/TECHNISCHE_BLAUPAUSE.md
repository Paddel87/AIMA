# Technische Blaupause für das AIMA-System

Dieses Dokument dient als einfache, hoch-levelige Blaupause für die technische Umsetzung des AIMA-Systems, basierend auf der Analyse der vorhandenen Projektdokumentation.

## 1. Hoch-Level Architektur

Das System wird als **Microservices-Architektur** konzipiert. Jeder Service ist ein unabhängiges, containerisiertes Modul, das über APIs kommuniziert. Die Kommunikation erfolgt ereignisgesteuert (event-driven) über einen Message Broker, um eine lose Kopplung zu gewährleisten.

**Architektur-Überblick:**

```
[Frontend/Clients] -> [API Gateway] -> [Backend Microservices]
                                     |
                                     v
                              [Message Broker]
                                     |
                                     v
                      [Analyse & GPU-Orchestrierung]
```

## 2. Kernmodule

1.  **API Gateway**: Zentraler Eingangspunkt. Verantwortlich für Routing, Authentifizierung und Rate Limiting.
2.  **User Management**: Verwaltet Benutzer, Rollen und Berechtigungen.
3.  **Media Ingestion & Storage**: Nimmt Mediendateien entgegen, validiert sie und speichert sie sicher (z.B. in einem S3-kompatiblen Speicher).
4.  **Job Management**: Erstellt, priorisiert und verwaltet Analyse-Jobs in einer Warteschlange.
5.  **GPU Orchestration**: Verwaltet dynamisch GPU-Ressourcen von verschiedenen Anbietern (Cloud & Lokal) und weist sie den Jobs zu.
6.  **Analyse-Pipelines**: Spezialisierte Services für die Analyse von Video-, Audio- und Bilddaten. Hier laufen die KI-Modelle.
7.  **Datenfusion (LLM)**: Ein übergeordnetes Sprachmodell (LLM) führt die Ergebnisse der einzelnen Analyse-Pipelines zu einem kohärenten Dossier zusammen.
8.  **Datenbank-Services**: Abstraktionsschicht für den Zugriff auf die verschiedenen Datenbanken.

## 3. Technologie-Stack (Vorschlag)

-   **Backend**: Python (FastAPI)
-   **Frontend**: React oder Vue.js
-   **Datenbanken**:
    -   **PostgreSQL**: Für strukturierte Daten (Benutzer, Metadaten, Jobs).
    -   **MongoDB**: Für semi-strukturierte Analyseergebnisse (JSON).
    -   **Milvus/Pinecone**: Für Vektor-Embeddings (Gesichts-, Bilderkennung).
-   **Containerisierung**: Docker
-   **Orchestrierung**: Kubernetes
-   **Message Broker**: RabbitMQ oder Kafka
-   **API Gateway**: Traefik oder Kong

## 4. Datenfluss (vereinfacht)

1.  **Upload**: Ein Benutzer lädt eine Mediendatei über das Frontend hoch.
2.  **Ingestion**: Das `Media Ingestion` Modul empfängt die Datei, prüft sie und speichert sie im Objektspeicher.
3.  **Job-Erstellung**: Das `Job Management` Modul erstellt einen neuen Analyse-Job und legt ihn in die Warteschlange.
4.  **Ressourcen-Zuweisung**: Der `GPU Orchestrator` reserviert eine passende GPU-Instanz.
5.  **Analyse**: Die Mediendatei wird zur GPU-Instanz transferiert. Die relevanten Analyse-Pipelines (Video, Audio etc.) werden ausgeführt.
6.  **Ergebnisspeicherung**: Die Roh-Ergebnisse jeder Pipeline werden in der MongoDB gespeichert, die Vektor-Embeddings in der Vektordatenbank.
7.  **Fusion**: Das LLM-Modul liest die Roh-Ergebnisse, fusioniert sie zu einem verständlichen Bericht und speichert diesen ebenfalls in der MongoDB.
8.  **Abschluss**: Der Job wird als abgeschlossen markiert und der Benutzer benachrichtigt.

## 5. Datenbank-Architektur

Es wird ein polyglotter Persistenzansatz verfolgt, um für jeden Datentyp die optimale Speicherlösung zu nutzen:

-   **PostgreSQL**: Dient als "Source of Truth" für alle strukturierten, relationalen Daten. Hier liegen die Kern-Entitäten wie `users`, `media_files` und `analysis_jobs`.
-   **MongoDB**: Dient als flexibler Speicher für die komplexen, oft verschachtelten JSON-Ausgaben der KI-Modelle und die finalen Dossiers.
-   **Milvus/Pinecone**: Spezialisierte Datenbank für die hocheffiziente Ähnlichkeitssuche auf Basis von Vektor-Embeddings, die von den KI-Modellen erzeugt werden.

Die Referenzen zwischen den Datenbanken (z.B. eine `job_id` aus PostgreSQL in einem MongoDB-Dokument) müssen auf Anwendungsebene konsistent gehalten werden.

## 6. Implementierungsphasen (vereinfacht)

1.  **Phase 1: MVP - Kerninfrastruktur**
    -   Grundlegende Microservices (API Gateway, Job Management).
    -   Manuelle GPU-Anbindung (ein Anbieter).
    -   Eine einfache Analyse-Pipeline (z.B. Personenerkennung im Bild).
    -   Grundlegendes Frontend für Upload und Ergebnis-Anzeige.

2.  **Phase 2: Erweiterung der Analysefähigkeiten**
    -   Implementierung weiterer Analyse-Pipelines (Audio, erweiterte Videoanalyse).
    -   Aufbau der Multi-Datenbank-Architektur.
    -   Einführung des LLM-basierten Fusions-Moduls.

3.  **Phase 3: Automatisierung & Skalierung**
    -   Implementierung des dynamischen GPU-Orchestrators.
    -   Optimierung der Performance und Kosten.
    -   Ausbau des Frontends mit interaktiven Analyse-Werkzeugen.

## 7. Kritische offene Fragen

Vor der Implementierung müssen dringend die im Dokument `UNKLARHEITEN.md` genannten Punkte geklärt werden. Die wichtigsten sind:

-   **Multi-Database-Transaktionen**: Wie wird die Datenkonsistenz über PostgreSQL, MongoDB und Milvus hinweg sichergestellt (z.B. bei Löschoperationen)?
-   **Kostenschätzung & Budget-Kontrolle**: Wie und wann werden die Analysekosten geschätzt und dem Benutzer zur Bestätigung vorgelegt?
-   **Fehlerbehandlung & Checkpoints**: Wie wird der Prozess bei einem Fehler in einer langen Analyse wieder aufgenommen, ohne von vorne beginnen zu müssen?
-   **Sicherheit & Compliance**: Wie wird die Ende-zu-Ende-Verschlüsselung und die Einhaltung von Datenschutzrichtlinien (z.B. DSGVO) in der verteilten Architektur konkret umgesetzt?