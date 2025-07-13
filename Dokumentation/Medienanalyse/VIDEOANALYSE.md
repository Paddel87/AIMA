# Verfahrensweise der Videoanalyse

Dieses Dokument beschreibt detailliert, wie das System mit einer Videodatei umgehen soll, um eine vollständige Analyse durchführen zu können.

## 1. Videoaufnahme und Validierung

### 1.1 Dateiannahme
- **Unterstützte Formate**: MP4, MOV, AVI
- **Maximale Dateigröße**: 2 GB
- **Validierungsprozess**:
  - Überprüfung des Dateiformats
  - Überprüfung der Dateigröße
  - Überprüfung der Videocodecs auf Kompatibilität
  - Überprüfung der Videointegrität (nicht beschädigt)

### 1.2 Duplikaterkennung
- Berechnung eines Hashwerts der Videodatei
- Abgleich mit der Datenbank bereits analysierter Videos
- Bei Übereinstimmung: Information an den Benutzer mit Optionen:
  - Vorhandene Analyseergebnisse anzeigen
  - Erneute Analyse durchführen
  - Analyse abbrechen

## 2. Vorverarbeitung

### 2.1 Metadatenextraktion
- Auslesen von:
  - Videolänge
  - Auflösung
  - Framerate
  - Audiokanäle
  - Erstellungsdatum (falls in Metadaten vorhanden)

### 2.2 Kostenberechnung
- Berechnung der voraussichtlichen Analysekosten basierend auf:
  - Videolänge
  - Auflösung
  - Aktuelle GPU-Preise der verfügbaren Anbieter
- Anzeige des Kostenvoranschlags an den Benutzer
- Einholung der Genehmigung vor Fortsetzung

### 2.3 Aufbereitung
- Temporäre Speicherung der Videodatei im Arbeitsspeicher
- Aufteilung in Video- und Audiospur
- Erstellung von Keyframes für die Bildanalyse
- Optimierung der Audiodaten für die Spracherkennung

## 3. GPU-Ressourcenzuweisung

### 3.1 Ressourcenplanung
- Bestimmung der benötigten GPU-Ressourcen basierend auf:
  - Videolänge und Komplexität
  - Verfügbare GPU-Instanzen
  - Aktuelle Auslastung des Systems

### 3.2 Instanzauswahl
- Abfrage der verfügbaren GPU-Instanzen bei allen konfigurierten Anbietern
- Auswahl der optimalen Instanz basierend auf:
  - Erforderlicher VRAM (mindestens 16 GB)
  - Kosten-Nutzen-Verhältnis
  - Verfügbarkeit
- Bei lokaler GPU-Verfügbarkeit: Option zur Nutzung der lokalen Ressourcen

### 3.3 Jobeinreihung
- Einreihung des Analysejobs in die Warteschlange
- Anzeige der aktuellen Position in der Warteschlange
- Option zur manuellen Priorisierung durch den Benutzer

## 4. Parallele Videoanalyse

### 4.1 Videostream-Analyse
- **Personen-Tracking**:
  - Identifikation und Verfolgung von Personen über Frames hinweg
  - Zuweisung temporärer IDs
  - Extraktion von Gesichtsmerkmalen für Re-Identifikation

- **Pose Estimation**:
  - Erkennung von Körperhaltungen in jedem Frame
  - Identifikation von Posen, die auf Fesselung hindeuten
  - Analyse der Körpersprache für Verhaltensanalyse

- **Objekterkennung**:
  - Identifikation relevanter Objekte (z.B. Fesselungsmaterialien)
  - Klassifizierung nach Materialtyp (Seil, Klebeband, Metall, etc.)
  - Tracking der Objekte über Frames hinweg

- **Kleidungsanalyse**:
  - Klassifizierung des Kleidungsstils von `casual` bis `fetish`
  - Erkennung von Kleidungsfarben und -arten
  - Identifikation von Kleidungsänderungen im Zeitverlauf

