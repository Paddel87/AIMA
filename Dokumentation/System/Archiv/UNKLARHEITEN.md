# Unklarheiten und Klärungsbedarf

Dieses Dokument sammelt Unklarheiten in der Systemspezifikation und schlägt Klärungen vor.

## 1. Schnittstellen zwischen Workflow und GPU-Orchestrierung

### 1.1 Checkpoint-Mechanismus
- **Unklarheit**: In `MEDIENWORKFLOW.md` wird ein Checkpoint-Mechanismus erwähnt, aber es fehlt eine konkrete Beschreibung, wann und wie Checkpoints erstellt werden, welche Daten gespeichert werden und wie die Wiederaufnahme erfolgt.
- **Vorgeschlagene Klärung**: 
  - Definition der Checkpoint-Intervalle (zeitbasiert oder fortschrittsbasiert)
  - Spezifikation der zu speichernden Daten (Zwischenergebnisse, Modellzustand, etc.)
  - Beschreibung des Wiederaufnahmeprozesses nach einem Fehler
  - Speicherort und Format der Checkpoint-Daten

### 1.2 Kostenschätzung und Zeitpunkt
- **Unklarheit**: Es ist unklar, wann genau die Kostenschätzung erfolgt und wann die Benutzerabfrage zur Bestätigung stattfindet (vor der Einreihung oder unmittelbar vor der Ausführung).
- **Vorgeschlagene Klärung**:
  - Festlegung des genauen Zeitpunkts der Kostenschätzung im Workflow
  - Definition der Parameter für die Kostenschätzung (GPU-Typ, geschätzte Laufzeit, etc.)
  - Prozess bei Überschreitung eines Kostenbudgets
  - Umgang mit Abweichungen zwischen Schätzung und tatsächlichen Kosten


  

## 2. Technische Details

### 2.1 Metriken-Erfassung und -Bereitstellung
- **Unklarheit**: Es ist unklar, welche spezifischen GPU-Nutzungsmetriken erfasst werden, in welchem Format und wie sie bereitgestellt werden.
- **Vorgeschlagene Klärung**:
  - Liste der zu erfassenden Metriken (Auslastung, Temperatur, Speicherverbrauch, etc.)
  - Erfassungsintervall und Aggregationsmethoden
  - Speicherformat und Aufbewahrungsdauer
  - Schnittstellen für den Zugriff auf Metriken (API, Dashboard, etc.)

### 2.2 Prädiktive Skalierung
- **Unklarheit**: Der Algorithmus oder die Parameter für die prädiktive Skalierung sind nicht spezifiziert.
- **Vorgeschlagene Klärung**:
  - Definition des Vorhersagemodells (Zeitreihenanalyse, ML-basiert, etc.)
  - Eingabeparameter für die Vorhersage (historische Nutzung, Tageszeit, etc.)
  - Schwellenwerte für Skalierungsentscheidungen
  - Evaluierungsmethoden für die Vorhersagegenauigkeit

### 2.3 Abbruchverhalten
- **Unklarheit**: Es fehlen Details zum Verhalten bezüglich teilweise generierter Ergebnisse und deren Speicherung bei Benutzerabbruch des Analyseprozesses.
- **Vorgeschlagene Klärung**:
  - Definition des Verhaltens bei verschiedenen Abbruchszenarien (Benutzerabbruch, Systemfehler, etc.)
  - Spezifikation der zu speichernden Teilergebnisse
  - Prozess zur Wiederaufnahme oder Neustart nach Abbruch
  - Benachrichtigungsmechanismen bei Abbruch

## 3. Benutzerinteraktion

### 3.1 Fehlerbehandlung
- **Unklarheit**: Es ist unklar, wie Fehler während der Analyse behandelt werden und welche Optionen dem System und dem Benutzer zur Verfügung stehen.
- **Vorgeschlagene Klärung**:
  - Kategorisierung von Fehlertypen (kritisch, nicht-kritisch, etc.)
  - Automatische Reaktionen auf verschiedene Fehlertypen
  - Benutzerbenachrichtigungen und -optionen bei Fehlern
  - Protokollierung und Diagnose von Fehlern

### 3.2 Priorisierungsmechanismus
- **Unklarheit**: Es fehlen Details zum konzeptionellen Prozess der Benutzerprioritisierung der Warteschlange und dessen systemseitigen Auswirkungen.
- **Vorgeschlagene Klärung**:
  - Definition von Prioritätsstufen und deren Bedeutung
  - Berechtigungskonzept für Priorisierung (wer darf priorisieren)
  - Auswirkungen auf bereits eingereihte Jobs
  - Benachrichtigungsmechanismen bei Priorisierungsänderungen

