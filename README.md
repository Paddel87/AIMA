# AIMA – AI Media Analysis Pipeline (MVP)

## Projektübersicht
AIMA ist eine modulare Offline-Videoanalyse-Pipeline, die Videos in Szenen zerlegt und für jede Szene Frames, Audios (ASR), Objektdetektionen, Tags und JSON-Reports erzeugt. Zusätzlich werden pro Szene Embeddings erstellt und persistent in einem Vektorstore gespeichert, um semantische Suche zu ermöglichen. Der Fokus liegt auf lokaler Verarbeitung, klarer Struktur und einfacher Erweiterbarkeit.

## Funktionsumfang
- Szenenerkennung (feste 5‑Sekunden‑Fenster)
- Frame‑Extraktion per `ffmpeg` (Mitte der Szene)
- Whisper ASR mit segmentgenauer Szenenzuordnung
- YOLOv8 Objekterkennung (konfigurierbarer Confidence‑Threshold)
- Tag‑Generierung aus Objekten + ASR‑Texten
- Embeddings per SentenceTransformer (`all-MiniLM-L6-v2`)
- ChromaDB‑Vektorspeicher pro Szene
- Semantische Szenensuche über `search`‑Befehl
- Status‑Dokumentation pro Modell (`ffmpeg`, `whisper`, `yolo`)

## Projektstruktur
```
aima/
  cli/
    main.py
  pipelines/
    analyzer.py
  services/
    frame_extractor.py
    embedding_service.py
    vector_store.py
  modules/
    objects/
      yolo.py
    asr/
      whisper_asr.py
  schemas/
    models.py
  aggregator/
    json_aggregator.py
outputs/
  ... (bei Ausführung erzeugt)
Tagesschau.mp4 (Beispieldatei)
requirements.txt
README.md
```
- `aima/cli/`: CLI‑Befehle (`analyze`, `search`)
- `aima/pipelines/`: Orchestrierung der End‑to‑End‑Analyse
- `aima/services/`: Dienste (Frame‑Extraktion, Embeddings, Vectorstore)
- `aima/modules/`: Modell‑Module (Objekterkennung, ASR)
- `aima/schemas/`: Pydantic‑Modelle und Szenen‑Schemas
- `aima/aggregator/`: Ausgabe/Serialization nach JSON
- `outputs/`: Ergebnisse (Frames, JSONs, Vectorstore)

## Installation
Virtuelle Umgebung (Host bleibt sauber):
```
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1
```
Abhängigkeiten:
```
pip install --upgrade pip
pip install -r requirements.txt
```
Hinweis: `ffmpeg` wird portabel im Workspace eingebunden, falls nicht im System vorhanden.

## Nutzung
Analyse eines Videos:
```
python -m aima.cli.main analyze Tagesschau.mp4 --duration 11 --modules objects,asr --out outputs
```
Erklärung:
- `analyze`: führt die komplette Pipeline aus
- `duration`: zu analysierende Videolänge
- `modules`: welche Module aktiv sind (z. B. `objects,asr`)
- `out`: Ausgabeverzeichnis

Beispielausgabe:
- `outputs/scene_0.json`
- `outputs/frames/scene_0.jpg`
- `outputs/scene_1.json`, `outputs/frames/scene_1.jpg` usw.

## Semantische Suche
Befehl:
```
python -m aima.cli.main search "deutsche fernsehen studio" --top_k 3
```
Ablauf:
- Embedding der Query
- ChromaDB‑Abfrage
- Ausgabe: Szenen‑IDs, Scores, zugehörige JSONs

## Konfiguration
- YOLO‑Threshold: `DEFAULT_YOLO_THRESHOLD = 0.6`
- Whisper‑Modell: `"small"` (konfigurierbar)
- Embedding‑Modell: `"all-MiniLM-L6-v2"`
- Vektorstore‑Pfad: `outputs/vectorstore`

## Erweiterungsideen (Roadmap)
- OCR (PaddleOCR)
- Gesichtserkennung (InsightFace)
- Pose Tracking
- automatische Szenenerkennung
- LLM‑basierte Query‑Reformulierung
- Web‑Frontend
- Docker‑Containerisierung

## Lizenz / Hinweis
Dieses Projekt ist ein technisches MVP und dient zu Forschungs‑ und Entwicklungszwecken.