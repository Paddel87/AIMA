# Service Discovery in der AIMA-Architektur

## 1. Problemstellung: Kommunikation in einer dynamischen Microservice-Umgebung

Die AIMA-Plattform ist als eine verteilte Ansammlung von Microservices konzipiert. Jeder Service (z.B. `api-gateway`, `user-management`, `media-ingestion`, `face-detection-model`) läuft als unabhängige Instanz. In einer modernen, Cloud-nativen Umgebung sind die Netzwerkstandorte (IP-Adressen und Ports) dieser Instanzen nicht statisch. Sie können sich aus verschiedenen Gründen ändern:

-   **Skalierung:** Um auf Lastspitzen zu reagieren, werden automatisch neue Instanzen eines Dienstes gestartet (horizontale Skalierung).
-   **Ausfallsicherheit (Resilienz):** Fällt eine Instanz oder ein ganzer Host aus, wird der Dienst an anderer Stelle im Cluster neu gestartet.
-   **Deployments:** Bei der Aktualisierung eines Dienstes werden alte Instanzen heruntergefahren und neue gestartet (z.B. bei Rolling Updates).

Das manuelle Verwalten und Hartcodieren von Netzwerkadressen in Konfigurationsdateien ist unter diesen Umständen unmöglich, extrem fehleranfällig und widerspricht den Prinzipien einer agilen und robusten Architektur.

## 2. Lösung: Das Service-Discovery-Muster

Service Discovery ist ein Architekturmuster, das dieses Problem löst, indem es einen Mechanismus zur dynamischen Abfrage von Dienstestandorten bereitstellt. Es fungiert als eine Art automatisches, stets aktuelles "Telefonbuch" für die Dienste innerhalb des Systems.

Das Muster besteht aus zwei Kernkomponenten:

### 2.1. Service Registry

Die **Service Registry** ist eine zentrale, hochverfügbare Datenbank, die eine Liste aller aktiven Service-Instanzen und ihrer Metadaten (insbesondere IP-Adresse und Port) enthält. Sie ist die "Single Source of Truth" für die Erreichbarkeit von Diensten.

### 2.2. Registrierungs- und Entdeckungsprozess

-   **Service Registration (Selbstregistrierung):**
    1.  Wenn eine neue Service-Instanz startet, registriert sie sich proaktiv bei der Service Registry.
    2.  Sie übermittelt dabei ihre Service-ID (z.B. `face-detection-service`), ihre Netzwerkadresse (`10.1.2.3:8080`) und optional weitere Metadaten (z.B. `version=1.2`).
    3.  Die Instanz sendet in regelmäßigen Abständen ein "Lebenszeichen" (Health Check / Heartbeat) an die Registry. Bleibt dieser Heartbeat aus, geht die Registry davon aus, dass die Instanz nicht mehr fehlerfrei funktioniert, und entfernt sie aus der Liste der verfügbaren Instanzen.

-   **Service Discovery (Entdeckung):**
    1.  Wenn ein Client-Service (z.B. der `api-gateway`) mit einem anderen Service (z.B. dem `user-management`) kommunizieren möchte, kontaktiert er nicht direkt eine ihm bekannte Adresse.
    2.  Stattdessen stellt er eine Anfrage an die Service Registry: "Gib mir eine oder mehrere gesunde Instanzen des Services `user-management`."
    3.  Die Registry antwortet mit einer Liste der aktuell verfügbaren und als fehlerfrei markierten Instanzen.
    4.  Der Client kann nun eine dieser Adressen für die Kommunikation verwenden. Oft wird hier client-seitiges Load-Balancing angewendet, um die Anfragen auf die verfügbaren Instanzen zu verteilen (z.B. per Round-Robin).

## 3. Empfehlung für AIMA: HashiCorp Consul

Für die Implementierung von Service Discovery in AIMA wird der Einsatz von **HashiCorp Consul** empfohlen.

**Warum Consul?**
-   **Industriestandard:** Consul ist ein etabliertes, weit verbreitetes und gut dokumentiertes Werkzeug.
-   **Mehr als nur Service Discovery:** Es bietet ein umfassendes Set an Features, die für eine Microservice-Architektur wertvoll sind:
    -   **Health Checking:** Umfangreiche Mechanismen zur Überprüfung des Zustands von Diensten.
    -   **Verteiltes Key-Value-Store:** Kann als zentraler Ort für die Verwaltung von Konfigurationsparametern genutzt werden.
    -   **Service Mesh:** Bietet erweiterte Funktionen für sichere Service-zu-Service-Kommunikation (mTLS), Traffic-Management und Observability.
-   **Plattformunabhängig:** Läuft auf allen gängigen Betriebssystemen und lässt sich nahtlos in Container-Orchestrierungs-Plattformen wie Kubernetes oder Nomad integrieren.

## 4. Integrationsszenario

1.  Ein Consul-Cluster (typischerweise 3-5 Server-Knoten für Hochverfügbarkeit) wird als zentrale Service Registry aufgesetzt.
2.  Jeder Microservice in der AIMA-Plattform integriert einen Consul-Client (oft als Bibliothek in der jeweiligen Programmiersprache verfügbar).
3.  Beim Start registriert sich der Microservice bei Consul.
4.  Für die Kommunikation zwischen den Diensten wird die Consul-API oder das integrierte DNS-Interface von Consul genutzt, um die Adressen anderer Dienste dynamisch aufzulösen.