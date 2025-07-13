# Anwendungsszenario aus Benutzersicht

Dieses Dokument beschreibt ein typisches Anwendungsszenario des AIMA-Systems aus der Perspektive eines Benutzers, von der Medienaufnahme bis zur Ergebnisdarstellung.

## 1. Medienupload

### 1.1 Upload-Prozess

- Der Benutzer greift über eine benutzerfreundliche Weboberfläche auf das AIMA-System zu
- Der Upload von Mediendateien erfolgt wahlweise durch:
  - Auswahl eines lokalen Verzeichnisses über den Datei-Browser
  - Drag & Drop von Dateien oder Ordnern direkt in die Benutzeroberfläche
- Während des Uploads werden folgende Informationen in Echtzeit angezeigt:
  - Größe jeder einzelnen Datei
  - Gesamtspeichermenge aller hochgeladenen Dateien
  - Verbleibende Übertragungszeit (dynamisch berechnet)
  - Aktuelle Uploadgeschwindigkeit in MB/s
  - Fortschrittsbalken für den Gesamtfortschritt

### 1.2 Job-Erstellung und Identifikation

- Nach Abschluss des Uploads werden die Mediendateien automatisch verarbeitet:
  - Einzelne Videodateien erhalten eine eindeutige Job-ID
  - Bei Bulk-Upload mehrerer Videos in einem Ordner:
    - Alle Videos erhalten eine gemeinsame übergeordnete Job-ID
    - Jede einzelne Datei erhält zusätzlich eine individuelle Unter-ID
    - Die Unter-ID ist mit der übergeordneten Job-ID verknüpft
  - Gleiches Verfahren gilt für Bilder und Bilderserien
- Das System generiert automatisch Vorschaubilder aus den hochgeladenen Videodateien
- Die Jobs werden in einer übersichtlichen Liste mit Vorschaubildern präsentiert

### 1.3 Kontextuelle Eingaben

- Der Benutzer kann einen Job aus der Liste auswählen, um weitere Details einzusehen:
  - Zusätzliche Vorschaubilder werden angezeigt
  - Metadaten der Mediendateien werden dargestellt
- Der Benutzer hat die Möglichkeit, durch Eingabeprompts zusätzlichen Kontext zu definieren:
  - Inhaltlicher Kontext kann vorgegeben werden
  - Spezifische Analyseziele können präzisiert werden
  - Diese Eingaben ergänzen die automatischen Erkennungs- und Detektionsfunktionen

## 2. Ressourcenplanung und Kostenübersicht

### 2.1 GPU-Ressourcenübersicht

- Vor der Analyse erhält der Benutzer eine detaillierte Übersicht über die benötigten GPU-Ressourcen:
  - Liste der verfügbaren GPU-Anbieter (z.B. AWS, Google Cloud, Azure)
  - Spezifikationen der eingesetzten GPU-Modelle (z.B. NVIDIA A100, V100)
  - Voraussichtliche Dauer der Analyse basierend auf Dateigröße und -komplexität

### 2.2 Kostenaufstellung

- Eine transparente Kostenaufstellung wird präsentiert:
  - Geschätzte Kosten pro GPU-Stunde
  - Gesamtkosten für die Analyse aller ausgewählten Mediendateien
  - Optionale Kostenoptimierungen (z.B. niedrigere Priorität für geringere Kosten)
  - Vergleich verschiedener GPU-Optionen mit Preis-Leistungs-Verhältnis

### 2.3 Bestätigung und Start

- Der Benutzer bestätigt die Analyse durch Klicken auf "OK" oder "Akzeptieren"
- Nach der Bestätigung:
  - Das System beginnt mit der Aufbereitung der Mediendaten
  - Verschlüsselte Übertragung an die GPU-Instanz wird initiiert
  - Der Benutzer erhält eine Fortschrittsanzeige für den gesamten Prozess

## 3. Analyseprozess

### 3.1 Medienverarbeitung

- Die Mediendaten werden für die Analyse vorbereitet:
  - Formatvalidierung und -optimierung
  - Extraktion relevanter Metadaten
  - Verschlüsselung für die sichere Übertragung

### 3.2 GPU-Analyse

- Die Analyse erfolgt auf den zugewiesenen GPU-Instanzen:
  - Parallele Verarbeitung verschiedener Aspekte (Bild, Video, Audio)
  - Fortlaufende Statusaktualisierungen für den Benutzer
  - Zwischenergebnisse werden gesichert

### 3.3 Ergebnisrückführung

- Nach Abschluss der Analyse:
  - Die Ergebnisse werden von der GPU-Instanz an das System zurückgesendet
  - Alternativ holt das System die Ergebnisse von der GPU-Instanz ab
  - Die Daten werden entschlüsselt und für die Weiterverarbeitung vorbereitet

## 4. Ergebnisdarstellung

### 4.1 Datenfusion

- Ein Open-Source-LLM-Modell fusioniert die verschiedenen Analyseergebnisse:
  - Integration von Bild-, Video- und Audioanalysen
  - Erstellung eines kohärenten Analysekontexts
  - Identifikation von Zusammenhängen zwischen verschiedenen Medien

### 4.2 Personendossiers

- Der Benutzer erhält Zugriff auf strukturierte Personendossiers:
  - Erkannte Personen aus Bild- oder Videodateien werden zusammengefasst
  - Biometrische Merkmale werden dargestellt
  - Zeitliche und räumliche Zuordnung der Personen
  - Beziehungen zwischen erkannten Personen

### 4.3 Detaillierte Analyseergebnisse

- Der Benutzer kann die spezifischen Ergebnisse der verschiedenen Analysetypen einsehen:
  - Audioanalyse: Transkriptionen, Sprechererkennung, Emotionsanalyse
  - Bildanalyse: Objekterkennung, Szenenerkennung, Textextraktion
  - Videoanalyse: Bewegungsanalyse, Aktivitätserkennung, zeitliche Abläufe

### 4.4 Interaktive Exploration

- Die Benutzeroberfläche ermöglicht eine interaktive Exploration der Ergebnisse:
  - Zeitleisten für die Navigation in Videos
  - Filteroptionen für spezifische Erkennungen
  - Verknüpfungen zwischen zusammengehörigen Elementen
  - Exportmöglichkeiten für Berichte und Einzelergebnisse

## 5. Nachbearbeitung

### 5.1 Manuelle Korrekturen

- Der Benutzer kann bei Bedarf manuelle Korrekturen vornehmen:
  - Anpassung von Personenzuordnungen
  - Ergänzung fehlender Erkennungen
  - Korrektur von Fehlinterpretationen

### 5.2 Ergebnisexport

- Die Analyseergebnisse können in verschiedenen Formaten exportiert werden:
  - PDF-Berichte für Dokumentationszwecke
  - JSON-Daten für Weiterverarbeitung
  - CSV-Dateien für tabellarische Auswertungen
  - Mediendateien mit eingebetteten Annotationen

Dieses Anwendungsszenario beschreibt den idealtypischen Ablauf aus Benutzersicht. Die tatsächliche Implementierung kann je nach spezifischen Anforderungen und technischen Rahmenbedingungen variieren.