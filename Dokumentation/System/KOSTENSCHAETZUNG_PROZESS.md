# Kostenschätzung und Zeitpunkt im AIMA-System

Dieses Dokument spezifiziert den Prozess der Kostenschätzung für GPU-basierte Analysen im AIMA-System, einschließlich des genauen Zeitpunkts der Schätzung, der Parameter für die Berechnung und des Umgangs mit Abweichungen.

## 1. Zeitpunkt der Kostenschätzung

### 1.1 Zweistufiger Schätzprozess

#### Erste Schätzung (bei Einreichung)
- **Zeitpunkt**: Unmittelbar nach Upload und Vorverarbeitung des Mediums
- **Genauigkeit**: Grobe Schätzung basierend auf Medieneigenschaften
- **Benutzerinteraktion**: Anzeige der geschätzten Kosten mit Bestätigungsaufforderung
- **Entscheidungspunkt**: Benutzer kann den Job abbrechen oder fortfahren

#### Verfeinerte Schätzung (vor Ausführung)
- **Zeitpunkt**: Unmittelbar vor der tatsächlichen Zuweisung von GPU-Ressourcen
- **Genauigkeit**: Präzisere Schätzung basierend auf aktuellen GPU-Preisen und Verfügbarkeit
- **Benutzerinteraktion**: Nur bei signifikanter Abweichung (>20%) von der ersten Schätzung
- **Automatische Entscheidung**: Fortsetzung ohne Benutzerinteraktion, wenn innerhalb der Toleranz

### 1.2 Prozessablauf

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Medien-Upload  │────▶│  Erste          │────▶│  Einreihung in  │
│  & Verarbeitung │     │  Kostenschätzung│     │  Warteschlange  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │                          │
                               ▼                          ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Benutzer-      │     │  Verfeinerte    │
                        │  Bestätigung    │     │  Kostenschätzung│
                        └─────────────────┘     └─────────────────┘
                               │                          │
                               ▼                          ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Abbruch oder   │────▶│  GPU-Zuweisung  │
                        │  Fortsetzung    │     │  & Ausführung   │
                        └─────────────────┘     └─────────────────┘
```

## 2. Parameter für die Kostenschätzung

### 2.1 Medienspezifische Parameter

#### Videoanalyse
- **Dauer**: Länge des Videos in Minuten
- **Auflösung**: Pixelanzahl (z.B. 1080p, 4K)
- **Framerate**: Frames pro Sekunde
- **Komplexität**: Anzahl der zu erkennenden Objekte/Personen (geschätzt durch Sampling)

#### Bildanalyse
- **Anzahl**: Menge der zu analysierenden Bilder
- **Auflösung**: Pixelanzahl pro Bild
- **Komplexität**: Detailgrad und Anzahl der zu erkennenden Elemente

#### Audioanalyse
- **Dauer**: Länge der Audiodaten in Minuten
- **Qualität**: Bitrate und Sampling-Rate
- **Sprachanteil**: Geschätzter Anteil von Sprache vs. Umgebungsgeräuschen

### 2.2 Ressourcenparameter

#### GPU-spezifisch
- **GPU-Typ**: Erforderlicher GPU-Typ (z.B. NVIDIA A100, RTX 4090)
- **VRAM-Bedarf**: Geschätzter Speicherbedarf für die Modelle
- **Parallelisierbarkeit**: Möglichkeit zur parallelen Verarbeitung

#### Anbieterparameter
- **Aktuelle Marktpreise**: Echtzeit-Preise verschiedener GPU-Anbieter
- **Verfügbarkeit**: Aktuelle Verfügbarkeit der benötigten GPU-Typen
- **Standort**: Geografischer Standort mit den günstigsten Preisen
- **Spot vs. On-Demand**: Preisunterschiede zwischen Spot- und On-Demand-Instanzen

### 2.3 Berechnungsformel

```python
def calculate_cost_estimate(media_params, resource_params, provider_data):
    # Basiskosten basierend auf Medientyp und Dauer
    if media_params['type'] == 'video':
        base_duration = media_params['duration_minutes']
        resolution_factor = get_resolution_factor(media_params['resolution'])
        complexity_factor = estimate_complexity(media_params['sample_frames'])
        
        # Geschätzte Verarbeitungszeit in Stunden
        processing_time = (base_duration * resolution_factor * complexity_factor) / 60.0
        
    elif media_params['type'] == 'image':
        image_count = media_params['count']
        resolution_factor = get_resolution_factor(media_params['resolution'])
        complexity_factor = estimate_complexity(media_params['sample_images'])
        
        # Geschätzte Verarbeitungszeit in Stunden
        processing_time = (image_count * 0.5 * resolution_factor * complexity_factor) / 60.0
        
    elif media_params['type'] == 'audio':
        base_duration = media_params['duration_minutes']
        speech_factor = 1.0 + (media_params['speech_percentage'] / 100.0)
        
        # Geschätzte Verarbeitungszeit in Stunden
        processing_time = (base_duration * speech_factor) / 60.0
    
    # GPU-Anforderungen
    required_gpu = determine_required_gpu(media_params, resource_params)
    
    # Beste Anbieterauswahl
    provider, hourly_rate = find_best_provider(required_gpu, provider_data)
    
    # Gesamtkostenschätzung
    estimated_cost = processing_time * hourly_rate
    
    # Unsicherheitsfaktor hinzufügen
    uncertainty_margin = 0.2  # 20% Unsicherheitsmarge
    max_estimated_cost = estimated_cost * (1 + uncertainty_margin)
    
    return {
        'estimated_cost': estimated_cost,
        'max_estimated_cost': max_estimated_cost,
        'estimated_duration': processing_time,
        'selected_provider': provider,
        'gpu_type': required_gpu,
        'hourly_rate': hourly_rate
    }
