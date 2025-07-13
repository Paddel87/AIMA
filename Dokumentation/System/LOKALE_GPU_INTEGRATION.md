# Integration lokaler GPUs in den AIMA-Workflow

Dieses Dokument spezifiziert, wie lokale GPUs in den AIMA-Workflow integriert werden und wie das System zwischen lokalen und Cloud-GPUs entscheidet.

## 1. Entscheidungskriterien für die GPU-Auswahl

### 1.1 Primäre Entscheidungsfaktoren

#### Leistungsanforderungen
- **Minimale VRAM-Anforderungen**:
  - Videoanalyse: Mindestens 24 GB VRAM
  - Bildanalyse: Mindestens 16 GB VRAM
  - Audioanalyse: Mindestens 8 GB VRAM
- **Rechenleistung**: Erforderliche CUDA-Kerne/Tensor-Kerne für die Analyse
- **Modellkompatibilität**: Unterstützung für die benötigten ML-Modelle

#### Datenschutzanforderungen
- **Vertraulichkeitsstufe**: Klassifizierung der zu analysierenden Daten
  - Stufe 1 (Öffentlich): Cloud-GPUs bevorzugt
  - Stufe 2 (Intern): Cloud oder lokale GPUs
  - Stufe 3 (Vertraulich): Nur lokale GPUs
- **Regulatorische Anforderungen**: Einhaltung von DSGVO, HIPAA, etc.
- **Datenresidenz**: Anforderungen an den physischen Speicherort der Daten

#### Kostenoptimierung
- **Kostenvergleich**: Lokale vs. Cloud-Kosten für die spezifische Analyse
- **Auslastungsgrad**: Aktuelle Auslastung der lokalen GPUs
- **Energiekosten**: Berücksichtigung lokaler Stromkosten

### 1.2 Entscheidungsmatrix

| Faktor | Gewichtung | Lokale GPU bevorzugt wenn | Cloud-GPU bevorzugt wenn |
|--------|------------|---------------------------|---------------------------|
| VRAM-Anforderung | Hoch | Lokale GPU hat ausreichend VRAM | Lokale GPU hat unzureichend VRAM |
| Datenschutz | Hoch | Hohe Vertraulichkeit | Niedrige Vertraulichkeit |
| Verfügbarkeit | Mittel | Sofort verfügbar | Lokale Warteschlange > 1 Stunde |
| Kosten | Mittel | Günstiger als Cloud | Günstiger als lokal |
| Dringlichkeit | Niedrig | Niedrige Dringlichkeit | Hohe Dringlichkeit bei lokaler Warteschlange |
| Netzwerkbandbreite | Niedrig | Große Mediendateien, begrenzte Upload-Bandbreite | Kleine Mediendateien oder hohe Upload-Bandbreite |

### 1.3 Entscheidungsalgorithmus

```python
def select_gpu_environment(job_requirements, local_gpus, cloud_providers):
    """Wählt zwischen lokalen und Cloud-GPUs basierend auf Job-Anforderungen"""
    # Extrahiere Job-Anforderungen
    vram_required = job_requirements.get('vram_required', 0)
    data_confidentiality = job_requirements.get('data_confidentiality', 'public')
    urgency_level = job_requirements.get('urgency_level', 'normal')
    media_size = job_requirements.get('media_size_gb', 0)
    
    # Prüfe Datenschutzanforderungen (höchste Priorität)
    if data_confidentiality == 'confidential':
        # Für vertrauliche Daten nur lokale GPUs verwenden
        suitable_gpus = filter_suitable_local_gpus(local_gpus, vram_required)
        if not suitable_gpus:
            return {
                'decision': 'error',
                'reason': 'No suitable local GPU for confidential data',
                'alternatives': suggest_alternatives(job_requirements)
            }
        return {
            'decision': 'local',
            'selected_gpu': select_best_local_gpu(suitable_gpus, job_requirements)
        }
    
    # Prüfe VRAM-Anforderungen
    suitable_local_gpus = filter_suitable_local_gpus(local_gpus, vram_required)
    
    # Wenn keine geeignete lokale GPU verfügbar ist, verwende Cloud
    if not suitable_local_gpus:
        return {
            'decision': 'cloud',
            'selected_provider': select_best_cloud_provider(cloud_providers, job_requirements)
        }
    
    # Prüfe Verfügbarkeit und Warteschlange
    local_queue_time = estimate_local_queue_time(suitable_local_gpus)
    if urgency_level == 'high' and local_queue_time > 60:  # 60 Minuten
        return {
            'decision': 'cloud',
            'reason': 'High urgency, local queue too long',
            'selected_provider': select_best_cloud_provider(cloud_providers, job_requirements)
        }
    
    # Kostenvergleich
    local_cost = estimate_local_cost(suitable_local_gpus, job_requirements)
    cloud_cost = estimate_cloud_cost(cloud_providers, job_requirements)
    
    # Berücksichtige Netzwerkbandbreite bei großen Mediendateien
    if media_size > 10 and cloud_cost < local_cost * 1.2:  # 20% Toleranz
        upload_time = estimate_upload_time(media_size)
        if upload_time > 30:  # 30 Minuten
            return {
                'decision': 'local',
                'reason': 'Large media size, upload would take too long',
                'selected_gpu': select_best_local_gpu(suitable_local_gpus, job_requirements)
            }
    
    # Finale Entscheidung basierend auf Kosten
    if local_cost <= cloud_cost * 1.1:  # 10% Toleranz zugunsten lokaler GPUs
        return {
            'decision': 'local',
            'reason': 'Cost-effective local option available',
            'selected_gpu': select_best_local_gpu(suitable_local_gpus, job_requirements),
            'estimated_cost': local_cost
        }
    else:
        return {
            'decision': 'cloud',
            'reason': 'Cloud option more cost-effective',
            'selected_provider': select_best_cloud_provider(cloud_providers, job_requirements),
            'estimated_cost': cloud_cost
        }
```

