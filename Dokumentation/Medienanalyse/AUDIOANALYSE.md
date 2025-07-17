# Verfahrensweise der Audioanalyse

Dieses Dokument beschreibt detailliert, wie das System mit Audiodateien umgehen soll, um eine vollständige Analyse durchführen zu können.

## 1. Audioaufnahme und Validierung

### 1.1 Dateiannahme
- **Unterstützte Formate**: Audioextraktionen aus Videodateien (MP4, MOV, AVI)
- **Maximale Dateigröße**: Entsprechend der Videodateigröße (max. 2 GB)
- **Validierungsprozess**:
  - Überprüfung des Audiocodecs auf Kompatibilität
  - Überprüfung der Audiointegrität (nicht beschädigt)
  - Validierung der Audioqualität (Rauschpegel, Verständlichkeit)

### 1.2 Duplikaterkennung
- Berechnung eines akustischen Fingerabdrucks der Audiodatei
- Abgleich mit der Datenbank bereits analysierter Audiodaten
- Bei Übereinstimmung: Information an den Benutzer mit Optionen:
  - Vorhandene Analyseergebnisse anzeigen
  - Erneute Analyse durchführen
  - Analyse abbrechen

## 2. Vorverarbeitung

### 2.1 Metadatenextraktion
- Auslesen von:
  - Audiodauer
  - Samplerate
  - Bitrate
  - Anzahl der Kanäle
  - Audiocodec

### 2.2 Kostenberechnung
- Berechnung der voraussichtlichen Analysekosten basierend auf:
  - Audiodauer
  - Komplexität der Analyse
  - Aktuelle GPU-Preise der verfügbaren Anbieter
- Anzeige des Kostenvoranschlags an den Benutzer
- Einholung der Genehmigung vor Fortsetzung

### 2.3 Audiooptimierung
- Konvertierung in ein einheitliches Format für die Analyse
- Rauschunterdrückung
- Normalisierung der Lautstärke
- Kanaltrennung (bei Stereo oder Mehrkanal)
- Segmentierung in analysierbare Abschnitte

## 3. GPU-Ressourcenzuweisung

### 3.1 Ressourcenplanung
- Bestimmung der benötigten GPU-Ressourcen basierend auf:
  - Audiodauer
  - Komplexität der Analyse
  - Verfügbare GPU-Instanzen
  - Aktuelle Auslastung des Systems

### 3.2 Instanzauswahl
- Abfrage der verfügbaren GPU-Instanzen bei allen konfigurierten Anbietern
- Auswahl der optimalen Instanz basierend auf:
  - Erforderlicher VRAM (mindestens 16 GB)
  - Kosten-Nutzen-Verhältnis
  - Verfügbarkeit


### 3.3 Jobeinreihung
- Einreihung des Analysejobs in die Warteschlange
- Anzeige der aktuellen Position in der Warteschlange
- Option zur manuellen Priorisierung durch den Benutzer

## 4. Audioanalyse

### 4.1 Spracherkennung und Transkription
- **Sprachidentifikation**:
  - Erkennung der gesprochenen Sprache(n)
  - Unterstützung für Englisch, Chinesisch und Japanisch

- **Sprachtranskription**:
  - Umwandlung von Sprache in Text
  - Zeitstempelung der Transkription
  - Sprecherzuordnung (falls mehrere Sprecher)

- **Übersetzung**:
  - Bei Bedarf Übersetzung in die Systemsprache
  - Beibehaltung der Originaltranskription

### 4.2 Emotionsanalyse
- **Stimmlagenanalyse**:
  - Erkennung von Tonhöhe und -variation
  - Analyse der Sprechgeschwindigkeit
  - Identifikation von Betonungsmustern

- **Emotionserkennung**:
  - Klassifizierung von Emotionen (Angst, Stress, Freude, etc.)
  - Erkennung von emotionalen Veränderungen im Zeitverlauf
  - Bewertung der emotionalen Intensität

### 4.3 Nicht-sprachliche Audioanalyse
- **Geräuscherkennung**:
  - Identifikation von Hintergrundgeräuschen
  - Erkennung von Schreien, Weinen oder anderen relevanten Lauten
  - Klassifizierung von Umgebungsgeräuschen

- **Stille-/Pausenerkennung**:
  - Identifikation von Sprechpausen
  - Analyse der Pausenmuster
  - Erkennung von unnatürlichen Unterbrechungen

### 4.4 Schlüsselwortanalyse
- **Lexikalische Analyse**:
  - Identifikation relevanter Schlüsselwörter (z.B. "Hilfe", "Stopp")
  - Kontextuelle Einordnung der Schlüsselwörter
  - Häufigkeitsanalyse bestimmter Wortgruppen

- **Semantische Analyse**:
  - Bestimmung der Bedeutung und Intention
  - Erkennung von impliziten Hilfeersuchen
  - Analyse von Gesprächsmustern