```

## 3. Benutzerinteraktion und Budgetkontrolle

### 3.1 Benutzeroberfläche für Kostenschätzung

```
┌─────────────────────────────────────────────────────────────┐
│  Kostenschätzung für Ihre Medienanalyse                     │
├─────────────────────────────────────────────────────────────┤
│  Medium: Video (1080p, 45 Minuten)                          │
│                                                             │
│  Geschätzte Kosten:                                         │
│    • Minimale Schätzung:    $3.50                           │
│    • Maximale Schätzung:    $4.20                           │
│                                                             │
│  Geschätzte Verarbeitungszeit: 35-40 Minuten                │
│                                                             │
│  Ausgewählter Anbieter: RunPod (A100 GPU)                   │
│                                                             │
│  [ ] Kostenbudget festlegen: $____                          │
│                                                             │
│  [Abbrechen]                [Später ausführen]    [Bestätigen]
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Budgetkontrolle

#### Budgetfestlegung
- **Optionales Kostenbudget**: Benutzer kann ein maximales Budget festlegen
- **Standardbudget**: Systemweite oder benutzerspezifische Standardbudgets
- **Budgetwarnung**: Automatische Warnung, wenn die Schätzung das Budget überschreitet

#### Budgetüberschreitung
- **Automatische Ablehnung**: Jobs werden automatisch abgelehnt, wenn sie das Budget überschreiten
- **Alternativen vorschlagen**: System schlägt kostengünstigere Alternativen vor
  - Reduzierte Auflösung
  - Weniger detaillierte Analyse
  - Günstigere GPU-Typen mit längerer Verarbeitungszeit
- **Genehmigungsprozess**: Optionaler Genehmigungsprozess für Budgetüberschreitungen

## 4. Umgang mit Abweichungen

### 4.1 Überwachung während der Ausführung

- **Echtzeit-Kostentracking**: Kontinuierliche Überwachung der tatsächlichen Kosten
- **Fortschrittsbasierte Neuschätzung**: Aktualisierung der Kostenschätzung basierend auf tatsächlichem Fortschritt
- **Frühwarnsystem**: Benachrichtigung, wenn die tatsächlichen Kosten die Schätzung überschreiten könnten

### 4.2 Kostenüberschreitungsbehandlung

#### Automatische Maßnahmen
- **Soft-Limit (80% des Budgets)**: Warnung an den Benutzer
- **Hard-Limit (100% des Budgets)**:
  - Option 1: Automatischer Abbruch mit Speicherung der Teilergebnisse
  - Option 2: Pausieren und Benutzerabfrage zur Fortsetzung
  - Option 3: Degradation auf kostengünstigere Analyse für den Rest

