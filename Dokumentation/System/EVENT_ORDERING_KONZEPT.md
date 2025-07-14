# Sicherstellung der Event-Reihenfolge (Event Ordering)

## 1. Problemstellung: Datenkonsistenz in asynchronen Systemen

In der ereignisgesteuerten Architektur von AIMA kommunizieren Microservices lose gekoppelt über einen Message Broker. Ein zentraler Anwendungsfall ist die Verarbeitung von Änderungen an einer bestimmten Geschäfts-Entität, z.B. einem `MediaItem`.

Ein typischer Lebenszyklus erzeugt eine Reihe von Events:
1.  `MediaItemCreated` (ID: media-123)
2.  `MediaItemMetadataUpdated` (ID: media-123, Titel hinzugefügt)
3.  `AnalysisStarted` (ID: media-123)
4.  `AnalysisCompleted` (ID: media-123)
5.  `MediaItemDeleted` (ID: media-123)

Die korrekte Verarbeitung dieser Events ist von ihrer Reihenfolge abhängig. In einem verteilten System gibt es jedoch keine inhärente Garantie, dass die Events in der Reihenfolge verarbeitet werden, in der sie gesendet wurden. Netzwerklatenz, Broker-Interna, konkurrierende Consumer oder Fehlerbehandlungs-Mechanismen (wie Retries) können dazu führen, dass die Reihenfolge bei der Verarbeitung durcheinandergerät. Dies kann zu schweren Konsistenzproblemen und Fehlern führen (z.B. der Versuch, ein bereits gelöschtes Medium zu analysieren).

## 2. Lösungsansatz: Partitionierte Verarbeitung mit Apache Kafka

Um eine strikte Reihenfolgen-Garantie (*strict ordering*) für zusammengehörige Events zu gewährleisten, wird der Einsatz von **Apache Kafka** als Message Broker in Kombination mit dem **Partition-Key-Muster** als verbindlich festgelegt.

### 2.1. Technologische Wahl: Apache Kafka

Während generische Message Broker wie RabbitMQ viele Messaging-Muster unterstützen, ist Kafka speziell für den Aufbau von hochperformanten, unveränderlichen Event-Streams optimiert. Seine Architektur basiert auf dem Konzept eines verteilten, partitionierten Commit-Logs, was es zur idealen Wahl für Anwendungsfälle macht, die eine garantierte Reihenfolge erfordern.

### 2.2. Das Partition-Key-Muster

Das Prinzip ist wie folgt:

1.  **Definition des Schlüssels:** Für jede Gruppe von Events, deren Reihenfolge kritisch ist, wird ein gemeinsamer Schlüssel definiert. Im Falle von AIMA ist dies für alle medienbezogenen Prozesse die **`media_id`**.

2.  **Produzenten-Logik (Producer):** Wenn ein Microservice ein Event produziert (z.B. `MediaItemMetadataUpdated`), sendet er es nicht nur an ein Kafka-Topic (z.B. `media-events`), sondern versieht es explizit mit dem Partition Key, in diesem Fall der `media_id` des betroffenen Mediums.

3.  **Kafka-Broker-Garantie:** Kafka garantiert, dass alle Nachrichten, die mit demselben Partition Key an ein Topic gesendet werden, **immer in derselben Partition** landen. Eine Partition ist eine geordnete, unveränderliche Sequenz von Nachrichten (ein Log).

4.  **Konsumenten-Logik (Consumer):** Kafka garantiert, dass ein Consumer (bzw. eine Consumer-Instanz innerhalb einer Consumer-Group) die Nachrichten **innerhalb einer einzelnen Partition strikt in der Reihenfolge liest**, in der sie geschrieben wurden.

### 2.3. Konsequenzen für die Architektur

-   **Garantierte Reihenfolge pro Entität:** Durch die Verwendung der `media_id` als Partition Key wird sichergestellt, dass alle Events für ein spezifisches Medium (Created, Updated, Deleted etc.) wie an einer Perlenkette aufgereiht und nacheinander verarbeitet werden. Die Reihenfolge bleibt gewahrt.
-   **Parallele Verarbeitung und Skalierbarkeit:** Events, die unterschiedliche Medien betreffen (und somit unterschiedliche Partition Keys haben), werden von Kafka auf verschiedene Partitionen verteilt. Diese Partitionen können von unterschiedlichen Consumer-Instanzen parallel verarbeitet werden. Das System kann also horizontal skalieren, ohne die Reihenfolgen-Garantie pro Medium zu verletzen.
-   **Zustandsbehaftete Services:** Dieses Muster ist die Grundlage für zustandsbehaftete Microservices, die den Zustand einer Entität (z.B. eines `MediaItem`) aus dem Event-Stream rekonstruieren und konsistent halten können.

## 3. Implementierungsrichtlinie

Für alle asynchronen Prozesse in AIMA, bei denen die Reihenfolge der Operationen für eine bestimmte Entität (z.B. `MediaItem`, `Dossier`, `User`) von Bedeutung ist, ist die Verwendung von Apache Kafka mit einem entsprechenden Partition Key (z.B. `media_id`, `dossier_id`, `user_id`) obligatorisch.