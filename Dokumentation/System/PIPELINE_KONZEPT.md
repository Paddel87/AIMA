# AIMA Pipeline-Konzept mit zeitlicher Synchronisation

## Überblick

Dieses Dokument beschreibt die zeitlich synchronisierte Pipeline-Architektur für das AIMA-System mit **LLaVA-1.6 (34B) als zentralem multimodalen Modell** und **Llama 3.1 (70B/405B) für finale Datenfusion**. Diese konsolidierte Architektur reduziert die Komplexität erheblich, indem LLaVA die meisten spezialisierten Bildanalysemodelle ersetzt.

## 1. Zeitschienen-Architektur

### 1.1 Master-Timeline

```python
class AIMATimeline:
    def __init__(self, media_file):
        self.start_time = 0
        self.duration = media_file.duration
        self.fps = 30  # Standard Video-FPS
        self.audio_sample_rate = 44100
        self.analysis_window = 1.0  # 1 Sekunde Analyse-Fenster
        self.sync_points = []  # Synchronisationspunkte
        
    def create_sync_points(self):
        """Erstellt Synchronisationspunkte alle 1 Sekunde"""
        for t in range(0, int(self.duration), 1):
            self.sync_points.append({
                'timestamp': t,
                'frame_number': t * self.fps,
                'audio_sample': t * self.audio_sample_rate
            })
```

### 1.2 Zeitliche Koordination

```
Zeitschiene (Sekunden):  0----1----2----3----4----5----6----7----8----9----10
Video-Frames:           [0-29][30-59][60-89][90-119][120-149][150-179]...
Audio-Samples:          [0-44k][44k-88k][88k-132k][132k-176k]...
Analyse-Fenster:        [  W1  ][  W2  ][  W3  ][  W4  ][  W5  ]...
```

## 2. Pipeline-Architektur

### 2.1 Drei-Stufen-Pipeline

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   STUFE 1:      │    │   STUFE 2:      │    │   STUFE 3:      │
│ Datenextraktion │───▶│ Multimodale     │───▶│ Finale Fusion   │
│                 │    │ Analyse         │    │ & Bewertung     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2.2 Konsolidierte Pipeline-Struktur

```python
class AIMAPipeline:
    def __init__(self):
        # Stufe 1: Datenextraktion
        self.media_extractor = MediaExtractor()  # Vereinheitlicht für alle Medientypen
        
        # Stufe 2: LLaVA-zentrierte Multimodale Analyse
        self.llava_analyzer = LLaVAAnalyzer()  # Primäres multimodales Modell
        self.whisper_analyzer = WhisperAnalyzer()  # Spezialisiert für Audio
        
        # Stufe 3: Llama 3.1 Finale Fusion
        self.llama_fusion = Llama31Fusion()  # Finale Synthese und Kontextualisierung
        
        # Zeitliche Synchronisation
        self.timeline = None
        self.sync_buffer = SynchronizationBuffer()
        
        # Fallback-Modelle (nur bei Bedarf)
        self.fallback_models = {
            'face_detection': None,  # RetinaFace bei Bedarf
            'speaker_id': None       # Zusätzliche Audio-Modelle bei Bedarf
        }
```

## 3. Stufe 1: Zeitlich synchronisierte Datenextraktion

### 3.1 Audio-Extraktion

```python
class AudioExtractor:
    def extract_timeline_data(self, audio_file, timeline):
        results = []
        
        for sync_point in timeline.sync_points:
            window_start = sync_point['timestamp']
            window_end = window_start + timeline.analysis_window
            
            # Audio-Segment extrahieren
            audio_segment = audio_file[window_start:window_end]
            
            results.append({
                'timestamp': window_start,
                'duration': timeline.analysis_window,
                'audio_data': audio_segment,
                'sample_rate': timeline.audio_sample_rate
            })
            
        return results
```

### 3.2 Video-Extraktion

```python
class VideoExtractor:
    def extract_timeline_data(self, video_file, timeline):
        results = []
        
        for sync_point in timeline.sync_points:
            # Repräsentativer Frame pro Sekunde (mittlerer Frame)
            target_frame = sync_point['frame_number'] + (timeline.fps // 2)
            
            # Frame extrahieren
            frame = video_file.get_frame(target_frame)
            
            results.append({
                'timestamp': sync_point['timestamp'],
                'frame_number': target_frame,
                'frame_data': frame,
                'resolution': frame.shape
            })
            
        return results
```

## 4. Stufe 2: Multimodale Analyse

### 4.1 Audio-Analyse-Pipeline

