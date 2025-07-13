# AIMA Datenspeicherung und Datenfusion - Systemarchitektur

Basierend auf der Analyse der ML-Modelle im AIMA-System wurde der Umfang der generierten Metadaten ermittelt. Dieses Dokument definiert die Architektur für Datenspeicherung und multimodale Datenfusion.

## 1. Übersicht der generierten Metadaten

### 1.1 Audio-Metadaten

#### Spracherkennung (Whisper)
```json
{
  "transcription": {
    "text": "Vollständiger Transkriptionstext",
    "language": "de",
    "confidence": 0.95,
    "segments": [
      {
        "start": 0.0,
        "end": 2.5,
        "text": "Segment-Text",
        "confidence": 0.92
      }
    ]
  }
}
```

#### Emotionsanalyse (Emotion2Vec)
```json
{
  "audio_emotions": {
    "valence": 0.3,
    "arousal": 0.8,
    "dominance": 0.2,
    "emotion_class": "fear",
    "confidence": 0.87,
    "timestamp": "00:01:23.456"
  }
}
```

#### Geräuschanalyse (PANNs)
```json
{
  "audio_events": [
    {
      "event_class": "scream",
      "confidence": 0.92,
      "start_time": 15.2,
      "end_time": 17.8,
      "intensity": 0.85
    },
    {
      "event_class": "metal_clanking",
      "confidence": 0.78,
      "start_time": 45.1,
      "end_time": 46.3,
      "intensity": 0.65
    }
  ]
}
```

#### Schlüsselwort-Erkennung (BC-ResNet)
```json
{
  "keywords": {
    "consent_indicators": [
      {
        "word": "nein",
        "category": "non_consent",
        "confidence": 0.95,
        "timestamp": "00:02:15.123",
        "priority": "critical"
      }
    ],
    "bdsm_terms": [
      {
        "word": "shibari",
        "category": "bondage_technique",
        "confidence": 0.88,
        "timestamp": "00:00:45.678"
      }
    ]
  }
}
```

#### Speaker Diarization (pyannote.audio)
```json
{
  "speakers": {
    "speaker_segments": [
      {
        "speaker_id": "SPEAKER_00",
        "start": 0.0,
        "end": 5.2,
        "confidence": 0.91
      },
      {
        "speaker_id": "SPEAKER_01",
        "start": 5.2,
        "end": 8.7,
        "confidence": 0.89
      }
    ],
    "speaker_count": 2
  }
}
```

### 1.2 Bild/Video-Metadaten

#### Personenerkennung (RetinaFace + ArcFace)
```json
{
  "persons": [
    {
      "person_id": "PERSON_001",
      "face_embedding": [512-dim vector],
      "bounding_box": [x, y, width, height],
      "landmarks": {
        "left_eye": [x, y],
        "right_eye": [x, y],
        "nose": [x, y],
        "left_mouth": [x, y],
        "right_mouth": [x, y]
      },
      "confidence": 0.94,
      "frame_number": 1250,
      "timestamp": "00:00:41.667"
    }
  ]
}
```

#### Pose Estimation (HRNet/AlphaPose)
```json
{
  "poses": [
    {
      "person_id": "PERSON_001",
      "keypoints": {
        "nose": [x, y, confidence],
        "left_shoulder": [x, y, confidence],
        "right_shoulder": [x, y, confidence],
        "left_wrist": [x, y, confidence],
        "right_wrist": [x, y, confidence]
        // ... weitere 12 Keypoints
      },
      "pose_confidence": 0.87,
      "stress_indicators": {
        "tension_score": 0.75,
        "unnatural_position": true
      },
      "frame_number": 1250
    }
  ]
}
```

#### Objekterkennung (InstructBLIP/CLIP)
```json
{
  "objects": {
    "restraints": [
      {
        "object_type": "rope",
        "material": "natural_fiber",
        "application": "wrist_binding",
        "safety_assessment": "moderate_risk",
        "bounding_box": [x, y, width, height],
        "confidence": 0.91
      }
    ],
    "safety_equipment": [
      {
        "object_type": "safety_shears",
        "accessibility": "visible_nearby",
        "confidence": 0.85
      }
    ]
  }
}
```