## 2. Registrierung und Verwaltung lokaler GPUs

### 2.1 Registrierungsprozess

#### Manuelle Registrierung
- **Administratorschnittstelle**: Web-UI für die Registrierung neuer GPUs
- **Erforderliche Informationen**:
  - GPU-Modell und Spezifikationen (VRAM, CUDA-Version, etc.)
  - Physischer Standort und Netzwerkanbindung
  - Verfügbarkeitszeiten (24/7 oder bestimmte Zeitfenster)
  - Zugriffsbeschränkungen und Berechtigungen

#### Automatische Erkennung
- **Netzwerk-Discovery**: Automatische Erkennung von GPUs im lokalen Netzwerk
- **Agent-basierte Registrierung**: Leichtgewichtiger Agent auf GPU-Hosts
- **Benchmark-Tests**: Automatische Leistungsmessung bei der Registrierung

### 2.2 GPU-Ressourcenverwaltung

```python
class LocalGPUManager:
    def __init__(self, database_client):
        self.db = database_client
        self.gpu_agents = {}
        self.monitoring_interval = 60  # Sekunden
    
    def register_gpu(self, gpu_info):
        """Registriert eine neue lokale GPU"""
        # Validiere GPU-Informationen
        if not self._validate_gpu_info(gpu_info):
            return {'status': 'error', 'message': 'Invalid GPU information'}
        
        # Generiere eindeutige GPU-ID
        gpu_id = f"gpu_{uuid.uuid4().hex[:8]}"
        
        # Führe Benchmark-Tests durch, wenn möglich
        if gpu_info.get('run_benchmarks', True):
            benchmark_results = self._run_benchmarks(gpu_info['host_address'])
            gpu_info['benchmark_results'] = benchmark_results
        
        # Speichere GPU-Informationen in der Datenbank
        gpu_record = {
            'gpu_id': gpu_id,
            'model': gpu_info['model'],
            'vram_gb': gpu_info['vram_gb'],
            'cuda_version': gpu_info['cuda_version'],
            'host_address': gpu_info['host_address'],
            'location': gpu_info['location'],
            'availability_schedule': gpu_info.get('availability_schedule', '24/7'),
            'access_restrictions': gpu_info.get('access_restrictions', []),
            'benchmark_results': gpu_info.get('benchmark_results', {}),
            'status': 'available',
            'registered_at': datetime.now(),
            'last_seen': datetime.now()
        }
        
        self.db.gpus.insert_one(gpu_record)
        
        # Starte Monitoring für die GPU
        self._start_monitoring(gpu_id, gpu_info['host_address'])
        
        return {'status': 'success', 'gpu_id': gpu_id}
    
    def update_gpu_status(self, gpu_id, status_info):
        """Aktualisiert den Status einer GPU"""
        # Validiere Status-Informationen
        if not self._validate_status_info(status_info):
            return {'status': 'error', 'message': 'Invalid status information'}
        
        # Aktualisiere GPU-Status in der Datenbank
        update_data = {
            'status': status_info['status'],
            'last_seen': datetime.now(),
            'current_load': status_info.get('current_load', 0),
            'temperature': status_info.get('temperature', 0),
            'memory_used': status_info.get('memory_used', 0),
            'current_processes': status_info.get('current_processes', [])
        }
        
        self.db.gpus.update_one(
            {'gpu_id': gpu_id},
            {'$set': update_data}
        )
        
        return {'status': 'success'}
    
    def list_available_gpus(self, requirements=None):
        """Listet verfügbare GPUs auf, optional gefiltert nach Anforderungen"""
        query = {'status': 'available'}
        
        # Füge Anforderungsfilter hinzu, wenn vorhanden
        if requirements:
            if 'min_vram_gb' in requirements:
                query['vram_gb'] = {'$gte': requirements['min_vram_gb']}
            
            if 'cuda_version' in requirements:
                query['cuda_version'] = {'$gte': requirements['cuda_version']}
            
            if 'access_level' in requirements:
                query['access_restrictions'] = {
                    '$not': {'$elemMatch': {'$nin': requirements['access_level']}}
                }
        
        # Führe Datenbankabfrage durch
        available_gpus = list(self.db.gpus.find(query))
        
        return available_gpus
    
    def allocate_gpu(self, job_id, gpu_id, allocation_details):
        """Reserviert eine GPU für einen bestimmten Job"""
        # Prüfe, ob GPU verfügbar ist
        gpu = self.db.gpus.find_one({'gpu_id': gpu_id, 'status': 'available'})
        if not gpu:
            return {'status': 'error', 'message': 'GPU not available'}
        
        # Erstelle Allokationsdatensatz
        allocation = {
            'job_id': job_id,
            'gpu_id': gpu_id,
            'allocated_at': datetime.now(),
            'estimated_duration': allocation_details.get('estimated_duration', 3600),
            'priority': allocation_details.get('priority', 'normal'),
            'allocated_memory': allocation_details.get('required_memory', 0),
            'status': 'allocated'
        }
        
        # Speichere Allokation in der Datenbank
        self.db.gpu_allocations.insert_one(allocation)
        
        # Aktualisiere GPU-Status
        self.db.gpus.update_one(
            {'gpu_id': gpu_id},
            {'$set': {'status': 'allocated', 'allocated_to': job_id}}
        )
        
        # Sende Allokationsbefehl an GPU-Agent
        self._send_allocation_command(gpu_id, job_id, allocation_details)
        
        return {'status': 'success', 'allocation_id': str(allocation['_id'])}
    
    def release_gpu(self, gpu_id, job_id):
        """Gibt eine GPU nach Abschluss eines Jobs frei"""
        # Prüfe, ob GPU für diesen Job allokiert ist
        allocation = self.db.gpu_allocations.find_one({
            'gpu_id': gpu_id,
            'job_id': job_id,
            'status': 'allocated'
        })
        
        if not allocation:
            return {'status': 'error', 'message': 'No matching allocation found'}
        
        # Aktualisiere Allokationsstatus
        self.db.gpu_allocations.update_one(
            {'_id': allocation['_id']},
            {'$set': {
                'status': 'completed',
                'released_at': datetime.now(),
                'actual_duration': (datetime.now() - allocation['allocated_at']).total_seconds()
            }}
        )
        
        # Aktualisiere GPU-Status
        self.db.gpus.update_one(
            {'gpu_id': gpu_id},
            {'$set': {'status': 'available'}, '$unset': {'allocated_to': 1}}
        )
        
        # Sende Freigabebefehl an GPU-Agent
        self._send_release_command(gpu_id, job_id)
        
        return {'status': 'success'}
```

