# Checkpoint-Mechanismus für AIMA

Dieses Dokument spezifiziert den Checkpoint-Mechanismus für das AIMA-System, der in `MEDIENWORKFLOW.md` erwähnt wird. Es definiert, wann und wie Checkpoints erstellt werden, welche Daten gespeichert werden und wie die Wiederaufnahme nach Fehlern erfolgt.

## 1. Checkpoint-Intervalle

### 1.1 Zeitbasierte Checkpoints
- **Standardintervall**: Alle 5 Minuten während der Analyse
- **Dynamisches Intervall**: Bei ressourcenintensiven Analysen (z.B. 4K-Video) alle 2 Minuten
- **Minimales Intervall**: Nicht weniger als 30 Sekunden zwischen Checkpoints, um Leistungseinbußen zu vermeiden

### 1.2 Fortschrittsbasierte Checkpoints
- **Meilenstein-basiert**: Nach Abschluss jeder Hauptanalysephase (z.B. nach Personenerkennung, vor Beginn der Posenerkennung)
- **Prozentual**: Bei Erreichen von 25%, 50%, 75% und 90% des Gesamtfortschritts
- **Modellwechsel**: Vor und nach dem Wechsel zwischen verschiedenen ML-Modellen

## 2. Zu speichernde Daten

### 2.1 Analysezustand
```json
{
  "job_id": "job_12345",
  "checkpoint_id": "cp_789",
  "timestamp": "2023-06-15T14:30:45Z",
  "progress_percentage": 42.5,
  "current_phase": "pose_estimation",
  "completed_phases": ["person_detection", "face_recognition"],
  "pending_phases": ["object_detection", "emotion_analysis", "fusion"]
}
```

### 2.2 Zwischenergebnisse
- **Extrahierte Metadaten**: Alle bisher generierten Analyseergebnisse im JSON-Format
- **Verarbeitete Frames/Segmente**: Liste der bereits analysierten Video-Frames oder Audio-Segmente
- **Temporäre Personen-IDs**: Zuordnungstabelle für erkannte Personen

### 2.3 Modellzustand
- **Aktive Modelle**: Liste der aktuell verwendeten ML-Modelle mit Versionsinformationen
- **Modell-Caches**: Zwischengespeicherte Embeddings oder Feature-Maps
- **Tracking-Zustand**: Zustand von Tracking-Algorithmen (z.B. für Personen-Tracking über Frames)

### 2.4 Ressourcennutzung
- **GPU-Auslastung**: Aktuelle und durchschnittliche GPU-Nutzung
- **Speicherverbrauch**: Aktueller RAM- und VRAM-Verbrauch
- **Laufzeit**: Bisherige Laufzeit und geschätzte verbleibende Zeit

## 3. Speicherformat und -ort

### 3.1 Format
- **Primäres Format**: JSON für Metadaten und Konfigurationen
- **Binäres Format**: Protocol Buffers für effiziente Speicherung großer Datenmengen
- **Kompression**: GZIP-Kompression für alle Checkpoint-Dateien

### 3.2 Speicherort
- **Temporärer Speicher**: Lokales SSD-Volume auf der GPU-Instanz
- **Persistenter Speicher**: Object Storage (S3-kompatibel) für Langzeit-Verfügbarkeit
- **Verzeichnisstruktur**:
  ```
  /checkpoints/
    /{job_id}/
      /metadata.json
      /{checkpoint_id}/
        /state.json
        /results.pb.gz
        /model_state.pb.gz
  ```

## 4. Wiederaufnahmeprozess

### 4.1 Fehlererkennungsmechanismus
- **Heartbeat-System**: Regelmäßige Statusmeldungen (alle 30 Sekunden)
- **Fehlerklassifizierung**:
  - Kritisch: Sofortiger Abbruch, Neustart von letztem Checkpoint
  - Nicht-kritisch: Retry-Mechanismus, dann Fallback auf letzten Checkpoint
  - Ressourcenmangel: Pausieren und Wiederaufnahme bei Ressourcenverfügbarkeit

