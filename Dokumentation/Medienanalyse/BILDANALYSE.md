# Verfahrensweise der Bildanalyse

Dieses Dokument beschreibt detailliert, wie das System mit Einzelbildern und Bildserien umgehen soll, um eine vollständige Analyse durchführen zu können.

## 1. Bildaufnahme und Validierung

### 1.1 Dateiannahme
- **Unterstützte Formate**: PNG, JPG, WEBP
- **Maximale Dateigröße**: 2 GB (für die gesamte Bildserie)
- **Validierungsprozess**:
  - Überprüfung des Dateiformats
  - Überprüfung der Dateigröße
  - Überprüfung der Bildintegrität (nicht beschädigt)
  - Validierung der Metadaten

### 1.2 Serienerkennung
- Automatische Erkennung zusammengehöriger Bilder basierend auf:
  - Zeitstempel in Metadaten
  - Dateinamen-Muster (z.B. img_001.jpg, img_002.jpg)
  - Visuelle Ähnlichkeit
- Option zur manuellen Gruppierung von Einzelbildern zu einer Serie

### 1.3 Duplikaterkennung
- Berechnung von Hashwerten für jedes Bild
- Abgleich mit der Datenbank bereits analysierter Bilder
- Bei Übereinstimmung: Information an den Benutzer mit Optionen:
  - Vorhandene Analyseergebnisse anzeigen
  - Erneute Analyse durchführen
  - Analyse abbrechen

## 2. Vorverarbeitung

### 2.1 Metadatenextraktion
- Auslesen von:
  - Bildauflösung
  - Farbtiefe
  - EXIF-Daten (falls vorhanden)
  - Erstellungsdatum und -zeit
  - Geolokalisierungsdaten (falls vorhanden)

### 2.2 Kostenberechnung
- Berechnung der voraussichtlichen Analysekosten basierend auf:
  - Anzahl der Bilder
  - Bildauflösung
  - Komplexität der Analyse
  - Aktuelle GPU-Preise der verfügbaren Anbieter
- Anzeige des Kostenvoranschlags an den Benutzer
- Einholung der Genehmigung vor Fortsetzung

### 2.3 Bildoptimierung
- Skalierung auf optimale Größe für die Analyse
- Normalisierung der Farbwerte
- Rauschunterdrückung (falls erforderlich)
- Kontrastverbesserung (falls erforderlich)

## 3. GPU-Ressourcenzuweisung

### 3.1 Ressourcenplanung
- Bestimmung der benötigten GPU-Ressourcen basierend auf:
  - Anzahl und Größe der Bilder
  - Komplexität der Analyse
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

## 4. Parallele Bildanalyse

### 4.1 Einzelbildanalyse
- **Personenerkennung**:
  - Identifikation von Personen im Bild
  - Extraktion von Gesichtsmerkmalen
  - Zuweisung temporärer IDs

- **Pose Estimation**:
  - Erkennung von Körperhaltungen
  - Identifikation von Posen, die auf Fesselung hindeuten
  - Analyse der Körpersprache für Verhaltensanalyse

- **Objekterkennung**:
  - Identifikation relevanter Objekte (z.B. Fesselungsmaterialien)
  - Klassifizierung nach Materialtyp (Seil, Klebeband, Metall, etc.)
  - Bestimmung der räumlichen Beziehung zwischen Objekten und Personen

- **Kleidungsanalyse**:
  - Klassifizierung des Kleidungsstils von `casual` bis `fetish`
  - Erkennung von Kleidungsfarben und -arten
  - Identifikation spezifischer Kleidungsstücke

- **Gesichtsanalyse**:
  - Erkennung von Emotionen
  - Analyse des Gesichtsausdrucks für Verhaltensanalyse
  - Extraktion von Merkmalen für die Personen-Re-Identifikation

