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
- Gesichtserkennung (MTCNN + InceptionResnetV1) mit 512‑dim Embeddings pro Gesicht

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
    faces/
      detector.py
      encoder.py
      face_pipeline.py
    ocr.py
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
Hinweis: `facenet-pytorch` ist enthalten und benötigt eine kompatible PyTorch‑Version (bereits in `requirements.txt`).

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
- Faces‑Defaults:
  - `FACES_ENABLED_DEFAULT = False`
  - `FACES_MIN_CONFIDENCE = 0.9`
  - `FACES_MAX_PER_SCENE = 10`

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
## API-Server
Voraussetzungen: `fastapi`, `uvicorn` sind in `requirements.txt` enthalten.

Start:
```
uvicorn aima.api.server:app --reload
```
Standard-Port: `http://127.0.0.1:8000`

Dokumentation: `http://127.0.0.1:8000/docs`

Beispiele:
- POST `/analyze`
  ```json
  {
    "video_path": "Tagesschau.mp4",
    "duration": 11,
    "modules": ["objects", "asr"]
  }
  ```
- GET `/scene/{id}`
- GET `/search?query=deutsche+fernsehen+studio&top_k=3`

## Gesichtserkennung – Ausgabeformat
- Aktivierung über `aima/config.py` (`FACES_ENABLED_DEFAULT = True`).
- Pro Szene wird im JSON‑Report das Feld `faces` ergänzt:
  - `face_id`: eindeutige ID pro Szene
  - `bbox`: `[x1, y1, x2, y2]`
  - `confidence`: Erkennungs‑Confidence
  - `embedding`: Liste mit 512 Fließkommawerten (InceptionResnetV1)
- Fehlerrobust: Falls kein Gesicht erkannt wird, bleibt `faces` leer und der `facenet`‑Status im `models`‑Block dokumentiert den Schritt.