### 2.3 GPU-Agent-Architektur

```python
class GPUAgent:
    def __init__(self, config):
        self.config = config
        self.gpu_manager_url = config['gpu_manager_url']
        self.agent_id = config['agent_id']
        self.host_info = self._collect_host_info()
        self.gpus = self._detect_gpus()
        self.registered_gpus = {}
        self.active_jobs = {}
        
    def start(self):
        """Startet den GPU-Agenten"""
        # Registriere GPUs beim Manager
        self._register_gpus()
        
        # Starte Monitoring-Thread
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        # Starte API-Server für eingehende Befehle
        self.api_server = APIServer(self)
        self.api_server.start()
        
        logging.info(f"GPU Agent started with {len(self.gpus)} GPUs")
    
    def _detect_gpus(self):
        """Erkennt verfügbare GPUs auf dem Host"""
        detected_gpus = []
        
        try:
            # Verwende NVIDIA Management Library (NVML) zur GPU-Erkennung
            import pynvml
            pynvml.nvmlInit()
            
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                device_info = pynvml.nvmlDeviceGetName(handle)
                
                gpu = {
                    'local_index': i,
                    'model': device_info.decode('utf-8'),
                    'vram_total': info.total,
                    'vram_gb': info.total / (1024**3),
                    'uuid': pynvml.nvmlDeviceGetUUID(handle).decode('utf-8')
                }
                
                detected_gpus.append(gpu)
            
            pynvml.nvmlShutdown()
            
        except Exception as e:
            logging.error(f"Error detecting GPUs: {str(e)}")
        
        return detected_gpus
    
    def _register_gpus(self):
        """Registriert erkannte GPUs beim GPU-Manager"""
        for gpu in self.gpus:
            registration_data = {
                'model': gpu['model'],
                'vram_gb': gpu['vram_gb'],
                'cuda_version': self._get_cuda_version(),
                'host_address': self.host_info['ip_address'],
                'location': self.config.get('location', 'unknown'),
                'availability_schedule': self.config.get('availability_schedule', '24/7'),
                'access_restrictions': self.config.get('access_restrictions', []),
                'agent_id': self.agent_id,
                'gpu_uuid': gpu['uuid']
            }
            
            try:
                response = requests.post(
                    f"{self.gpu_manager_url}/register",
                    json=registration_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result['status'] == 'success':
                        gpu_id = result['gpu_id']
                        self.registered_gpus[gpu_id] = gpu
                        logging.info(f"GPU {gpu['model']} registered with ID {gpu_id}")
                    else:
                        logging.error(f"Failed to register GPU: {result['message']}")
                else:
                    logging.error(f"Failed to register GPU, status code: {response.status_code}")
                    
            except Exception as e:
                logging.error(f"Error registering GPU: {str(e)}")
    
    def _monitoring_loop(self):
        """Kontinuierliches Monitoring der GPUs"""
        while True:
            for gpu_id, gpu in self.registered_gpus.items():
                try:
                    # Sammle aktuelle GPU-Metriken
                    metrics = self._collect_gpu_metrics(gpu['local_index'])
                    
                    # Sende Status-Update an Manager
                    self._send_status_update(gpu_id, metrics)
                    
                except Exception as e:
                    logging.error(f"Error monitoring GPU {gpu_id}: {str(e)}")
            
            # Warte vor dem nächsten Monitoring-Zyklus
            time.sleep(self.config.get('monitoring_interval', 60))
    
    def _collect_gpu_metrics(self, gpu_index):
        """Sammelt Metriken für eine bestimmte GPU"""
        metrics = {}
        
        try:
            import pynvml
            pynvml.nvmlInit()
            
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            
            # Speichernutzung
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            metrics['memory_total'] = memory.total
            metrics['memory_used'] = memory.used
            metrics['memory_free'] = memory.free
            metrics['memory_used_percent'] = (memory.used / memory.total) * 100
            
            # GPU-Auslastung
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            metrics['gpu_utilization'] = utilization.gpu
            metrics['memory_utilization'] = utilization.memory
            
            # Temperatur
            metrics['temperature'] = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            
            # Stromverbrauch
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW zu W
                metrics['power_usage'] = power
            except:
                metrics['power_usage'] = 0
            
            # Aktive Prozesse
            processes = []
            try:
                for proc in pynvml.nvmlDeviceGetComputeRunningProcesses(handle):
                    process_info = {
                        'pid': proc.pid,
                        'memory_used': proc.usedGpuMemory
                    }
                    try:
                        process_name = pynvml.nvmlSystemGetProcessName(proc.pid)
                        process_info['name'] = process_name.decode('utf-8')
                    except:
                        process_info['name'] = 'unknown'
                    
                    processes.append(process_info)
            except:
                pass
            
            metrics['processes'] = processes
            
            # Status bestimmen
            if metrics['gpu_utilization'] > 80 or metrics['memory_used_percent'] > 80:
                metrics['status'] = 'busy'
            elif metrics['gpu_utilization'] > 20 or metrics['memory_used_percent'] > 20:
                metrics['status'] = 'active'
            else:
                metrics['status'] = 'idle'
            
            pynvml.nvmlShutdown()
            
        except Exception as e:
            logging.error(f"Error collecting GPU metrics: {str(e)}")
            metrics['status'] = 'error'
            metrics['error'] = str(e)
        
        return metrics
```