```python
class AudioAnalyzer:
    def __init__(self):
        self.whisper = WhisperModel()
        self.emotion2vec = Emotion2VecModel()
        self.panns = PANNsModel()
        self.pyannote = PyannoteModel()
        
    def analyze_timeline(self, audio_timeline_data):
        results = []
        
        for audio_segment in audio_timeline_data:
            timestamp = audio_segment['timestamp']
            audio_data = audio_segment['audio_data']
            
            # Parallele Analyse aller Audio-Modelle
            analysis = {
                'timestamp': timestamp,
                'transcription': self.whisper.transcribe(audio_data),
                'emotion': self.emotion2vec.analyze(audio_data),
                'environment': self.panns.classify(audio_data),
                'speakers': self.pyannote.diarize(audio_data)
            }
            
            results.append(analysis)
            
        return results
```

### 4.2 LLaVA-basierte Visuelle Analyse

```python
class LLaVAAnalyzer:
    def __init__(self):
        self.llava_model = LLaVAModel()
        self.forensic_prompts = ForensicPrompts()
        
    def analyze_timeline(self, video_timeline_data, audio_context=None):
        results = []
        
        for frame_data in video_timeline_data:
            timestamp = frame_data['timestamp']
            frame = frame_data['frame_data']
            
            # Kontextueller Prompt mit Audio-Informationen
            if audio_context and timestamp in audio_context:
                audio_info = audio_context[timestamp]
                prompt = self.create_contextual_prompt(audio_info)
            else:
                prompt = self.forensic_prompts.base_analysis
            
            # LLaVA-Analyse
            visual_analysis = self.llava_model.analyze(
                image=frame,
                prompt=prompt,
                timestamp=timestamp
            )
            
            results.append({
                'timestamp': timestamp,
                'visual_analysis': visual_analysis,
                'confidence': visual_analysis.confidence,
                'key_observations': visual_analysis.key_points
            })
            
        return results
    
    def create_contextual_prompt(self, audio_info):
        return f"""
        Analysiere dieses Bild im Kontext folgender Audio-Informationen:
        - Transkript: "{audio_info['transcription']}"
        - Emotion: {audio_info['emotion']}
        - Sprecher: {audio_info['speakers']}
        
        Bewerte besonders:
        1. Konsens-Indikatoren in Körpersprache und Gesichtsausdruck
        2. Korrelation zwischen visuellen und auditiven Signalen
        3. Machtdynamiken zwischen den Personen
        4. Anzeichen von Zwang oder Freiwilligkeit
        """
```

## 5. Stufe 3: Zeitlich synchronisierte Fusion

### 5.1 Synchronisations-Buffer

```python
class SynchronizationBuffer:
    def __init__(self):
        self.audio_buffer = {}
        self.visual_buffer = {}
        self.fusion_results = {}
        
    def add_audio_analysis(self, timestamp, analysis):
        self.audio_buffer[timestamp] = analysis
        self._try_fusion(timestamp)
        
    def add_visual_analysis(self, timestamp, analysis):
        self.visual_buffer[timestamp] = analysis
        self._try_fusion(timestamp)
        
    def _try_fusion(self, timestamp):
        """Versucht Fusion wenn beide Modalitäten verfügbar"""
        if (timestamp in self.audio_buffer and 
            timestamp in self.visual_buffer):
            self._perform_fusion(timestamp)
    
    def _perform_fusion(self, timestamp):
        audio_data = self.audio_buffer[timestamp]
        visual_data = self.visual_buffer[timestamp]
        
        # Fusion durch Llama 3.1
        fusion_result = self.llama_fusion.fuse(
            audio=audio_data,
            visual=visual_data,
            timestamp=timestamp
        )
        
        self.fusion_results[timestamp] = fusion_result
```

### 5.2 Llama 3.1 Fusion-Engine