#### Benutzerbenachrichtigung
```json
{
  "notification_type": "cost_overrun",
  "job_id": "job_12345",
  "original_estimate": 4.20,
  "current_cost": 3.80,
  "projected_final_cost": 5.10,
  "budget": 5.00,
  "progress_percentage": 75,
  "options": [
    {
      "action": "continue",
      "description": "Fortsetzen und Budget überschreiten",
      "estimated_additional_cost": 1.30
    },
    {
      "action": "pause",
      "description": "Pausieren für spätere Fortsetzung",
      "storage_cost_per_day": 0.05
    },
    {
      "action": "degrade",
      "description": "Auf kostengünstigere Analyse umstellen",
      "estimated_final_cost": 4.90,
      "quality_impact": "medium"
    },
    {
      "action": "abort",
      "description": "Abbrechen und Teilergebnisse speichern",
      "refund_amount": 0.00
    }
  ]
}
```

### 4.3 Nachträgliche Analyse

- **Kostenabweichungsbericht**: Detaillierte Analyse der Abweichung zwischen Schätzung und tatsächlichen Kosten
- **Verbesserung des Schätzmodells**: Kontinuierliche Verbesserung der Schätzalgorithmen basierend auf historischen Daten
- **Benutzer-Feedback**: Sammlung von Feedback zur Genauigkeit der Kostenschätzung

## 5. Implementierungsdetails

### 5.1 Kostenschätzungs-Service

```python
class CostEstimationService:
    def __init__(self, provider_api_client, model_registry, historical_data):
        self.provider_api_client = provider_api_client
        self.model_registry = model_registry
        self.historical_data = historical_data
        self.estimation_models = self._load_estimation_models()
    
    def initial_estimate(self, media_file, analysis_config):
        """Erstellt eine initiale Kostenschätzung basierend auf Medieneigenschaften"""
        # Extrahiere Medieneigenschaften
        media_params = self._extract_media_parameters(media_file)
        
        # Bestimme erforderliche Ressourcen basierend auf Analysekonfiguration
        resource_params = self._determine_resource_requirements(analysis_config, media_params)
        
        # Hole aktuelle Anbieterpreise
        provider_data = self.provider_api_client.get_current_pricing()
        
        # Berechne Kostenschätzung
        estimate = calculate_cost_estimate(media_params, resource_params, provider_data)
        
        # Speichere Schätzung für spätere Vergleiche
        self._store_estimate(media_file.id, estimate)
        
        return estimate
    
    def refined_estimate(self, job_id):
        """Erstellt eine verfeinerte Kostenschätzung vor der Ausführung"""
        # Hole ursprüngliche Schätzung
        original_estimate = self._get_stored_estimate(job_id)
        
        # Hole aktuelle Anbieterpreise (könnten sich seit der ersten Schätzung geändert haben)
        current_provider_data = self.provider_api_client.get_current_pricing()
        
        # Aktualisiere die Schätzung mit aktuellen Preisen
        updated_estimate = self._update_estimate_with_current_prices(
            original_estimate, 
            current_provider_data
        )
        
        # Prüfe, ob eine signifikante Abweichung vorliegt
        deviation = self._calculate_deviation(original_estimate, updated_estimate)
        
        # Speichere aktualisierte Schätzung
        self._update_stored_estimate(job_id, updated_estimate, deviation)
        
        return {
            'updated_estimate': updated_estimate,
            'original_estimate': original_estimate,
            'deviation': deviation,
            'requires_confirmation': deviation > 0.2  # 20% Schwellenwert
        }
    
    def track_actual_costs(self, job_id, execution_metrics):
        """Verfolgt die tatsächlichen Kosten während der Ausführung"""
        # Hole gespeicherte Schätzung
        estimate = self._get_stored_estimate(job_id)
        
        # Berechne tatsächliche Kosten basierend auf Ausführungsmetriken
        actual_cost = self._calculate_actual_cost(
            estimate['hourly_rate'],
            execution_metrics['elapsed_time']
        )
        
        # Projiziere Endkosten basierend auf Fortschritt
        projected_cost = self._project_final_cost(
            actual_cost,
            execution_metrics['progress_percentage']
        )
        
        # Prüfe auf Budgetüberschreitung
        budget = self._get_job_budget(job_id)
        budget_status = self._check_budget_status(projected_cost, budget)
        
        return {
            'job_id': job_id,
            'actual_cost': actual_cost,
            'projected_cost': projected_cost,
            'original_estimate': estimate['estimated_cost'],
            'progress': execution_metrics['progress_percentage'],
            'budget': budget,
            'budget_status': budget_status
        }
```

### 5.2 Integration in den Workflow