## 3. Umgang mit unterschiedlichen Leistungsmerkmalen

### 3.1 GPU-Leistungsprofilierung

#### Benchmark-Tests
- **Standardisierte Tests**: Ausführung von ML-Benchmark-Tests bei der Registrierung
- **Modellspezifische Tests**: Leistungsmessung mit den tatsächlich verwendeten Modellen
- **Leistungsmetriken**:
  - Inferenzzeit pro Bild/Frame/Audioclip
  - Maximale Batch-Größe
  - Speicherverbrauch pro Modell
  - Energieeffizienz (Inferenzen pro Watt)

#### Leistungsprofil-Beispiel
```json
{
  "gpu_id": "gpu_a1b2c3d4",
  "model": "NVIDIA RTX 4090",
  "benchmark_results": {
    "general": {
      "fp32_gflops": 82580,
      "fp16_gflops": 165160,
      "memory_bandwidth_gbps": 1008
    },
    "model_specific": {
      "yolov8x": {
        "inference_time_ms": 12.5,
        "max_batch_size": 16,
        "memory_usage_mb": 4200,
        "throughput_fps": 80
      },
      "whisper_large": {
        "inference_time_ms": 850,
        "max_batch_size": 4,
        "memory_usage_mb": 10500,
        "throughput_factor": 1.2
      }
    }
  }
}
```

