# Betriebskonzept: AIMA als "Docker-Only"-Setup

Dieses Dokument beschreibt ein vereinfachtes Betriebskonzept für AIMA, das ausschließlich auf Docker und `docker-compose` aufbaut. Es ist für Szenarien mit sporadischer Nutzung auf einem einzelnen Server (z.B. einem VPS oder einer lokalen Workstation mit GPU) ausgelegt, bei denen keine automatische Skalierung oder Hochverfügbarkeit erforderlich ist.

## 1. Zielsetzung und Anwendungsfall

*   **Ziel**: Bereitstellung einer funktionsfähigen AIMA-Instanz mit minimalem Einrichtungs- und Betriebsaufwand.
*   **Anwendungsfall**: Entwicklung, Tests, Demos oder die Durchführung einzelner, zeitlich begrenzter Analysen.
*   **Annahme**: Das System wird nicht unter Dauerlast betrieben. Die Nutzung erfolgt sporadisch.

## 2. Architektur

Die gesamte Anwendung wird über eine einzige `docker-compose.yml`-Datei auf einem einzelnen Host-System verwaltet. Alle Komponenten von AIMA laufen als isolierte Docker-Container.

*   **Orchestrierung**: `docker-compose` startet, stoppt und vernetzt alle notwendigen Dienste.
*   **Host**: Ein einzelner Server (physisch oder virtuell) mit Docker und Docker Compose.
*   **GPU-Zugriff**: Der AIMA-Worker-Container erhält über das NVIDIA Container Toolkit direkten Zugriff auf die GPU des Host-Systems.
*   **Netzwerk**: `docker-compose` erstellt ein internes Bridge-Netzwerk für die Kommunikation der Dienste. Ein Reverse-Proxy (z.B. Traefik oder Nginx, ebenfalls als Container) dient als zentraler Eingangspunkt und leitet Anfragen an die AIMA-API oder das Web-Frontend weiter.

 *Diagramm: Vereinfachte Darstellung der Docker-Only Architektur*

## 3. Komponenten & Konfiguration

Das Setup besteht aus den folgenden Kernkomponenten:

1.  **`docker-compose.yml`**: Die zentrale Definitionsdatei. Sie enthält:
    *   **`services`**: Definitionen für alle Container (AIMA-Backend, Datenbank, Message Queue, GPU-Worker, Reverse-Proxy).
    *   **`volumes`**: Persistente Speicherung für Datenbank-Dateien und Konfigurationen.
    *   **`networks`**: Definition des internen Netzwerks.

2.  **`.env`-Datei**: Eine Datei zur Auslagerung von Umgebungsvariablen wie Passwörtern, Ports, API-Schlüsseln und Pfaden. Dies vermeidet sensible Daten direkt in der `docker-compose.yml`.

3.  **Dienste (Beispielhafte Auswahl)**:
    *   `aima-backend`: Der Hauptanwendungs-Service.
    *   `aima-gpu-worker`: Ein separater Dienst für GPU-intensive Aufgaben. **Dieser wird nur bei Bedarf manuell gestartet.**
    *   `database`: Ein PostgreSQL- oder MariaDB-Container.
    *   `message-queue`: Ein RabbitMQ- oder Redis-Container.
    *   `reverse-proxy`: Ein Traefik-Container, der automatisch die anderen Dienste erkennt und nach außen verfügbar macht.

## 4. Betriebsablauf (Sporadische Nutzung)

Der manuelle, bedarfsgesteuerte Betrieb ist das Kernprinzip dieses Konzepts, um Kosten und Ressourcen zu sparen.

*   **Schritt 1: Systemstart (Basisdienste)**
    *   Der Nutzer verbindet sich per SSH mit dem Server.
    *   Mit dem Befehl `docker-compose up -d --remove-orphans` werden alle Basisdienste (Backend, DB, etc.) gestartet, aber **nicht** der GPU-Worker.

*   **Schritt 2: GPU-Analyse durchführen**
    *   Wenn eine rechenintensive Analyse ansteht, wird der GPU-Worker manuell hinzugeschaltet:
    *   `docker-compose up -d --no-deps aima-gpu-worker`
    *   Der Worker verbindet sich mit der Message Queue, nimmt den Job entgegen und beginnt mit der Verarbeitung auf der GPU.

*   **Schritt 3: GPU-Worker stoppen**
    *   Nach Abschluss der Analyse wird der GPU-Worker wieder heruntergefahren, um die GPU freizugeben und Strom zu sparen:
    *   `docker-compose stop aima-gpu-worker`

*   **Schritt 4: Gesamtes System stoppen**
    *   Wenn das System für längere Zeit nicht benötigt wird, können alle Dienste beendet und die Container entfernt werden:
    *   `docker-compose down`

## 5. Vor- und Nachteile

#### Vorteile:

*   **Maximale Einfachheit**: Das Setup ist leicht verständlich und schnell aufgesetzt.
*   **Minimale Kosten**: Es fallen nur die Fixkosten für den Server an. Teure GPU-Ressourcen werden nur bei aktivem Bedarf genutzt.
*   **Volle Kontrolle**: Der Nutzer hat die vollständige Kontrolle über die Umgebung und die Daten.
*   **Portabilität**: Das gesamte Setup kann leicht auf jeden anderen Rechner mit Docker umgezogen werden.

#### Nachteile:

*   **Manueller Aufwand**: Start und Stopp der Dienste sind manuelle Prozesse.
*   **Keine Skalierbarkeit**: Das System ist auf die Leistung des einen Servers beschränkt.
*   **Keine Hochverfügbarkeit**: Bei einem Ausfall des Servers oder eines Containers ist das System nicht erreichbar, bis ein manueller Eingriff erfolgt.
*   **Limitierte AIMA-Architektur**: Der GPU-Orchestrator, eine Kernkomponente von AIMA, hat in diesem Setup keine Funktion, da es nur eine einzige, feste GPU-Ressource gibt.