# Medienworkflow

Dieses Dokument beschreibt den Workflow für die Analyse von Medien (Bilder, Videos, Audio) im AIMA-System. Es definiert den Prozess von der Medienaufnahme bis zur Erstellung des Analysedossiers.

## 1. Upload und Vorverarbeitung

### 1.1 Medientyperkennung
- Das System erkennt automatisch den Typ des hochgeladenen Mediums (Bild, Video, Audio)
- Basierend auf dem Medientyp wird der entsprechende Analysepfad ausgewählt
- Nicht unterstützte Formate werden abgelehnt mit entsprechender Fehlermeldung

### 1.2 Duplikaterkennung
- Prüfung auf bereits analysierte identische Medien mittels Hashwert-Vergleich
- Bei Duplikaten wird der Benutzer informiert und kann wählen:
  - Vorhandene Analyseergebnisse verwenden
  - Neue Analyse durchführen
  - Analyse abbrechen

### 1.3 Job-Einreihung
- Erstellung eines Analysejobs mit eindeutiger ID
- Einreihung in die Warteschlange nach Priorität
- Schätzung der Analysekosten und -dauer
- Optional: Benutzerabfrage zur Bestätigung vor Ausführung

### 1.4 Priorisierung
- Standard: First-In-First-Out (FIFO)
- Benutzer mit höherer Priorität können die Warteschlange überspringen
- Notfallanalysen können mit höchster Priorität eingereiht werden
- Ressourcenintensive Analysen können in Nebenzeiten verschoben werden

## 2. Parallele Analyse auf GPU-Instanzen

### 2.1 Videoanalyse
- Aufteilung in parallele Analysepfade:
  - Videostream-Analyse (Personen, Posen, Objekte, Kleidung, Gesichter)
  - Audiostream-Analyse (Spracherkennung, Emotionsanalyse)
- Regelmäßige Checkpoints zur Fortschrittssicherung
- Detaillierte Beschreibung siehe [VIDEOANALYSE_VERFAHREN.md](VIDEOANALYSE_VERFAHREN.md)

### 2.2 Bildanalyse
- Einzelbildanalyse für alleinstehende Bilder
- Serienanalyse für zusammengehörige Bildserien
- Kontextuelle Analyse bei mehreren Bildern
- Detaillierte Beschreibung siehe [BILDANALYSE_VERFAHREN.md](BILDANALYSE_VERFAHREN.md)

### 2.3 Audioanalyse
- Spracherkennung und Transkription
- Emotionsanalyse der Stimme
- Nicht-linguistische Audioanalyse (Hintergrundgeräusche, etc.)
- Detaillierte Beschreibung siehe [AUDIOANALYSE_VERFAHREN.md](AUDIOANALYSE_VERFAHREN.md)

### 2.4 Fehlerbehandlung
- Automatische Wiederholungsversuche bei temporären Fehlern
- Degradation auf weniger ressourcenintensive Modelle bei Ressourcenmangel
- Benachrichtigung des Benutzers bei kritischen Fehlern
- Speicherung von Teilergebnissen bei Abbruch

### 2.5 Abbruchmöglichkeiten
- Benutzer kann Analyse jederzeit abbrechen
- System kann Analyse bei kritischen Fehlern automatisch abbrechen
- Bei Abbruch werden alle bisher generierten Ergebnisse gespeichert
- Ressourcen werden sofort freigegeben

## 3. Datenfusion und Dossiererstellung

### 3.1 LLM-basierte Datenfusion
- Zusammenführung aller Analyseergebnisse durch LLM
- Erstellung eines kohärenten Narrativs aus den Einzelanalysen
- Identifikation von Widersprüchen und Unsicherheiten
- Bewertung der Freiwilligkeit und des Kontexts

### 3.2 Temporäre Personen-ID-Zuweisung
- Zuweisung eindeutiger IDs zu erkannten Personen
- Verknüpfung derselben Person über verschiedene Medien hinweg
- Möglichkeit zur manuellen Korrektur der Zuordnungen
- Speicherung der Zuordnungen für zukünftige Analysen

### 3.3 Dossierspeicherung
- Speicherung des Dossiers in der Datenbank
- Verknüpfung mit dem ursprünglichen Medium
- Versionierung bei wiederholten Analysen
- Exportmöglichkeiten in verschiedene Formate (PDF, JSON, etc.)

## 4. Nachbearbeitung und Korrektur

### 4.1 Manuelle Korrektur
- Benutzeroberfläche zur Korrektur nicht erkannter Elemente
- Möglichkeit zur Anpassung der automatischen Zuordnungen
- Hinzufügen von manuellen Anmerkungen und Kontextinformationen
- Neuberechnung der Analyse mit manuellen Korrekturen

### 4.2 Feedback-Schleife
- Sammlung von Benutzerkorrekturen zur Modellverbesserung
- Periodisches Training der Modelle mit korrigierten Daten
- Kontinuierliche Verbesserung der Erkennungsgenauigkeit
- A/B-Tests neuer Modellversionen

## 5. Abschluss und Bereinigung

### 5.1 Ergebnisbereitstellung
- Benachrichtigung des Benutzers über abgeschlossene Analyse
- Bereitstellung des Dossiers über die Benutzeroberfläche
- Optionale E-Mail-Benachrichtigung mit Zusammenfassung
- Exportmöglichkeiten für externe Verwendung

### 5.2 Ressourcenfreigabe
- Sofortige Freigabe der GPU-Ressourcen nach Abschluss
- Löschung temporärer Dateien und Zwischenergebnisse
- Aktualisierung der Nutzungsstatistiken
- Vorbereitung der Ressourcen für den nächsten Job

### 5.3 Langzeitarchivierung
- Optional: Archivierung der Analyseergebnisse für langfristige Speicherung
- Komprimierung und Verschlüsselung der archivierten Daten
- Definierte Aufbewahrungsfristen je nach Anwendungsfall
- Automatische Löschung nach Ablauf der Aufbewahrungsfrist