### 3.2 Dynamische Workload-Anpassung

#### Modellskalierung
- **Automatische Modellauswahl**: Auswahl des optimalen Modells basierend auf verfügbarer GPU-Leistung
- **Quantisierung**: Dynamische Quantisierung (FP32 → FP16 → INT8) je nach GPU-Unterstützung
- **Modellvarianten**: Verwendung von Modellvarianten unterschiedlicher Größe (z.B. YOLOv8n bis YOLOv8x)

#### Batch-Größen-Optimierung
- **Dynamische Batch-Größen**: Anpassung der Batch-Größe an die verfügbare GPU-Leistung
- **Speicheroptimierung**: Gradient Checkpointing und andere Techniken für große Modelle
- **Parallele Verarbeitung**: Aufteilung der Verarbeitung auf mehrere GPUs, wenn verfügbar

```python
class AdaptiveModelSelector:
    def __init__(self, model_registry):
        self.model_registry = model_registry
        self.performance_cache = {}
    
    def select_optimal_model(self, task_type, gpu_profile, job_requirements):
        """Wählt das optimale Modell basierend auf GPU-Profil und Anforderungen"""
        # Hole verfügbare Modelle für den Task-Typ
        available_models = self.model_registry.get_models(task_type)
        
        # Filtere Modelle nach Mindestanforderungen
        if 'min_accuracy' in job_requirements:
            available_models = [m for m in available_models 
                               if m['accuracy'] >= job_requirements['min_accuracy']]
        
        if not available_models:
            return None
        
        # Sortiere Modelle nach Leistung auf der spezifischen GPU
        ranked_models = self._rank_models_for_gpu(available_models, gpu_profile)
        
        # Wähle das beste Modell aus, das auf die GPU passt
        for model in ranked_models:
            if self._can_fit_on_gpu(model, gpu_profile):
                # Bestimme optimale Batch-Größe
                optimal_batch_size = self._determine_optimal_batch_size(
                    model, gpu_profile, job_requirements
                )
                
                # Bestimme optimale Präzision
                optimal_precision = self._determine_optimal_precision(
                    model, gpu_profile
                )
                
                return {
                    'model_id': model['id'],
                    'model_name': model['name'],
                    'model_version': model['version'],
                    'batch_size': optimal_batch_size,
                    'precision': optimal_precision,
                    'estimated_throughput': self._estimate_throughput(
                        model, gpu_profile, optimal_batch_size, optimal_precision
                    )
                }
        
        # Wenn kein Modell passt, versuche Fallback-Optionen
        return self._find_fallback_option(available_models, gpu_profile, job_requirements)
    
    def _rank_models_for_gpu(self, models, gpu_profile):
        """Sortiert Modelle nach ihrer Leistung auf der spezifischen GPU"""
        # Erstelle Leistungsbewertung für jedes Modell
        model_scores = []
        
        for model in models:
            # Prüfe, ob wir Benchmark-Daten für dieses Modell auf dieser GPU haben
            cache_key = f"{model['id']}_{gpu_profile['gpu_id']}"
            
            if cache_key in self.performance_cache:
                # Verwende gecachte Leistungsdaten
                performance = self.performance_cache[cache_key]
            elif model['id'] in gpu_profile.get('benchmark_results', {}).get('model_specific', {}):
                # Verwende Benchmark-Ergebnisse aus dem GPU-Profil
                performance = gpu_profile['benchmark_results']['model_specific'][model['id']]
                self.performance_cache[cache_key] = performance
            else:
                # Schätze Leistung basierend auf Modellparametern und GPU-Spezifikationen
                performance = self._estimate_model_performance(model, gpu_profile)
                self.performance_cache[cache_key] = performance
            
            # Berechne Gesamtpunktzahl basierend auf Leistung und Genauigkeit
            throughput_score = performance.get('throughput_fps', 0)
            accuracy_score = model.get('accuracy', 0) * 100
            
            # Gewichtete Punktzahl (kann an Prioritäten angepasst werden)
            total_score = (throughput_score * 0.7) + (accuracy_score * 0.3)
            
            model_scores.append((model, total_score))
        
        # Sortiere nach Punktzahl (absteigend)
        model_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Gib sortierte Modelle zurück
        return [m[0] for m in model_scores]
```