```python
class MediaAnalysisWorkflow:
    def __init__(self, cost_estimation_service, job_queue, notification_service):
        self.cost_estimation_service = cost_estimation_service
        self.job_queue = job_queue
        self.notification_service = notification_service
    
    def process_media_upload(self, media_file, analysis_config, user):
        """Verarbeitet einen neuen Medien-Upload"""
        # Vorverarbeitung des Mediums
        preprocessed_media = self._preprocess_media(media_file)
        
        # Erstelle initiale Kostenschätzung
        initial_estimate = self.cost_estimation_service.initial_estimate(
            preprocessed_media, 
            analysis_config
        )
        
        # Erstelle Job-Objekt
        job = {
            'id': generate_job_id(),
            'user_id': user.id,
            'media_id': preprocessed_media.id,
            'config': analysis_config,
            'initial_estimate': initial_estimate,
            'status': 'awaiting_confirmation'
        }
        
        # Speichere Job
        self._store_job(job)
        
        # Sende Bestätigungsanfrage an Benutzer
        self.notification_service.send_cost_confirmation(
            user,
            job['id'],
            initial_estimate
        )
        
        return job
    
    def handle_cost_confirmation(self, job_id, user_decision, budget=None):
        """Verarbeitet die Benutzerentscheidung zur Kostenschätzung"""
        # Hole Job-Informationen
        job = self._get_job(job_id)
        
        if user_decision == 'confirm':
            # Setze optionales Budget
            if budget is not None:
                job['budget'] = budget
            
            # Aktualisiere Job-Status
            job['status'] = 'queued'
            self._update_job(job)
            
            # Füge Job zur Warteschlange hinzu
            self.job_queue.enqueue(job)
            
            return {'status': 'queued', 'job_id': job_id}
            
        elif user_decision == 'schedule':
            # Plane Job für späteren Zeitpunkt
            scheduled_time = self._determine_optimal_time(job)
            
            job['status'] = 'scheduled'
            job['scheduled_time'] = scheduled_time
            self._update_job(job)
            
            return {'status': 'scheduled', 'job_id': job_id, 'scheduled_time': scheduled_time}
            
        elif user_decision == 'cancel':
            # Breche Job ab
            job['status'] = 'cancelled'
            self._update_job(job)
            
            # Bereinige temporäre Daten
            self._cleanup_temp_data(job)
            
            return {'status': 'cancelled', 'job_id': job_id}
    
    def prepare_job_execution(self, job_id):
        """Bereitet einen Job für die Ausführung vor"""
        # Hole Job-Informationen
        job = self._get_job(job_id)
        
        # Erstelle verfeinerte Kostenschätzung
        refined_estimate = self.cost_estimation_service.refined_estimate(job_id)
        
        # Aktualisiere Job mit verfeinerter Schätzung
        job['refined_estimate'] = refined_estimate['updated_estimate']
        self._update_job(job)
        
        # Prüfe, ob Benutzerbestätigung erforderlich ist
        if refined_estimate['requires_confirmation']:
            # Ändere Status und sende Benachrichtigung
            job['status'] = 'awaiting_reconfirmation'
            self._update_job(job)
            
            self.notification_service.send_cost_update_confirmation(
                self._get_user(job['user_id']),
                job_id,
                refined_estimate
            )
            
            return {'status': 'awaiting_reconfirmation', 'job_id': job_id}
        
        # Fahre mit der Ausführung fort
        return self._proceed_to_execution(job)
    
    def _proceed_to_execution(self, job):
        """Fährt mit der Job-Ausführung fort"""
        # Aktualisiere Job-Status
        job['status'] = 'executing'
        job['execution_start_time'] = datetime.now()
        self._update_job(job)
        
        # Starte Kostenüberwachung
        self._start_cost_monitoring(job['id'])
        
        # Weise GPU-Ressourcen zu und starte Ausführung
        execution_id = self._allocate_resources_and_execute(job)
        
        return {'status': 'executing', 'job_id': job['id'], 'execution_id': execution_id}
    
    def _start_cost_monitoring(self, job_id):
        """Startet die Kostenüberwachung für einen Job"""
        # Starte Hintergrundprozess zur Kostenüberwachung
        monitoring_task = BackgroundTask(
            task_function=self._monitor_job_costs,
            task_args=(job_id,),
            interval_seconds=60  # Überprüfe Kosten jede Minute
        )
        
        monitoring_task.start()
    
    def _monitor_job_costs(self, job_id):
        """Überwacht die Kosten eines laufenden Jobs"""
        # Hole aktuelle Ausführungsmetriken
        execution_metrics = self._get_execution_metrics(job_id)
        
        # Aktualisiere Kostentracking
        cost_tracking = self.cost_estimation_service.track_actual_costs(
            job_id,
            execution_metrics
        )
        
        # Prüfe auf Budgetüberschreitungen
        if cost_tracking['budget_status'] == 'approaching_limit':
            # Sende Warnung
            self._send_budget_warning(job_id, cost_tracking)
            
        elif cost_tracking['budget_status'] == 'exceeded':
            # Behandle Budgetüberschreitung
            self._handle_budget_exceeded(job_id, cost_tracking)
```

