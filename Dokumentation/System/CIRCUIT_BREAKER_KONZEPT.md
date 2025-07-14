# Circuit Breaker Pattern

## 1. Problemstellung

In einer verteilten Microservice-Architektur wie AIMA, in der Dienste voneinander abhängen, kann der Ausfall oder die Latenz eines einzelnen Dienstes zu kaskadierenden Fehlern führen. Wenn beispielsweise der Gesichtserkennungs-Service nicht verfügbar ist, würden alle Dienste, die auf dessen Ergebnisse warten (z.B. der Fusions-Service oder die API-Endpunkte), blockiert werden. Dies führt zu langen Wartezeiten, verbrauchten Ressourcen (Threads, Sockets) und kann im schlimmsten Fall das gesamte System zum Erliegen bringen.

## 2. Lösungsansatz: Das Circuit Breaker Pattern

Das Circuit Breaker Pattern ist ein Entwurfsmuster zur Steigerung der Stabilität und Resilienz. Es agiert als zustandsbehafteter Proxy zwischen einem aufrufenden Dienst (Consumer) und einem potenziell unzuverlässigen Dienst (Provider). Der "Breaker" überwacht die Aufrufe und kann den "Stromkreis" unterbrechen, um den Provider vor Überlastung und den Consumer vor dem Warten auf fehlgeschlagene Aufrufe zu schützen.

Der Circuit Breaker hat drei Zustände:

### a) Closed (Geschlossen)

Dies ist der Normalzustand. Alle Anfragen vom Consumer werden an den Provider weitergeleitet. Der Breaker überwacht die Anzahl der Fehlschläge (z.B. durch Timeouts oder explizite Fehlercodes). Wenn die Fehlerrate innerhalb eines bestimmten Zeitfensters einen vordefinierten Schwellenwert überschreitet, wechselt der Breaker in den `Open`-Zustand.

### b) Open (Offen)

In diesem Zustand wird der "Stromkreis" unterbrochen. Alle Anfragen an den Provider werden sofort und ohne Ausführung des eigentlichen Aufrufs mit einem Fehler (z.B. "Service unavailable") beantwortet. Dies wird als "Fail Fast" bezeichnet. Der Breaker verbleibt für eine festgelegte Timeout-Dauer in diesem Zustand, um dem ausgefallenen Dienst Zeit zur Wiederherstellung zu geben.

### c) Half-Open (Halb-Offen)

Nach Ablauf des Timeouts wechselt der Breaker in den `Half-Open`-Zustand. In diesem Zustand lässt er eine begrenzte Anzahl von Test-Anfragen zum Provider durch.

*   **Erfolg:** Wenn diese Test-Anfragen erfolgreich sind, geht der Breaker davon aus, dass der Provider wieder stabil ist, und wechselt zurück in den `Closed`-Zustand. Der normale Betrieb wird wieder aufgenommen.
*   **Fehlschlag:** Wenn eine der Test-Anfragen fehlschlägt, schließt der Breaker den Stromkreis sofort wieder (wechselt zurück in den `Open`-Zustand) und startet den Timeout-Timer erneut. Dies verhindert, dass ein noch instabiler Dienst erneut mit Anfragen überflutet wird.

## 3. Implementierung und Integration in AIMA

Die Implementierung des Circuit Breaker Patterns erfolgt typischerweise nicht von Grund auf, sondern durch die Nutzung etablierter Bibliotheken.

*   **Technologie:** Je nach gewähltem Programmiersprachen-Stack können Bibliotheken wie `Polly` (.NET), `Resilience4j` (Java) oder `istio` (Service Mesh-basiert) verwendet werden.
*   **Anwendungspunkte:** Circuit Breaker sollten an allen kritischen Kommunikationspunkten zwischen den Microservices implementiert werden, insbesondere bei Aufrufen von:
    *   API-Gateway zu den Backend-Services.
    *   Orchestrierungs-Services zu den einzelnen Analyse-Services (Bild, Audio, Video).
    *   Services untereinander, z.B. wenn der Dossier-Service Informationen vom Personen-Service abruft.
*   **Konfiguration:** Jeder Breaker muss individuell konfiguriert werden (Fehlerschwellenwert, Timeout-Dauer, etc.), um den spezifischen Anforderungen und der erwarteten Stabilität des jeweiligen Dienstes gerecht zu werden.