## 4. Failover-Mechanismen

### 4.1 Erkennung von Nichtverfügbarkeit

#### Überwachungssystem
- **Heartbeat-Mechanismus**: Regelmäßige Statusprüfungen (alle 30 Sekunden)
- **Fehlerklassifizierung**:
  - Temporäre Fehler: Kurzzeitige Nichtverfügbarkeit
  - Persistente Fehler: Längerfristige Ausfälle
  - Kritische Fehler: Hardware-Defekte oder schwerwiegende Probleme

#### Automatische Diagnose
- **Selbstheilungsversuche**: Automatische Neustartversuche bei temporären Fehlern
- **Diagnoseprotokolle**: Detaillierte Fehlerprotokolle für manuelle Diagnose
- **Fehlervorhersage**: Präventive Erkennung potenzieller Probleme (z.B. steigende Temperaturen)

### 4.2 Failover-Strategien

#### Lokaler Failover
- **GPU-Rotation**: Automatischer Wechsel zu einer anderen lokalen GPU
- **Prioritätsbasierte Umverteilung**: Verschiebung von Jobs mit niedrigerer Priorität
- **Teilweise Ausführung**: Fortsetzung mit reduzierter Leistung (z.B. weniger Modelle)

#### Cloud-Failover
- **Automatische Migration**: Verlagerung von Jobs in die Cloud bei lokalen Ausfällen
- **Hybride Ausführung**: Verteilung der Workload zwischen lokalen und Cloud-Ressourcen
- **Notfall-Skalierung**: Schnelle Bereitstellung zusätzlicher Cloud-Ressourcen