#### Kleidungsanalyse (DeepFashion2)
```json
{
  "clothing": [
    {
      "person_id": "PERSON_001",
      "clothing_items": [
        {
          "category": "underwear",
          "coverage": "partial",
          "material": "lace",
          "color": "black",
          "condition": "intact"
        }
      ],
      "undressing_level": 0.7,
      "context_indicator": "planned_scenario"
    }
  ]
}
```

#### Emotionserkennung Gesicht (AffectNet)
```json
{
  "facial_emotions": [
    {
      "person_id": "PERSON_001",
      "emotions": {
        "fear": 0.75,
        "sadness": 0.15,
        "anger": 0.05,
        "neutral": 0.03,
        "happiness": 0.02
      },
      "valence": -0.6,
      "arousal": 0.8,
      "confidence": 0.89,
      "frame_number": 1250
    }
  ]
}
```

#### Szenenanalyse (Places365/CLIP)
```json
{
  "scene_context": {
    "location_type": "bedroom",
    "privacy_level": "private",
    "lighting": "dim_artificial",
    "safety_environment": "controlled",
    "preparation_indicators": [
      "arranged_furniture",
      "specialized_equipment",
      "mood_lighting"
    ],
    "confidence": 0.88
  }
}
```

## 2. Datenbank-Architektur

### 2.1 Hauptdatenbank-Schema (PostgreSQL)

#### Media Files Tabelle
```sql
CREATE TABLE media_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(20) NOT NULL, -- 'audio', 'image', 'video'
    file_size BIGINT,
    duration DECIMAL(10,3), -- für Audio/Video in Sekunden
    resolution VARCHAR(20), -- für Bilder/Videos
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'pending',
    hash_sha256 VARCHAR(64) UNIQUE
);
```

#### Analysis Sessions Tabelle
```sql
CREATE TABLE analysis_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    media_file_id UUID REFERENCES media_files(id),
    session_type VARCHAR(50), -- 'full_analysis', 'quick_scan', 'forensic'
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running',
    final_consent_score DECIMAL(5,2), -- 0.00 bis 100.00
    risk_level VARCHAR(20), -- 'low', 'medium', 'high', 'critical'
    requires_review BOOLEAN DEFAULT FALSE
);
```

### 2.2 Metadaten-Speicherung (JSON-Dokumente)

#### Audio Metadata Tabelle
```sql
CREATE TABLE audio_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES analysis_sessions(id),
    transcription JSONB,
    emotions JSONB,
    audio_events JSONB,
    keywords JSONB,
    speakers JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indizes für effiziente Abfragen
CREATE INDEX idx_audio_keywords ON audio_metadata USING GIN ((keywords->'consent_indicators'));
CREATE INDEX idx_audio_emotions ON audio_metadata USING GIN ((emotions->'valence'));
```

#### Visual Metadata Tabelle
```sql
CREATE TABLE visual_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES analysis_sessions(id),
    frame_number INTEGER, -- NULL für Einzelbilder
    timestamp_ms INTEGER, -- Millisekunden im Video
    persons JSONB,
    poses JSONB,
    objects JSONB,
    clothing JSONB,
    facial_emotions JSONB,
    scene_context JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indizes für zeitbasierte Abfragen
CREATE INDEX idx_visual_timestamp ON visual_metadata (session_id, timestamp_ms);
CREATE INDEX idx_visual_persons ON visual_metadata USING GIN (persons);
```

#### Fusion Results Tabelle
```sql
CREATE TABLE fusion_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES analysis_sessions(id),
    llm_model VARCHAR(50), -- 'llama-3.1-70b', 'llama-3.1-405b'
    fusion_timestamp TIMESTAMP DEFAULT NOW(),
    
    -- Hauptergebnisse
    consent_score DECIMAL(5,2) NOT NULL,
    risk_assessment JSONB NOT NULL,
    
    -- Detaillierte Analyse
    temporal_analysis JSONB, -- Zeitliche Entwicklung
    cross_modal_validation JSONB, -- Modalitäten-Abgleich
    inconsistencies JSONB, -- Erkannte Widersprüche
    confidence_scores JSONB, -- Vertrauenswerte pro Modalität
    
    -- Erklärungen
    reasoning JSONB, -- LLM-Begründungen
    evidence_summary JSONB, -- Zusammenfassung der Beweise
    recommendations JSONB, -- Handlungsempfehlungen
    
    -- Metadaten
    processing_time_ms INTEGER,
    model_version VARCHAR(20)
);
```