- **Gesichtsanalyse**:
  - Erkennung von Emotionen
  - Analyse des Gesichtsausdrucks für Verhaltensanalyse
  - Extraktion von Merkmalen für die Personen-Re-Identifikation

### 4.2 Audiostream-Analyse
- **Spracherkennung**:
  - Transkription gesprochener Inhalte
  - Sprachidentifikation und ggf. Übersetzung
  - Extraktion von Schlüsselwörtern

- **Emotionsanalyse**:
  - Analyse der Stimmlage und Betonung
  - Erkennung von emotionalen Zuständen (Angst, Stress, etc.)
  - Identifikation von nicht-sprachlichen Lauten (Weinen, Schreien, etc.)

### 4.3 Checkpoint-Erstellung
- Regelmäßige Speicherung von Zwischenergebnissen (alle 30 Sekunden Videomaterial)
- Speicherung der Analyseergebnisse pro Modul
- Sicherung des Analysestatus für mögliche Wiederaufnahme

### 4.4 Fehlerbehandlung
- Kontinuierliche Überwachung des Analyseprozesses
- Bei Fehlern in einzelnen Modulen:
  - Protokollierung des Fehlers
  - Fortsetzung der Analyse mit den verbleibenden Modulen
  - Markierung der fehlgeschlagenen Abschnitte im Ergebnis

### 4.5 Abbruchmöglichkeit
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
- Berechnung eines Freiwilligkeits-Scores (0-100%) basierend auf:
  - Ergebnissen der Pose Estimation
  - Emotionsanalyse aus Gesicht und Stimme
  - Identifizierten Schlüsselwörtern in der Transkription
  - Kontextuelle Interpretation durch das LLM

## 6. Ergebnisaufbereitung

### 6.1 Dossier-Erstellung
- Zuweisung einer temporären Personen-ID
- Erstellung oder Aktualisierung des Personendossiers
- Chronologische Einordnung der Analyseergebnisse

### 6.2 Visualisierung
- Generierung von Thumbnails mit markierten Erkennungen
- Erstellung einer interaktiven Zeitleiste der Ereignisse
- Visualisierung des Freiwilligkeits-Scores

### 6.3 Exportvorbereitung
- Aufbereitung der Daten für den Export in verschiedenen Formaten:
  - PDF (für Berichte)
  - JSON (für Rohdaten)
  - CSV (für tabellarische Daten)

## 7. Nachbearbeitung und Korrektur

### 7.1 Manuelle Überprüfung
- Anzeige der Analyseergebnisse zur Überprüfung
- Markierung von unsicheren Erkennungen
- Hervorhebung nicht erkannter Objekte auf Thumbnails

### 7.2 Manuelle Korrektur
- Möglichkeit zur Korrektur von:
  - Falsch erkannten Objekten
  - Fehlerhaften Transkriptionen
  - Ungenauer Personen-Identifikation

### 7.3 Personen-Re-Identifikation
- Vorschläge zur Zusammenführung von Personendossiers
- Option zur manuellen Bestätigung oder Ablehnung
- Bei Zusammenführung: Konsolidierung der Zeitlinien

## 8. Abschluss und Bereinigung

### 8.1 Ergebnisspeicherung
- Dauerhafte Speicherung der Analyseergebnisse in der Datenbank
- Verknüpfung mit dem entsprechenden Personendossier
- Indexierung für schnellen Zugriff

### 8.2 Ressourcenfreigabe
- Freigabe der GPU-Ressourcen nach Abschluss der Analyse
- Anwendung der Shutdown-Policy für nicht mehr benötigte Instanzen

### 8.3 Dateilöschung
- Löschung der ursprünglichen Videodatei nach erfolgreicher Analyse
- Beibehaltung der generierten Thumbnails für die Visualisierung

## 9. Metriken und Protokollierung

### 9.1 Leistungsmetriken
- Erfassung von:
  - Gesamtverarbeitungszeit
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