## 4. Weitere Überlegungen

### 4.1 Ressourcenverteilung zwischen Analysetypen
- **Unklarheit**: Es ist unklar, wie GPU-Ressourcen zwischen verschiedenen Analysetypen (Video, Bild, Audio) verteilt werden, insbesondere bei parallelen GPU-Instanzen.
- **Vorgeschlagene Klärung**:
  - Ressourcenzuweisungsalgorithmus für verschiedene Analysetypen
  - Priorisierung bei Ressourcenknappheit
  - Möglichkeit zur Reservierung von Ressourcen für bestimmte Analysetypen
  - Dynamische Anpassung der Ressourcenverteilung basierend auf Auslastung

### 4.2 Anbieterübergreifende Optimierung
- **Unklarheit**: Es fehlen Details zur anbieterübergreifenden Optimierung, insbesondere hinsichtlich zeitabhängiger Preisunterschiede.
- **Vorgeschlagene Klärung**:
  - Algorithmus zur Auswahl des optimalen Anbieters zu einem bestimmten Zeitpunkt
  - Berücksichtigung von Preisvolatilität und Verfügbarkeit
  - Strategien für die Verteilung von Jobs über mehrere Anbieter
  - Failover-Mechanismen bei Nichtverfügbarkeit eines Anbieters

## 5. Datenbankarchitektur und -integration

### 5.1 Multi-Database-Transaktionen
- **Unklarheit**: Es ist unklar, wie ACID-Eigenschaften über PostgreSQL, MongoDB und Milvus hinweg gewährleistet werden.
- **Vorgeschlagene Klärung**:
  - Definition von Transaktionsgrenzen in der Multi-Database-Architektur
  - Implementierung von Saga-Pattern oder Two-Phase-Commit
  - Rollback-Strategien bei partiellen Fehlern
  - Konsistenz-Level-Definition für verschiedene Operationstypen

### 5.2 Cross-Database-Referenzen
- **Unklarheit**: Die Integrität von Referenzen zwischen verschiedenen Datenbanksystemen ist nicht spezifiziert.
- **Vorgeschlagene Klärung**:
  - Mechanismen zur Aufrechterhaltung referenzieller Integrität
  - Umgang mit "dangling references" bei Löschoperationen
  - Synchronisation von Primärschlüsseln zwischen Systemen
  - Validierungsstrategien für Cross-Database-Konsistenz

### 5.3 Vektorindex-Versionierung
- **Unklarheit**: Der Umgang mit Modell-Updates und bestehenden Einbettungen ist nicht definiert.
- **Vorgeschlagene Klärung**:
  - Migrationsstrategie bei Modell-Updates
  - Versionierung von Einbettungen und Backward-Kompatibilität
  - Re-Indexierung-Strategien für große Datenmengen
  - A/B-Testing mit verschiedenen Einbettungsmodellen

## 6. Datenfusion-Algorithmen und -Kalibrierung

### 6.1 Adaptive Gewichtung
- **Unklarheit**: Die konkreten Algorithmen für die dynamische Anpassung der Fusion-Gewichte sind nicht spezifiziert.
- **Vorgeschlagene Klärung**:
  - Mathematische Formulierung der Gewichtungsalgorithmen
  - Lernverfahren für optimale Gewichtungsparameter
  - Validierungsmetriken für Fusion-Qualität
  - Fallback-Strategien bei unzureichender Datenqualität

### 6.2 Konfidenz-Kalibrierung
- **Unklarheit**: Es fehlt eine Beschreibung, wie Konfidenzwerte verschiedener Modelle vergleichbar gemacht werden.
- **Vorgeschlagene Klärung**:
  - Kalibrierungsverfahren für modellspezifische Konfidenzwerte
  - Normalisierung von Konfidenzskalen
  - Unsicherheitsquantifizierung in der Fusion
  - Qualitätsmetriken für kalibrierte Konfidenzwerte

### 6.3 Temporal Fusion
- **Unklarheit**: Die Behandlung von zeitlichen Inkonsistenzen zwischen Modalitäten ist nicht definiert.
- **Vorgeschlagene Klärung**:
  - Synchronisationsstrategien für multimodale Zeitstempel
  - Interpolationsverfahren bei fehlenden Zeitpunkten
  - Gewichtung zeitlich versetzter Informationen
  - Erkennung und Behandlung von Timing-Anomalien

