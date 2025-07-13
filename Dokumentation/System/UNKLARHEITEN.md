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

### 1.3 Integration lokaler GPUs
- **Unklarheit**: Es fehlt eine Beschreibung, wie lokale GPUs in den Workflow integriert werden und wie das System zwischen lokalen und Cloud-GPUs entscheidet.
- **Vorgeschlagene Klärung**:
  - Entscheidungskriterien für die Auswahl zwischen lokalen und Cloud-GPUs
  - Prozess zur Registrierung und Verwaltung lokaler GPUs
  - Umgang mit unterschiedlichen Leistungsmerkmalen lokaler GPUs
  - Failover-Mechanismen bei Nichtverfügbarkeit lokaler Ressourcen

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