### 4.2 Serienanalyse (bei mehreren Bildern)
- **Zeitliche Analyse**:
  - Erstellung einer chronologischen Abfolge
  - Erkennung von Veränderungen zwischen Bildern
  - Tracking von Personen und Objekten über mehrere Bilder

- **Kontextanalyse**:
  - Erkennung von Szenenänderungen
  - Identifikation von Handlungsabläufen
  - Bestimmung von Beziehungen zwischen Bildern

### 4.3 Checkpoint-Erstellung
- Regelmäßige Speicherung von Zwischenergebnissen (nach jedem analysierten Bild)
- Speicherung der Analyseergebnisse pro Modul
- Sicherung des Analysestatus für mögliche Wiederaufnahme

### 4.4 Fehlerbehandlung
- Kontinuierliche Überwachung des Analyseprozesses
- Bei Fehlern in einzelnen Modulen:
  - Protokollierung des Fehlers
  - Fortsetzung der Analyse mit den verbleibenden Modulen
  - Markierung der fehlgeschlagenen Analysen im Ergebnis

### 4.5 Abbruchmöglichkeit
- Bereitstellung einer Option zum Abbruch der laufenden Analyse
- Bei Abbruch:
  - Sofortiges Stoppen aller GPU-Prozesse
  - Speicherung der bis dahin generierten Teilergebnisse
  - Freigabe der GPU-Ressourcen

## 5. Datenfusion

### 5.1 Zusammenführung der Rohdaten
- Sammlung aller Analyseergebnisse aus den verschiedenen Modulen
- Bei Bildserien: Zusammenführung der Ergebnisse aller Einzelbilder
- Strukturierung der Daten für die LLM-Verarbeitung

### 5.2 LLM-Verarbeitung
- Übergabe der strukturierten Daten an die LLM-Instanz
- Anwendung eines spezifischen Prompts zur Datenfusion
- Generierung einer narrativen Zusammenfassung der Analyseergebnisse

### 5.3 Freiwilligkeitsbewertung
- Berechnung eines Freiwilligkeits-Scores (0-100%) basierend auf:
  - Ergebnissen der Pose Estimation
  - Emotionsanalyse aus Gesichtsausdrücken
  - Kontextuelle Interpretation durch das LLM
  - Bei Bildserien: Berücksichtigung der zeitlichen Entwicklung

## 6. Ergebnisaufbereitung

### 6.1 Dossier-Erstellung
- Zuweisung einer temporären Personen-ID
- Erstellung oder Aktualisierung des Personendossiers
- Chronologische Einordnung der Analyseergebnisse
- Bei Bildserien: Darstellung der zeitlichen Entwicklung

### 6.2 Visualisierung
- Generierung von Thumbnails mit markierten Erkennungen
- Bei Bildserien: Erstellung einer visuellen Zeitleiste
- Visualisierung des Freiwilligkeits-Scores
- Hervorhebung relevanter Objekte und Personen

### 6.3 Exportvorbereitung
- Aufbereitung der Daten für den Export in verschiedenen Formaten:
  - PDF (für Berichte)
  - JSON (für Rohdaten)
  - CSV (für tabellarische Daten)

## 7. Nachbearbeitung und Korrektur

### 7.1 Manuelle Überprüfung
- Anzeige der Analyseergebnisse zur Überprüfung
- Markierung von unsicheren Erkennungen
- Hervorhebung nicht erkannter Objekte

### 7.2 Manuelle Korrektur
- Möglichkeit zur Korrektur von:
  - Falsch erkannten Objekten
  - Ungenauer Personen-Identifikation
  - Fehlerhaften Klassifizierungen

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
- Löschung der ursprünglichen Bilddateien nach erfolgreicher Analyse
- Beibehaltung der Thumbnails für die Visualisierung

## 9. Metriken und Protokollierung

### 9.1 Leistungsmetriken
- Erfassung von:
  - Gesamtverarbeitungszeit
  - Verarbeitungszeit pro Bild
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