### 2.3 Time-Series Datenbank (InfluxDB)

Für hochfrequente zeitbasierte Daten:

```influxql
-- Emotionale Verläufe
CREATE MEASUREMENT emotion_timeline (
    time TIMESTAMP,
    session_id TAG,
    person_id TAG,
    modality TAG, -- 'audio', 'visual'
    valence FIELD,
    arousal FIELD,
    dominance FIELD,
    confidence FIELD
);

-- Keyword-Erkennungen
CREATE MEASUREMENT keyword_events (
    time TIMESTAMP,
    session_id TAG,
    keyword TAG,
    category TAG, -- 'consent', 'non_consent', 'bdsm_term'
    confidence FIELD,
    priority TAG
);

-- Pose-Tracking
CREATE MEASUREMENT pose_timeline (
    time TIMESTAMP,
    session_id TAG,
    person_id TAG,
    stress_score FIELD,
    movement_intensity FIELD,
    pose_confidence FIELD
);
```

## 3. Datenfusion-Architektur

### 3.1 LLM-basierte Fusion-Pipeline

#### Fusion-Prompt-Template
```python
FUSION_PROMPT = """
Analysiere die folgenden multimodalen Metadaten einer AIMA-Analyse und erstelle eine Gesamtbewertung:

## Audio-Daten:
{audio_metadata}

## Visuelle Daten:
{visual_metadata}

## Zeitlicher Kontext:
{temporal_context}

## Aufgaben:
1. Bewerte den Konsens-Level (0-100%)
2. Identifiziere Risikofaktoren
3. Erkenne Inkonsistenzen zwischen Modalitäten
4. Erstelle eine begründete Gesamteinschätzung

## Ausgabeformat (JSON):
{
  "consent_score": <0-100>,
  "risk_level": "<low|medium|high|critical>",
  "confidence": <0-1>,
  "reasoning": "<detaillierte Begründung>",
  "evidence": {
    "supporting": ["<Belege für Konsens>"],
    "concerning": ["<Belege gegen Konsens>"]
  },
  "recommendations": ["<Handlungsempfehlungen>"]
}
"""
```

#### Fusion-Service Architektur
```python
class AIMADataFusion:
    def __init__(self):
        self.llm = LlamaModel("llama-3.1-70b")
        self.db = PostgreSQLConnection()
        self.timeseries = InfluxDBConnection()
        
    async def fuse_analysis_data(self, session_id: str) -> FusionResult:
        # 1. Daten sammeln
        audio_data = await self.get_audio_metadata(session_id)
        visual_data = await self.get_visual_metadata(session_id)
        temporal_data = await self.get_temporal_patterns(session_id)
        
        # 2. Daten strukturieren
        fusion_input = self.prepare_fusion_input(
            audio_data, visual_data, temporal_data
        )
        
        # 3. LLM-Fusion
        fusion_result = await self.llm.generate(
            prompt=FUSION_PROMPT.format(**fusion_input),
            max_tokens=2048,
            temperature=0.1
        )
        
        # 4. Ergebnis validieren und speichern
        validated_result = self.validate_fusion_result(fusion_result)
        await self.store_fusion_result(session_id, validated_result)
        
        return validated_result
```

### 3.2 Echtzeit-Fusion für Live-Streams

#### Streaming-Architektur
```python
class RealTimeFusion:
    def __init__(self):
        self.window_size = 30  # 30 Sekunden Analysefenster
        self.update_interval = 5  # Update alle 5 Sekunden
        self.fusion_queue = asyncio.Queue()
        
    async def process_live_stream(self, stream_id: str):
        while True:
            # Sammle Daten der letzten 30 Sekunden
            current_window = await self.get_current_window(stream_id)
            
            # Schnelle Fusion für Echtzeit-Bewertung
            quick_assessment = await self.quick_fusion(current_window)
            
            # Kritische Situationen sofort melden
            if quick_assessment.risk_level == "critical":
                await self.trigger_immediate_alert(stream_id, quick_assessment)
            
            # Vollständige Fusion in Background-Queue
            await self.fusion_queue.put((stream_id, current_window))
            
            await asyncio.sleep(self.update_interval)
```