### 4.2 Wiederaufnahmeschritte
1. **Checkpoint-Identifikation**: Ermittlung des letzten gültigen Checkpoints
2. **Zustandswiederherstellung**:
   - Laden der Analysekonfiguration und des Fortschritts
   - Wiederherstellung der Zwischenergebnisse
   - Initialisierung der ML-Modelle mit gespeichertem Zustand
3. **Validierung**: Überprüfung der Konsistenz wiederhergestellter Daten
4. **Fortsetzungspunkt**: Bestimmung des exakten Frame/Segments für die Fortsetzung
5. **Ressourcenzuweisung**: Anforderung der benötigten GPU-Ressourcen
6. **Logging**: Detaillierte Protokollierung des Wiederaufnahmeprozesses

### 4.3 Teilweise Wiederaufnahme
- **Phasenbasierte Wiederaufnahme**: Nur fehlgeschlagene Analysephasen werden wiederholt
- **Inkrementelle Verarbeitung**: Bereits analysierte Frames/Segmente werden übersprungen
- **Ergebnisfusion**: Zusammenführung von vorherigen und neuen Analyseergebnissen

## 5. Implementierungsdetails

### 5.1 Checkpoint-Manager-Klasse
```python
class CheckpointManager:
    def __init__(self, job_id, config):
        self.job_id = job_id
        self.config = config
        self.checkpoint_path = f"/checkpoints/{job_id}/"
        self.current_checkpoint = None
        self.checkpoint_history = []
        
    def should_create_checkpoint(self, current_state):
        """Entscheidet, ob ein Checkpoint erstellt werden soll"""
        # Zeitbasierte Prüfung
        time_since_last = time.time() - self.last_checkpoint_time
        if time_since_last >= self.config.time_interval:
            return True
            
        # Fortschrittsbasierte Prüfung
        progress_delta = current_state.progress - self.last_checkpoint_progress
        if progress_delta >= self.config.progress_threshold:
            return True
            
        # Phasenbasierte Prüfung
        if current_state.phase != self.last_phase:
            return True
            
        return False
        
    def create_checkpoint(self, analysis_state, results, model_states):
        """Erstellt einen neuen Checkpoint"""
        checkpoint_id = f"cp_{int(time.time())}"
        
        # Speichere Analysezustand
        state_json = json.dumps(analysis_state)
        self._save_file(f"{checkpoint_id}/state.json", state_json)
        
        # Speichere Zwischenergebnisse
        results_pb = self._serialize_results(results)
        self._save_file(f"{checkpoint_id}/results.pb.gz", self._compress(results_pb))
        
        # Speichere Modellzustände
        model_pb = self._serialize_model_states(model_states)
        self._save_file(f"{checkpoint_id}/model_state.pb.gz", self._compress(model_pb))
        
        # Aktualisiere Checkpoint-Historie
        self.checkpoint_history.append(checkpoint_id)
        self.current_checkpoint = checkpoint_id
        self.last_checkpoint_time = time.time()
        self.last_checkpoint_progress = analysis_state.progress
        self.last_phase = analysis_state.phase
        
        return checkpoint_id
        
    def restore_from_checkpoint(self, checkpoint_id=None):
        """Stellt den Zustand aus einem Checkpoint wieder her"""
        if checkpoint_id is None:
            checkpoint_id = self.current_checkpoint
            
        if checkpoint_id is None:
            raise ValueError("Kein Checkpoint verfügbar")
            
        # Lade Analysezustand
        state_json = self._load_file(f"{checkpoint_id}/state.json")
        analysis_state = json.loads(state_json)
        
        # Lade Zwischenergebnisse
        results_pb_gz = self._load_file(f"{checkpoint_id}/results.pb.gz")
        results = self._deserialize_results(self._decompress(results_pb_gz))
        
        # Lade Modellzustände
        model_pb_gz = self._load_file(f"{checkpoint_id}/model_state.pb.gz")
        model_states = self._deserialize_model_states(self._decompress(model_pb_gz))
        
        return {
            "analysis_state": analysis_state,
            "results": results,
            "model_states": model_states
        }
```