## 7. Microservices-Kommunikation und -Orchestrierung

### 7.1 Service-Discovery
- **Unklarheit**: Der Mechanismus für dynamische Service-Registrierung und -Erkennung ist nicht spezifiziert.
- **Vorgeschlagene Klärung**:
  - Service-Registry-Implementierung (Consul, etcd, etc.)
  - Health-Check-Mechanismen für Services
  - Load-Balancing-Strategien zwischen Service-Instanzen
  - Graceful Shutdown und Service-Deregistrierung

### 7.2 Event-Ordering und -Konsistenz
- **Unklarheit**: Reihenfolge-Garantien bei asynchroner Event-Verarbeitung sind nicht definiert.
- **Vorgeschlagene Klärung**:
  - Event-Ordering-Strategien (Partitionierung, Sequenznummern)
  - Eventual Consistency vs. Strong Consistency Anforderungen
  - Duplicate Event Detection und Idempotenz
  - Event-Replay-Mechanismen bei Fehlern

### 7.3 Circuit Breaker und Resilience
- **Unklarheit**: Fehlerbehandlung bei Ausfall kritischer Module ist nicht spezifiziert.
- **Vorgeschlagene Klärung**:
  - Circuit Breaker Pattern Implementierung
  - Timeout-Konfigurationen für Service-Calls
  - Bulkhead Pattern für Ressourcenisolation
  - Graceful Degradation Strategien

## 8. Sicherheit und Compliance

### 8.1 End-to-End-Verschlüsselung
- **Unklarheit**: Das Schlüsselmanagement über alle Systemkomponenten ist nicht definiert.
- **Vorgeschlagene Klärung**:
  - Key Management Service (KMS) Architektur
  - Schlüsselrotation und -versionierung
  - Verschlüsselung in Transit und at Rest
  - Hardware Security Module (HSM) Integration

### 8.2 GDPR-Compliance
- **Unklarheit**: Die Implementierung von Löschungsrechten in verteilter Architektur ist nicht spezifiziert.
- **Vorgeschlagene Klärung**:
  - "Right to be forgotten" Implementierung über alle Datenbanken
  - Pseudonymisierung und Anonymisierung von Personendaten
  - Data Lineage Tracking für Compliance-Audits
  - Consent Management über alle Services

### 8.3 Audit-Trail
- **Unklarheit**: Vollständige Nachverfolgbarkeit über alle Microservices ist nicht gewährleistet.
- **Vorgeschlagene Klärung**:
  - Distributed Tracing Implementierung
  - Correlation IDs für Request-Verfolgung
  - Immutable Audit Logs
  - Compliance Reporting und Dashboards

## 9. Performance und Skalierung

### 9.1 Speicher-Overhead Management
- **Unklarheit**: Das Management der geschätzten 400MB täglichen Metadaten ist nicht optimiert.
- **Vorgeschlagene Klärung**:
  - Datenarchivierung und -komprimierung Strategien
  - Hot/Cold Storage Tiering
  - Metadaten-Aggregation und -Summarization
  - Speicher-Monitoring und -Alerting

### 9.2 Auto-Scaling Strategien
- **Unklarheit**: Skalierungsstrategien für verschiedene Systemkomponenten sind nicht definiert.
- **Vorgeschlagene Klärung**:
  - Horizontal vs. Vertical Scaling Entscheidungskriterien
  - Predictive Scaling basierend auf historischen Daten
  - Resource Quotas und Limits
  - Cost-aware Scaling Policies

## 10. Monitoring und Observability

### 10.1 Distributed Monitoring
- **Unklarheit**: Monitoring-Strategien für die verteilte Architektur sind nicht vollständig spezifiziert.
- **Vorgeschlagene Klärung**:
  - Service Mesh Observability (Istio, Linkerd)
  - Custom Metrics Definition und Collection
  - Alerting Rules und Escalation Policies
  - Performance Baseline Definition

### 10.2 Log Aggregation
- **Unklarheit**: Zentrale Log-Sammlung und -Analyse über alle Services ist nicht definiert.
- **Vorgeschlagene Klärung**:
  - ELK Stack oder ähnliche Log-Pipeline
  - Structured Logging Standards
  - Log Retention Policies
  - Real-time Log Analysis und Anomaly Detection