### 3.3 Konfidenz-Management

#### Konfidenz-Aggregation
```python
class ConfidenceManager:
    def calculate_overall_confidence(self, metadata: Dict) -> float:
        weights = {
            'audio_transcription': 0.15,
            'audio_emotions': 0.20,
            'keyword_detection': 0.25,
            'facial_emotions': 0.20,
            'pose_estimation': 0.15,
            'object_detection': 0.05
        }
        
        weighted_confidence = 0.0
        total_weight = 0.0
        
        for modality, weight in weights.items():
            if modality in metadata and metadata[modality]['confidence'] > 0.5:
                weighted_confidence += metadata[modality]['confidence'] * weight
                total_weight += weight
        
        return weighted_confidence / total_weight if total_weight > 0 else 0.0
```

## 4. API-Schnittstellen

### 4.1 REST API für Analyse-Anfragen

```python
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel

app = FastAPI(title="AIMA Analysis API")

class AnalysisRequest(BaseModel):
    analysis_type: str  # 'full', 'quick', 'forensic'
    priority: str = 'normal'  # 'low', 'normal', 'high', 'critical'
    notify_on_completion: bool = True

@app.post("/analyze/upload")
async def upload_and_analyze(file: UploadFile, request: AnalysisRequest):
    # Datei speichern und Analyse starten
    session_id = await start_analysis(file, request)
    return {"session_id": session_id, "status": "started"}

@app.get("/analyze/{session_id}/status")
async def get_analysis_status(session_id: str):
    status = await get_session_status(session_id)
    return status

@app.get("/analyze/{session_id}/results")
async def get_analysis_results(session_id: str):
    results = await get_fusion_results(session_id)
    return results
```

### 4.2 WebSocket für Echtzeit-Updates

```python
@app.websocket("/ws/analysis/{session_id}")
async def websocket_analysis_updates(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    async for update in get_analysis_updates(session_id):
        await websocket.send_json({
            "type": "analysis_update",
            "session_id": session_id,
            "data": update
        })
```

## 5. Sicherheit und Datenschutz

### 5.1 Datenverschlüsselung

- **At Rest:** AES-256 Verschlüsselung für alle gespeicherten Metadaten
- **In Transit:** TLS 1.3 für alle API-Kommunikation
- **In Memory:** Verschlüsselte RAM-Bereiche für sensitive Daten

### 5.2 Zugriffskontrolle

```python
class AccessControl:
    def __init__(self):
        self.roles = {
            'analyst': ['read_analysis', 'start_analysis'],
            'supervisor': ['read_analysis', 'start_analysis', 'review_results'],
            'admin': ['*']
        }
    
    def check_permission(self, user_role: str, action: str) -> bool:
        if user_role in self.roles:
            permissions = self.roles[user_role]
            return '*' in permissions or action in permissions
        return False
```

### 5.3 Audit-Logging

```sql
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP DEFAULT NOW(),
    user_id VARCHAR(100),
    action VARCHAR(100),
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN,
    details JSONB
);
```

## 6. Performance-Optimierung

### 6.1 Caching-Strategie

- **Redis:** Zwischenspeicherung häufig abgerufener Analyseergebnisse
- **GPU Memory:** Persistente Modell-Ladung für schnelle Inferenz
- **Database Connection Pooling:** Optimierte Datenbankverbindungen

### 6.2 Skalierung

- **Horizontale Skalierung:** Mehrere GPU-Instanzen für parallele Verarbeitung
- **Load Balancing:** Intelligente Verteilung der Analyse-Anfragen
- **Auto-Scaling:** Dynamische Ressourcenzuteilung basierend auf Workload

## 7. Monitoring und Alerting

### 7.1 System-Metriken

- GPU-Auslastung und Speicherverbrauch
- Analyse-Durchsatz und Latenz
- Datenbank-Performance
- API-Response-Zeiten

### 7.2 Kritische Alerts

- Hohe Nicht-Konsens-Scores (>80%)
- System-Ausfälle oder Performance-Probleme
- Ungewöhnliche Analysemuster
- Sicherheitsverletzungen

Diese Architektur gewährleistet eine robuste, skalierbare und sichere Verarbeitung aller AIMA-Metadaten mit intelligenter multimodaler Fusion durch selbst gehostete LLM-Systeme.