```python
class LlamaFusion:
    def __init__(self):
        self.llama_model = Llama31Model()
        self.fusion_prompts = FusionPrompts()
        
    def fuse(self, audio, visual, timestamp):
        fusion_prompt = self.create_fusion_prompt(audio, visual, timestamp)
        
        result = self.llama_model.generate(
            prompt=fusion_prompt,
            temperature=0.1,  # Niedrig für konsistente Ergebnisse
            max_tokens=1000
        )
        
        return {
            'timestamp': timestamp,
            'fusion_analysis': result.text,
            'confidence': result.confidence,
            'consent_assessment': self.extract_consent_score(result),
            'risk_indicators': self.extract_risk_indicators(result)
        }
    
    def create_fusion_prompt(self, audio, visual, timestamp):
        return f"""
        FORENSISCHE ANALYSE - Zeitpunkt: {timestamp}s
        
        AUDIO-DATEN:
        - Transkript: "{audio['transcription']}"
        - Emotion: {audio['emotion']} (Konfidenz: {audio['emotion_confidence']})
        - Umgebung: {audio['environment']}
        - Sprecher: {audio['speakers']}
        
        VISUELLE DATEN:
        {visual['visual_analysis']}
        
        AUFGABE:
        Analysiere die Korrelation zwischen Audio- und visuellen Daten.
        Bewerte den Konsens auf einer Skala von 0-100:
        - 0-20: Eindeutig Non-Konsens
        - 21-40: Wahrscheinlich Non-Konsens
        - 41-60: Unklar/Ambivalent
        - 61-80: Wahrscheinlich Konsens
        - 81-100: Eindeutig Konsens
        
        Begründe deine Bewertung mit spezifischen Beobachtungen.
        """
```

## 6. Zeitliche Konsistenz und Trends

### 6.1 Temporal Analysis

```python
class TemporalAnalyzer:
    def __init__(self):
        self.window_size = 5  # 5-Sekunden-Fenster für Trends
        
    def analyze_trends(self, fusion_results):
        """Analysiert zeitliche Trends in den Fusion-Ergebnissen"""
        timestamps = sorted(fusion_results.keys())
        trends = []
        
        for i in range(len(timestamps) - self.window_size + 1):
            window_timestamps = timestamps[i:i + self.window_size]
            window_data = [fusion_results[t] for t in window_timestamps]
            
            trend_analysis = self.analyze_window_trend(window_data)
            trends.append({
                'start_time': window_timestamps[0],
                'end_time': window_timestamps[-1],
                'trend': trend_analysis
            })
            
        return trends
    
    def analyze_window_trend(self, window_data):
        consent_scores = [d['consent_assessment'] for d in window_data]
        
        # Trend-Berechnung
        if len(consent_scores) < 2:
            return 'insufficient_data'
            
        slope = (consent_scores[-1] - consent_scores[0]) / len(consent_scores)
        
        if slope > 10:
            return 'improving_consent'
        elif slope < -10:
            return 'deteriorating_consent'
        else:
            return 'stable_consent'
```

## 7. Pipeline-Orchestrierung

### 7.1 Master-Controller

```python
class AIMAPipelineController:
    def __init__(self):
        self.pipeline = AIMAPipeline()
        self.timeline = None
        self.sync_buffer = SynchronizationBuffer()
        self.temporal_analyzer = TemporalAnalyzer()
        
    async def process_media(self, media_file):
        """Hauptverarbeitungsschleife"""
        # 1. Timeline erstellen
        self.timeline = AIMATimeline(media_file)
        
        # 2. Datenextraktion
        audio_timeline = await self.extract_audio_timeline(media_file)
        video_timeline = await self.extract_video_timeline(media_file)
        
        # 3. Parallele Analyse
        audio_task = self.analyze_audio_timeline(audio_timeline)
        video_task = self.analyze_video_timeline(video_timeline, audio_timeline)
        
        await asyncio.gather(audio_task, video_task)
        
        # 4. Temporale Analyse
        trends = self.temporal_analyzer.analyze_trends(
            self.sync_buffer.fusion_results
        )
        
        # 5. Finale Bewertung
        final_assessment = self.create_final_assessment(trends)
        
        return final_assessment
    
    async def analyze_audio_timeline(self, audio_timeline):
        """Asynchrone Audio-Analyse"""
        for audio_segment in audio_timeline:
            analysis = await self.pipeline.audio_analyzer.analyze(
                audio_segment
            )
            self.sync_buffer.add_audio_analysis(
                audio_segment['timestamp'], 
                analysis
            )
    
    async def analyze_video_timeline(self, video_timeline, audio_context):
        """Asynchrone Video-Analyse mit Audio-Kontext"""
        for frame_data in video_timeline:
            analysis = await self.pipeline.llava_analyzer.analyze(
                frame_data, 
                audio_context
            )
            self.sync_buffer.add_visual_analysis(
                frame_data['timestamp'], 
                analysis
            )
```

## 8. Performance-Optimierungen

### 8.1 Parallele Verarbeitung