### 4.5 Checkpoint-Erstellung
- Regelmäßige Speicherung von Zwischenergebnissen (alle 30 Sekunden Audiomaterial)
- Speicherung der Analyseergebnisse pro Modul
- Sicherung des Analysestatus für mögliche Wiederaufnahme

### 4.6 Fehlerbehandlung
- Kontinuierliche Überwachung des Analyseprozesses
- Bei Fehlern in einzelnen Modulen:
  - Protokollierung des Fehlers
  - Fortsetzung der Analyse mit den verbleibenden Modulen
  - Markierung der fehlgeschlagenen Abschnitte im Ergebnis

### 4.7 Abbruchmöglichkeit
- Bereitstellung einer Option zum Abbruch der laufenden Analyse
- Bei Abbruch:
  - Sofortiges Stoppen aller GPU-Prozesse
  - Speicherung der bis dahin generierten Teilergebnisse
  - Freigabe der GPU-Ressourcen

## 5. Datenfusion

### 5.1 Zusammenführung der Rohdaten
- Sammlung aller Analyseergebnisse aus den verschiedenen Modulen
- Zeitliche Synchronisation der Ergebnisse
- Strukturierung der Daten für die LLM-Verarbeitung

### 5.2 LLM-Verarbeitung
- Übergabe der strukturierten Daten an die LLM-Instanz
- Anwendung eines spezifischen Prompts zur Datenfusion
- Generierung einer narrativen Zusammenfassung der Analyseergebnisse

### 5.3 Freiwilligkeitsbewertung
- Beitrag zur Berechnung eines Freiwilligkeits-Scores (0-100%) basierend auf:
  - Emotionsanalyse aus der Stimme
  - Identifizierten Schlüsselwörtern in der Transkription
  - Kontextuelle Interpretation durch das LLM

## 6. Ergebnisaufbereitung

### 6.1 Dossier-Integration
- Integration der Audioanalyseergebnisse in das Personendossier
- Verknüpfung mit zugehörigen Video- oder Bildanalysen
- Chronologische Einordnung der Analyseergebnisse

### 6.2 Visualisierung
- Generierung von Audiowellenformen mit markierten Ereignissen
- Erstellung einer interaktiven Zeitleiste der Transkription
- Visualisierung der erkannten Emotionen im Zeitverlauf
- Hervorhebung relevanter Schlüsselwörter und Phrasen

### 6.3 Exportvorbereitung
- Aufbereitung der Daten für den Export in verschiedenen Formaten:
  - PDF (für Berichte)
  - JSON (für Rohdaten)
  - CSV (für tabellarische Daten)
  - TXT (für reine Transkriptionen)

## 7. Nachbearbeitung und Korrektur

### 7.1 Manuelle Überprüfung
- Anzeige der Transkription zur Überprüfung
- Markierung von unsicheren Erkennungen
- Hervorhebung von potenziell relevanten Abschnitten

### 7.2 Manuelle Korrektur
- Möglichkeit zur Korrektur von:
  - Fehlerhaften Transkriptionen
  - Ungenauer Sprecherzuordnung
  - Fehlerhaften Emotionsklassifizierungen

### 7.3 Sprecherzuordnung
- Vorschläge zur Zuordnung von Sprechern zu Personendossiers
- Option zur manuellen Bestätigung oder Ablehnung
- Bei Zuordnung: Integration in die entsprechenden Dossiers

## 8. Abschluss und Bereinigung

### 8.1 Ergebnisspeicherung
- Dauerhafte Speicherung der Analyseergebnisse in der Datenbank
- Verknüpfung mit dem entsprechenden Personendossier
- Indexierung für schnellen Zugriff

### 8.2 Ressourcenfreigabe
- Freigabe der GPU-Ressourcen nach Abschluss der Analyse
- Anwendung der Shutdown-Policy für nicht mehr benötigte Instanzen

### 8.3 Dateilöschung
- Löschung der ursprünglichen Audiodatei nach erfolgreicher Analyse
- Beibehaltung der Transkription und Analyseergebnisse

## 9. Metriken und Protokollierung

### 9.1 Leistungsmetriken
- Erfassung von:
  - Gesamtverarbeitungszeit
  - Word Error Rate (WER) der Transkription
  - GPU-Auslastung während der Analyse
  - Genauigkeit der verschiedenen Analysemodule

### 9.2 Kostenerfassung
- Berechnung der tatsächlichen Kosten nach Abschluss
- Vergleich mit dem ursprünglichen Kostenvoranschlag
- Speicherung für zukünftige Kostenoptimierungen

### 9.3 Fehlerprotokollierung
- Detaillierte Protokollierung aller aufgetretenen Fehler
- Kategorisierung nach Fehlertyp und Schweregrad
- Speicherung für Systemverbesserungen