```python
class FailoverManager:
    def __init__(self, local_gpu_manager, cloud_provider_manager, job_manager):
        self.local_gpu_manager = local_gpu_manager
        self.cloud_provider_manager = cloud_provider_manager
        self.job_manager = job_manager
        self.failover_history = {}
    
    def handle_gpu_failure(self, gpu_id, failure_info):
        """Behandelt den Ausfall einer GPU"""
        # Protokolliere Ausfall
        logging.error(f"GPU failure detected: {gpu_id}, reason: {failure_info['reason']}")
        
        # Hole betroffene Jobs
        affected_jobs = self.job_manager.get_jobs_by_gpu(gpu_id)
        
        if not affected_jobs:
            logging.info(f"No active jobs affected by GPU {gpu_id} failure")
            return {'status': 'success', 'affected_jobs': 0}
        
        # Klassifiziere Fehler
        failure_type = self._classify_failure(failure_info)
        
        # Behandle jeden betroffenen Job
        results = []
        for job in affected_jobs:
            result = self._handle_job_failover(job, failure_type)
            results.append(result)
            
            # Aktualisiere Failover-Historie
            self._update_failover_history(job['job_id'], gpu_id, failure_type, result)
        
        # Aktualisiere GPU-Status
        self._update_gpu_status(gpu_id, failure_type, failure_info)
        
        return {
            'status': 'success',
            'affected_jobs': len(affected_jobs),
            'results': results
        }
    
    def _classify_failure(self, failure_info):
        """Klassifiziert den Fehlertyp"""
        reason = failure_info.get('reason', '')
        duration = failure_info.get('duration_seconds', 0)
        
        if 'hardware' in reason.lower() or 'critical' in reason.lower():
            return 'critical'
        elif duration > 300 or 'persistent' in reason.lower():  # > 5 Minuten
            return 'persistent'
        else:
            return 'temporary'
    
    def _handle_job_failover(self, job, failure_type):
        """Behandelt Failover für einen einzelnen Job"""
        job_id = job['job_id']
        logging.info(f"Handling failover for job {job_id}, failure type: {failure_type}")
        
        # Speichere aktuellen Job-Zustand für Wiederaufnahme
        checkpoint = self.job_manager.create_checkpoint(job_id)
        
        # Bestimme Failover-Strategie basierend auf Fehlertyp und Job-Priorität
        if failure_type == 'temporary' and job['priority'] != 'high':
            # Bei temporären Fehlern und nicht-kritischen Jobs: Warte und versuche erneut
            return self._retry_on_same_gpu(job, checkpoint)
            
        elif failure_type == 'temporary' and job['priority'] == 'high':
            # Bei temporären Fehlern und kritischen Jobs: Lokaler Failover
            return self._local_gpu_failover(job, checkpoint)
            
        elif failure_type == 'persistent':
            # Bei persistenten Fehlern: Versuche lokalen Failover, dann Cloud
            local_result = self._local_gpu_failover(job, checkpoint)
            
            if local_result['status'] != 'success':
                return self._cloud_failover(job, checkpoint)
            return local_result
            
        elif failure_type == 'critical':
            # Bei kritischen Fehlern: Direkt zu Cloud-Failover
            return self._cloud_failover(job, checkpoint)
        
        # Fallback
        return {'status': 'error', 'message': 'No suitable failover strategy'}
    
    def _retry_on_same_gpu(self, job, checkpoint):
        """Wartet und versucht die Ausführung auf derselben GPU erneut"""
        gpu_id = job['allocated_gpu']
        
        # Plane Wiederholungsversuch
        retry_delay = 60  # 1 Minute
        
        self.job_manager.schedule_retry({
            'job_id': job['job_id'],
            'gpu_id': gpu_id,
            'checkpoint': checkpoint,
            'retry_time': datetime.now() + timedelta(seconds=retry_delay),
            'attempt': job.get('retry_attempt', 0) + 1
        })
        
        return {
            'status': 'scheduled_retry',
            'gpu_id': gpu_id,
            'retry_delay': retry_delay
        }
    
    def _local_gpu_failover(self, job, checkpoint):
        """Versucht, den Job auf eine andere lokale GPU zu verschieben"""
        # Suche alternative lokale GPU
        requirements = job['resource_requirements']
        alternative_gpus = self.local_gpu_manager.find_alternative_gpus(requirements)
        
        if not alternative_gpus:
            return {'status': 'error', 'message': 'No alternative local GPUs available'}
        
        # Wähle beste alternative GPU
        new_gpu = alternative_gpus[0]  # Einfachste Implementierung: nimm die erste
        
        # Allokiere neue GPU und starte Job neu
        allocation_result = self.local_gpu_manager.allocate_gpu(
            job['job_id'], 
            new_gpu['gpu_id'],
            job['allocation_details']
        )
        
        if allocation_result['status'] != 'success':
            return {'status': 'error', 'message': 'Failed to allocate alternative GPU'}
        
        # Starte Job auf neuer GPU
        restart_result = self.job_manager.restart_from_checkpoint(
            job['job_id'],
            new_gpu['gpu_id'],
            checkpoint
        )
        
        return {
            'status': 'success',
            'strategy': 'local_failover',
            'old_gpu': job['allocated_gpu'],
            'new_gpu': new_gpu['gpu_id'],
            'restart_result': restart_result
        }
    
    def _cloud_failover(self, job, checkpoint):
        """Migriert den Job in die Cloud"""
        # Prüfe Datenschutzanforderungen
        if job.get('data_confidentiality', 'public') == 'confidential':
            return {'status': 'error', 'message': 'Cannot migrate confidential data to cloud'}
        
        # Wähle Cloud-Anbieter
        provider_result = self.cloud_provider_manager.select_provider(job['resource_requirements'])
        
        if provider_result['status'] != 'success':
            return {'status': 'error', 'message': 'Failed to select cloud provider'}
        
        # Bereite Cloud-Migration vor
        migration_result = self.job_manager.prepare_cloud_migration(job['job_id'], checkpoint)
        
        if migration_result['status'] != 'success':
            return {'status': 'error', 'message': 'Failed to prepare cloud migration'}
        
        # Starte Job in der Cloud
        cloud_job = self.cloud_provider_manager.start_job(
            provider_result['provider'],
            job['job_id'],
            migration_result['migration_package']
        )
        
        return {
            'status': 'success',
            'strategy': 'cloud_failover',
            'old_gpu': job['allocated_gpu'],
            'cloud_provider': provider_result['provider'],
            'cloud_job_id': cloud_job['cloud_job_id']
        }
```

## 5. Sicherheit und Datenschutz

### 5.1 Datenschutzklassifizierung

- **Klassifizierungssystem**: Einstufung von Daten in Vertraulichkeitsstufen
- **Automatische Klassifizierung**: KI-basierte Erkennung sensibler Inhalte
- **Benutzergesteuerte Klassifizierung**: Manuelle Einstufung durch Benutzer

### 5.2 Sichere Datenübertragung

- **Ende-zu-Ende-Verschlüsselung**: Verschlüsselung aller Daten während der Übertragung
- **Sichere Kanäle**: VPN oder SSH-Tunneling für lokale GPU-Kommunikation
- **Datenminimierung**: Übertragung nur der notwendigen Daten