### 5.2 Integration in den Workflow
```python
class MediaAnalysisJob:
    def __init__(self, job_id, media_file, config):
        self.job_id = job_id
        self.media_file = media_file
        self.config = config
        self.checkpoint_manager = CheckpointManager(job_id, config.checkpoint_config)
        self.analysis_state = AnalysisState(job_id)
        
    def run(self):
        try:
            # Initialisierung
            self._initialize_analysis()
            
            # Hauptanalyseschleife
            while not self.analysis_state.is_complete():
                # Führe nächsten Analyseschritt aus
                self._execute_next_phase()
                
                # Prüfe, ob Checkpoint erstellt werden soll
                if self.checkpoint_manager.should_create_checkpoint(self.analysis_state):
                    self._create_checkpoint()
                    
            # Finalisierung
            self._finalize_analysis()
            
            return self.analysis_state.results
            
        except CriticalError as e:
            # Protokolliere Fehler
            logging.error(f"Kritischer Fehler: {str(e)}")
            
            # Versuche Wiederaufnahme
            return self._attempt_recovery()
            
    def _create_checkpoint(self):
        """Erstellt einen Checkpoint des aktuellen Zustands"""
        model_states = self._capture_model_states()
        
        self.checkpoint_manager.create_checkpoint(
            self.analysis_state.to_dict(),
            self.analysis_state.results,
            model_states
        )
        
        logging.info(f"Checkpoint erstellt: {self.checkpoint_manager.current_checkpoint}")
        
    def _attempt_recovery(self):
        """Versucht die Wiederaufnahme nach einem Fehler"""
        logging.info("Starte Wiederherstellung aus letztem Checkpoint")
        
        # Lade letzten Checkpoint
        checkpoint_data = self.checkpoint_manager.restore_from_checkpoint()
        
        # Stelle Analysezustand wieder her
        self.analysis_state = AnalysisState.from_dict(checkpoint_data["analysis_state"])
        
        # Stelle Modellzustände wieder her
        self._restore_model_states(checkpoint_data["model_states"])
        
        # Setze Analyse fort
        logging.info(f"Wiederaufnahme ab Phase: {self.analysis_state.current_phase}")
        return self.run()
```

## 6. Leistungsoptimierung

### 6.1 Checkpoint-Overhead-Minimierung
- **Inkrementelle Checkpoints**: Nur Änderungen seit dem letzten Checkpoint speichern
- **Asynchrones Schreiben**: Checkpoint-Erstellung im Hintergrund, während die Analyse fortgesetzt wird
- **Selektive Serialisierung**: Nur relevante Teile des Modellzustands speichern

### 6.2 Speichereffizienz
- **Datenkompression**: Effiziente Kompression für alle Checkpoint-Daten
- **Garbage Collection**: Automatisches Löschen älterer Checkpoints nach erfolgreicher Erstellung neuer Checkpoints
- **Tiered Storage**: Automatische Migration älterer Checkpoints zu kostengünstigerem Speicher

## 7. Sicherheit und Datenschutz

### 7.1 Verschlüsselung
- **Verschlüsselung im Ruhezustand**: AES-256 für alle gespeicherten Checkpoint-Daten
- **Verschlüsselung bei der Übertragung**: TLS 1.3 für alle Datenübertragungen
- **Schlüsselverwaltung**: Integration mit zentralem Key Management Service

### 7.2 Zugriffssteuerung
- **Rollenbasierte Zugriffssteuerung**: Nur autorisierte Dienste können auf Checkpoints zugreifen
- **Audit-Logging**: Protokollierung aller Zugriffe auf Checkpoint-Daten
- **Automatische Löschung**: Entfernung aller Checkpoints nach Abschluss der Analyse