```python
class ParallelProcessor:
    def __init__(self, num_workers=4):
        self.num_workers = num_workers
        self.audio_queue = asyncio.Queue()
        self.video_queue = asyncio.Queue()
        
    async def process_parallel(self, timeline_data):
        # Audio-Worker
        audio_workers = [
            self.audio_worker() for _ in range(self.num_workers // 2)
        ]
        
        # Video-Worker
        video_workers = [
            self.video_worker() for _ in range(self.num_workers // 2)
        ]
        
        # Daten in Queues einreihen
        for data in timeline_data:
            await self.audio_queue.put(data['audio'])
            await self.video_queue.put(data['video'])
        
        # Parallele Verarbeitung
        await asyncio.gather(*audio_workers, *video_workers)
```

### 8.2 Caching-Strategien

```python
class AnalysisCache:
    def __init__(self):
        self.frame_cache = {}
        self.audio_cache = {}
        
    def get_cached_analysis(self, data_hash, timestamp):
        """Prüft ob Analyse bereits existiert"""
        cache_key = f"{data_hash}_{timestamp}"
        return self.frame_cache.get(cache_key)
    
    def cache_analysis(self, data_hash, timestamp, analysis):
        """Speichert Analyse-Ergebnis"""
        cache_key = f"{data_hash}_{timestamp}"
        self.frame_cache[cache_key] = analysis
```

## 9. Monitoring und Debugging

### 9.1 Pipeline-Monitoring

```python
class PipelineMonitor:
    def __init__(self):
        self.metrics = {
            'processing_times': [],
            'sync_delays': [],
            'model_performances': {},
            'error_rates': {}
        }
    
    def log_processing_time(self, stage, duration):
        self.metrics['processing_times'].append({
            'stage': stage,
            'duration': duration,
            'timestamp': time.time()
        })
    
    def log_sync_delay(self, expected_time, actual_time):
        delay = actual_time - expected_time
        self.metrics['sync_delays'].append(delay)
    
    def generate_report(self):
        return {
            'avg_processing_time': np.mean([m['duration'] for m in self.metrics['processing_times']]),
            'max_sync_delay': max(self.metrics['sync_delays']) if self.metrics['sync_delays'] else 0,
            'total_processed_segments': len(self.metrics['processing_times'])
        }
```

## 10. Konfiguration und Deployment

### 10.1 Pipeline-Konfiguration

```yaml
# pipeline_config.yaml
aima_pipeline:
  timeline:
    analysis_window: 1.0  # Sekunden
    fps: 30
    audio_sample_rate: 44100
  
  models:
    llava:
      model_path: "./models/llava-1.5-13b"
      max_tokens: 1000
      temperature: 0.1
    
    llama31:
      model_path: "./models/llama-3.1-70b"
      max_tokens: 2000
      temperature: 0.1
  
  performance:
    parallel_workers: 4
    cache_enabled: true
    batch_size: 8
  
  output:
    save_intermediate: true
    export_timeline: true
    generate_report: true
```

### 10.2 Hardware-Anforderungen

```
Minimale Konfiguration:
- GPU: 2x RTX 4090 (48GB VRAM)
- RAM: 64GB DDR4
- Storage: 2TB NVMe SSD
- CPU: 16-Core (für parallele Verarbeitung)

Optimale Konfiguration:
- GPU: 4x RTX 4090 (96GB VRAM) oder 2x A6000
- RAM: 128GB DDR4
- Storage: 4TB NVMe SSD
- CPU: 32-Core
```

## 11. Beispiel-Workflow

```python
# Beispiel für komplette Pipeline-Ausführung
async def main():
    # Pipeline initialisieren
    controller = AIMAPipelineController()
    
    # Media-Datei laden
    media_file = MediaFile("evidence_video.mp4")
    
    # Verarbeitung starten
    print("Starte AIMA-Pipeline...")
    result = await controller.process_media(media_file)
    
    # Ergebnisse ausgeben
    print(f"Verarbeitung abgeschlossen:")
    print(f"- Gesamtdauer: {result['duration']}s")
    print(f"- Analysierte Segmente: {result['segments_count']}")
    print(f"- Durchschnittlicher Konsens-Score: {result['avg_consent_score']}")
    print(f"- Kritische Zeitpunkte: {len(result['critical_moments'])}")
    
    # Detailbericht generieren
    report = controller.generate_detailed_report()
    report.save("aima_analysis_report.pdf")

if __name__ == "__main__":
    asyncio.run(main())
```

Dieses Pipeline-Konzept gewährleistet eine zeitlich synchronisierte, effiziente und skalierbare Verarbeitung aller Modalitäten im AIMA-System unter optimaler Nutzung von LLaVA für die multimodale Fusion.