### 5.3 Zugriffssteuerung

- **Rollenbasierte Zugriffssteuerung**: Differenzierte Berechtigungen für GPU-Ressourcen
- **Audit-Logging**: Protokollierung aller Zugriffe und Aktionen
- **Automatische Bereinigung**: Löschung temporärer Daten nach Abschluss der Analyse

## 6. Leistungsoptimierung

### 6.1 Netzwerkoptimierung

- **Datenlokalität**: Bevorzugung lokaler GPUs für große Mediendateien
- **Kompression**: Automatische Kompression von Mediendaten vor der Übertragung
- **Streaming-Verarbeitung**: Verarbeitung von Daten während der Übertragung

### 6.2 Ressourcenplanung

- **Vorausschauende Planung**: Vorhersage der GPU-Anforderungen basierend auf historischen Daten
- **Wartungsplanung**: Planung von Wartungsarbeiten in Zeiten geringer Auslastung
- **Energieeffizienz**: Optimierung der Energienutzung lokaler GPUs

## 7. Monitoring und Berichterstattung

### 7.1 Echtzeit-Monitoring

- **Dashboard**: Echtzeit-Übersicht über alle lokalen und Cloud-GPUs
- **Alarme**: Automatische Benachrichtigungen bei Problemen
- **Leistungsmetriken**: Detaillierte Metriken zur GPU-Nutzung

### 7.2 Nutzungsberichte

- **Auslastungsberichte**: Detaillierte Berichte zur GPU-Auslastung
- **Kostenvergleich**: Vergleich der Kosten zwischen lokalen und Cloud-GPUs
- **Optimierungsvorschläge**: Automatische Vorschläge zur Optimierung der GPU-Nutzung

### 7.3 Beispiel-Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│ AIMA GPU-Übersicht                                                       │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────┤
│ GPU-ID      │ Modell      │ Status      │ Auslastung  │ Aktuelle Jobs   │
├─────────────┼─────────────┼─────────────┼─────────────┼─────────────────┤
│ gpu_a1b2c3d4│ RTX 4090    │ Aktiv       │ 87%         │ job_12345       │
│ gpu_e5f6g7h8│ RTX 4090    │ Verfügbar   │ 0%          │ -               │
│ gpu_i9j0k1l2│ A100        │ Wartung     │ 0%          │ -               │
│ cloud_01    │ A100 (Vast) │ Aktiv       │ 92%         │ job_67890       │
│ cloud_02    │ A100 (RunP) │ Aktiv       │ 78%         │ job_24680       │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Aktuelle Auslastung                                                      │
│                                                                         │
│ Lokale GPUs: ███████████████████████████████████████████████░░░░░ 90%   │
│ Cloud GPUs:  █████████████████████████████████████████░░░░░░░░░░ 80%    │
│                                                                         │
│ Warteschlange: 3 Jobs (geschätzte Wartezeit: 45 Minuten)               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Kostenübersicht (letzte 30 Tage)                                        │
│                                                                         │
│ Lokale GPUs:  $1,245.67 (Energiekosten + Abschreibung)                 │
│ Cloud GPUs:   $2,890.12                                                 │
│ Einsparungen: $1,120.45 (durch lokale GPU-Nutzung)                     │
└─────────────────────────────────────────────────────────────────────────┘
```

## 8. Implementierungsplan

### 8.1 Phasenweise Implementierung

#### Phase 1: Grundlegende Integration
- Implementierung des GPU-Agenten für lokale GPUs
- Einfache Entscheidungslogik für die GPU-Auswahl
- Grundlegende Monitoring-Funktionen

#### Phase 2: Erweiterte Funktionen
- Leistungsprofilierung und Benchmarking
- Dynamische Workload-Anpassung
- Verbesserte Failover-Mechanismen

#### Phase 3: Optimierung und Skalierung
- Anbieterübergreifende Optimierung
- Erweiterte Sicherheits- und Datenschutzfunktionen
- Umfassende Berichterstattung und Analyse

### 8.2 Testplan

- **Einheitentests**: Tests für einzelne Komponenten
- **Integrationstests**: Tests für die Zusammenarbeit verschiedener Komponenten
- **Lasttests**: Tests unter hoher Last
- **Failover-Tests**: Simulation von Ausfällen und Tests der Failover-Mechanismen

### 8.3 Dokumentation und Schulung

- **Administratorhandbuch**: Detaillierte Anleitung für Systemadministratoren
- **Benutzerhandbuch**: Anleitung für Endbenutzer
- **Schulungsmaterialien**: Schulungsunterlagen für Administratoren und Benutzer