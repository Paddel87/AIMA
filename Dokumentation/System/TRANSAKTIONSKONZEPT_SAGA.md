# Transaktionskonzept: Das Saga-Pattern für AIMA

**Status:** Entwurf
**Datum:** 25.07.2024

## 1. Einleitung und Problemstellung

Die Microservice-Architektur von AIMA nutzt spezialisierte Datenbanken für unterschiedliche Aufgaben:

- **PostgreSQL:** Relationale Daten (Benutzer, Metadaten, Job-Status).
- **MongoDB:** Semistrukturierte Analyseergebnisse (JSON-Dokumente).
- **Milvus:** Vektor-Embeddings für Ähnlichkeitssuchen.

Ein einzelner Geschäftsprozess, wie die Aufnahme und Analyse eines neuen Mediums, erfordert Schreibvorgänge in mehreren dieser Datenbanken. Standard-ACID-Transaktionen sind über die Grenzen von Microservices und deren dedizierten Datenbanken hinweg nicht möglich. Dies führt zur Herausforderung der **Gewährleistung von Datenkonsistenz** bei verteilten Operationen.

Wenn ein Schritt in der Kette fehlschlägt, muss das System in einen konsistenten Zustand zurückkehren, ohne inkonsistente Teildaten zu hinterlassen. Dieses Dokument beschreibt die Verwendung des **Saga-Patterns** als Lösungsstrategie.

## 2. Das Saga-Pattern

Eine Saga ist eine Sequenz von lokalen Transaktionen, die von verschiedenen Microservices ausgeführt werden. Jeder lokale Transaktion aktualisiert die Datenbank seines Services und löst die nächste Transaktion in der Saga aus. Wenn eine lokale Transaktion fehlschlägt, führt die Saga eine Reihe von **kompensierenden Transaktionen** aus, um die vorherigen erfolgreichen Transaktionen rückgängig zu machen.

Es gibt zwei gängige Implementierungsarten:

1.  **Choreographie:** Jeder Service publiziert ein Ereignis (Event), wenn seine lokale Transaktion abgeschlossen ist. Andere Services hören auf diese Events und führen ihre eigenen lokalen Transaktionen aus. Dies ist dezentral und einfach, kann aber bei komplexen Sagas unübersichtlich werden.
2.  **Orchestrierung:** Ein zentraler Orchestrator (Saga Execution Coordinator) steuert die Saga. Er sendet Befehle an die einzelnen Services, um deren lokale Transaktionen auszuführen. Der Orchestrator ist für den gesamten Ablauf verantwortlich, einschließlich der Ausführung von kompensierenden Transaktionen im Fehlerfall. Dies ist zentralisiert und einfacher zu verwalten und zu überwachen.

**Für AIMA wird das Orchestrierungs-Modell empfohlen**, da es eine bessere Kontrolle und Übersicht über die komplexen Analyse-Workflows bietet.

## 3. Anwendungsbeispiel: Medien-Ingestion-Saga

Der Prozess der Aufnahme und Analyse eines neuen Videos ist ein idealer Anwendungsfall für eine Saga.

**Saga-Orchestrator:** `Workflow-Manager-Service`

**Beteiligte Services:**
- `Media-Storage-Service` (mit PostgreSQL)
- `Analysis-Service` (mit MongoDB)
- `Vector-DB-Service` (mit Milvus)

### Positiver Verlauf (Happy Path)

1.  **Start Saga:** Der `Workflow-Manager` startet die `MediaIngestionSaga`.
2.  **Schritt 1: Medium speichern**
    - **Befehl:** `Workflow-Manager` -> `Media-Storage-Service`: `createMediaEntry(video_data)`
    - **Lokale Transaktion:** `Media-Storage-Service` speichert das Video und legt einen Metadaten-Eintrag in PostgreSQL an.
    - **Antwort:** `Media-Storage-Service` -> `Workflow-Manager`: `mediaEntryCreated(media_id)`
3.  **Schritt 2: Analyse durchführen & speichern**
    - **Befehl:** `Workflow-Manager` -> `Analysis-Service`: `analyzeAndStoreResults(media_id)`
    - **Lokale Transaktion:** `Analysis-Service` führt die Analyse durch und speichert das Ergebnis-JSON in MongoDB.
    - **Antwort:** `Analysis-Service` -> `Workflow-Manager`: `analysisCompleted(analysis_id)`
4.  **Schritt 3: Vektoren generieren & speichern**
    - **Befehl:** `Workflow-Manager` -> `Vector-DB-Service`: `createEmbeddings(analysis_id)`
    - **Lokale Transaktion:** `Vector-DB-Service` extrahiert relevante Daten (z.B. Gesichter), generiert Vektor-Embeddings und speichert sie in Milvus.
    - **Antwort:** `Vector-DB-Service` -> `Workflow-Manager`: `embeddingsCreated()`
5.  **Ende Saga:** Der `Workflow-Manager` markiert die Saga als erfolgreich abgeschlossen.

### Fehlerverlauf (Compensation Path)

Angenommen, **Schritt 3 schlägt fehl** (z.B. Milvus ist nicht verfügbar).

1.  **Fehlererkennung:** Der `Vector-DB-Service` meldet einen Fehler an den `Workflow-Manager`.
2.  **Start Kompensation:** Der `Workflow-Manager` startet die kompensierenden Transaktionen in umgekehrter Reihenfolge.
3.  **Kompensation für Schritt 2:**
    - **Befehl:** `Workflow-Manager` -> `Analysis-Service`: `deleteAnalysisResults(analysis_id)`
    - **Lokale Transaktion:** `Analysis-Service` löscht das entsprechende Dokument aus MongoDB.
4.  **Kompensation für Schritt 1:**
    - **Befehl:** `Workflow-Manager` -> `Media-Storage-Service`: `deleteMediaEntry(media_id)`
    - **Lokale Transaktion:** `Media-Storage-Service` löscht den Metadaten-Eintrag aus PostgreSQL und ggf. die Videodatei.
5.  **Ende Saga:** Der `Workflow-Manager` markiert die Saga als fehlgeschlagen und kompensiert.

Das System befindet sich nun wieder in einem konsistenten Zustand.

## 4. Implementierungsdetails und Überlegungen

- **Idempotenz:** Alle Transaktionen (sowohl die Vorwärts- als auch die Kompensationstransaktionen) müssen idempotent sein. Das bedeutet, dass eine mehrfache Ausführung derselben Transaktion zum selben Ergebnis führt. Dies ist wichtig, um mit Netzwerkfehlern und Wiederholungen umgehen zu können.
- **Saga Log:** Der Orchestrator muss den Zustand jeder Saga-Instanz persistent speichern (z.B. in seiner eigenen Datenbank). Dieses Saga-Log ist entscheidend für die Wiederherstellung nach einem Absturz des Orchestrators.
- **Isolation:** Sagas bieten keine vollständige Isolation wie ACID-Transaktionen. Zwischenschritte sind für andere Transaktionen sichtbar (z.B. könnte ein anderer Service die Analyseergebnisse in MongoDB sehen, bevor die Saga abgeschlossen ist). Dies muss bei der Systemgestaltung berücksichtigt werden (z.B. durch Status-Flags wie `PENDING_CONFIRMATION`).

## 5. Fazit

Das Saga-Pattern (in der Orchestrierungsvariante) ist eine robuste und bewährte Methode, um die Datenkonsistenz in der verteilten Architektur von AIMA zu gewährleisten. Es wird als primäres Muster für komplexe, serviceübergreifende Geschäftsprozesse festgelegt.