# AIMA: Betriebskonzept für den Idle-Modus auf einem VPS

Dieses Dokument beschreibt die Architektur und den Arbeitsablauf, um AIMA in einem kosteneffizienten "Idle-Modus" auf einem herkömmlichen Virtual Private Server (VPS) zu betreiben. Das Kernprinzip ist die Minimierung der permanenten Kosten, indem teure Rechenressourcen (insbesondere GPUs) nur bei tatsächlichem Bedarf dynamisch und extern angemietet werden.

## 1. Zielsetzung

Das primäre Ziel ist es, die AIMA-Basisinfrastruktur dauerhaft auf einem kostengünstigen VPS laufen zu lassen. Das System befindet sich die meiste Zeit im Ruhezustand ("Idle") und aktiviert rechenintensive Prozesse nur für die Dauer einer konkreten Analyse-Anfrage ("Job").

## 2. Architektur: Trennung von Dauerbetrieb und Bedarfsanalyse

Die Architektur ist in zwei klar getrennte Bereiche aufgeteilt:

### 2.1. Komponenten im Dauerbetrieb (Auf dem VPS)

Diese Komponenten sind immer aktiv und bilden das Rückgrat von AIMA. Sie sind ressourcenschonend und können problemlos auf einem Standard-VPS mittels **Docker Compose** betrieben werden. Ein komplexes Kubernetes-Setup ist für dieses Szenario **nicht notwendig**.

Ihr spezifischer **Netcup VPS 1000 G11** mit **4 vCores, 8 GB RAM und 256 GB NVMe SSD** ist für dieses Szenario **hervorragend geeignet** und bietet sogar Leistungsreserven. <mcreference link="https://www.vpsbenchmarks.com/hosters/netcup/plans/rs-1000-g11" index="1">1</mcreference>

*   **API-Gateway & Web-Interface**: Der zentrale Eingangspunkt für Benutzerinteraktionen und API-Aufrufe.
*   **Metadaten-Datenbank**: Eine leichtgewichtige Datenbank (z.B. PostgreSQL oder MariaDB in einem Docker-Container) zur Speicherung von Job-Informationen, Benutzerdaten und Analyseergebnissen.
*   **Job-Queue**: Ein Nachrichtenbroker (z.B. RabbitMQ oder Redis in einem Docker-Container), der Analyse-Aufträge entgegennimmt und zur Verarbeitung vorhält.
*   **Orchestrator-Service**: Ein kleiner, permanenter Dienst, der die Job-Queue überwacht. Seine Hauptaufgabe ist es, bei neuen Jobs den Prozess der externen Ressourcenbeschaffung anzustoßen.

### 2.2. Komponenten bei Bedarf (On-Demand, extern)

Diese Komponenten werden nur bei Bedarf gestartet und nach Abschluss der Aufgabe sofort wieder beendet. Die Kosten fallen nur für die tatsächliche Nutzungsdauer an.

*   **GPU-Analyse-Worker**: Ein Docker-Container mit den notwendigen KI-Modellen und der Analyselogik. Dieser wird nicht auf dem VPS, sondern auf einer externen GPU-Instanz ausgeführt.
*   **Externe GPU-Provider**: Dienste wie **RunPod**, **Vast.ai** oder andere, die eine API zur programmatischen Anmietung von GPU-Instanzen auf Minuten- oder Sekundenbasis anbieten.

## 3. Workflow einer Analyse-Anfrage

1.  **Job-Erstellung**: Ein Benutzer lädt ein Medium über das Web-Interface hoch oder stellt eine Anfrage über die API. Das API-Gateway erstellt einen neuen Job und legt ihn in der **Job-Queue** ab.
2.  **Job-Erkennung**: Der **Orchestrator-Service** auf dem VPS erkennt den neuen Job in der Queue.
3.  **Ressourcen-Beschaffung**: Der Orchestrator kontaktiert per API den ausgewählten **externen GPU-Provider** (z.B. RunPod) und fordert eine GPU-Instanz mit einem vordefinierten Docker-Image (dem GPU-Analyse-Worker) an.
4.  **Analyse-Durchführung**: Sobald die externe Instanz bereit ist, führt der **GPU-Analyse-Worker** die Analyse des Mediums durch. Er kommuniziert dabei mit der **Metadaten-Datenbank** auf dem VPS, um Ergebnisse zu speichern.
5.  **Job-Abschluss & Ressourcen-Freigabe**: Nach Abschluss der Analyse meldet der Worker den Erfolg an den Orchestrator (z.B. über eine Statusänderung in der Datenbank).
6.  **Terminierung**: Der Orchestrator sendet sofort einen Befehl an die API des GPU-Providers, um die externe Instanz zu **beenden** und die Kostenbelastung zu stoppen.

## 4. Vorteile dieses Modells

*   **Minimale Fixkosten**: Die monatlichen Kosten beschränken sich auf die Miete des VPS (oft nur 5-10 €).
*   **Pay-per-Use für teure Ressourcen**: GPU-Kosten fallen nur an, wenn tatsächlich eine Analyse durchgeführt wird.
*   **Einfache Infrastruktur**: Ein Setup mit Docker Compose auf einem einzelnen VPS ist deutlich einfacher zu verwalten als ein Kubernetes-Cluster.
*   **Maximale Flexibilität**: Der GPU-Provider kann jederzeit gewechselt oder sogar dynamisch (je nach Preis und Verfügbarkeit) ausgewählt werden, ohne die Basisinfrastruktur zu verändern.
*   **Klare Skalierbarkeit**: Die Basisinfrastruktur muss nicht skaliert werden. Skalierung findet statt, indem bei Bedarf mehrere externe GPU-Instanzen parallel gestartet werden.