## 6. Anbieterübergreifende Optimierung

### 6.1 Preisvergleich in Echtzeit

- **API-Integration**: Direkte Integration mit APIs von RunPod, Vast.ai und anderen Anbietern
- **Preishistorie**: Speicherung historischer Preisdaten für Trendanalysen
- **Preisvolatilität**: Berücksichtigung der Preisvolatilität bei der Anbieterauswahl

### 6.2 Optimierungsstrategien

#### Zeitbasierte Optimierung
- **Tageszeit-Analyse**: Identifikation von Zeiten mit niedrigeren Preisen
- **Wochentag-Muster**: Berücksichtigung von Preisunterschieden zwischen Wochentagen
- **Automatische Planung**: Verschiebung nicht-dringender Jobs in kostengünstigere Zeitfenster

#### Anbieterbasierte Optimierung
- **Multi-Anbieter-Strategie**: Verteilung von Jobs auf verschiedene Anbieter
- **Anbieter-Zuverlässigkeit**: Berücksichtigung historischer Zuverlässigkeitsdaten
- **Standortoptimierung**: Auswahl des kostengünstigsten Standorts pro Anbieter

## 7. Berichterstattung und Analyse

### 7.1 Kostenberichte

- **Job-spezifische Berichte**: Detaillierte Kostenaufschlüsselung pro Job
- **Benutzerberichte**: Kostenübersicht für alle Jobs eines Benutzers
- **Systemweite Berichte**: Gesamtkostenanalyse für Administratoren

### 7.2 Kostenoptimierungsvorschläge

- **Automatische Empfehlungen**: Vorschläge zur Kostenreduzierung
- **Vergleichsanalyse**: Vergleich mit ähnlichen Jobs und deren Kosten
- **Trend-Analyse**: Identifikation von Kostentrends und Optimierungspotentialen

### 7.3 Beispiel-Kostenbericht

```json
{
  "job_id": "job_12345",
  "media_type": "video",
  "duration": "45 minutes",
  "resolution": "1080p",
  
  "cost_summary": {
    "initial_estimate": 4.20,
    "refined_estimate": 4.35,
    "actual_cost": 4.15,
    "deviation_percentage": -4.6
  },
  
  "resource_usage": {
    "gpu_type": "NVIDIA A100",
    "provider": "RunPod",
    "execution_time": "38 minutes",
    "hourly_rate": 6.55
  },
  
  "cost_breakdown": {
    "video_analysis": 2.80,
    "audio_analysis": 0.95,
    "data_fusion": 0.40
  },
  
  "optimization_suggestions": [
    {
      "suggestion": "Reduzierte Auflösung",
      "potential_savings": 0.85,
      "quality_impact": "minimal"
    },
    {
      "suggestion": "Nacht-Ausführung",
      "potential_savings": 1.20,
      "time_impact": "8-12 Stunden Verzögerung"
    }
  ]
}
```

## 8. Datenschutz und Compliance

### 8.1 Transparenz der Kostenberechnung

- **Detaillierte Aufschlüsselung**: Transparente Darstellung aller Kostenfaktoren
- **Nachvollziehbarkeit**: Klare Dokumentation der Berechnungsmethodik
- **Historische Daten**: Zugriff auf historische Kostendaten für Audits

### 8.2 Budgetkontrolle für Organisationen

- **Organisationsbudgets**: Definition von Budgets auf Organisationsebene
- **Benutzerbudgets**: Zuweisung von Teilbudgets an einzelne Benutzer
- **Genehmigungsworkflows**: Mehrstufige Genehmigungsprozesse für Budgetüberschreitungen
- **Kostenstellenzuordnung**: Zuordnung von Kosten zu internen Kostenstellen