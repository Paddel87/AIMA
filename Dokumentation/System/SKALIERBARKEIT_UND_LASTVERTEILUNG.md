# Skalierbarkeit und Lastverteilung im AIMA-System

Dieses Dokument beschreibt die Strategien und Implementierungsdetails für die Skalierbarkeit und Lastverteilung im AIMA-System, um eine effiziente Verarbeitung großer Datenmengen zu gewährleisten.

## 1. Architekturübersicht

### 1.1 Mehrschichtige Architektur

Das AIMA-System verwendet eine mehrschichtige Architektur, die horizontal und vertikal skaliert werden kann:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Client-Schicht                               │
│  (Web-Interface, API-Clients, Batch-Upload-Tools)                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                      API-Gateway-Schicht                            │
│  (Lastverteilung, Authentifizierung, Rate-Limiting)                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                     Orchestrierungs-Schicht                         │
│  (Job-Scheduling, Ressourcenzuweisung, Statusverfolgung)           │
└─────────┬─────────────────────┬──────────────────────┬──────────────┘
          │                     │                      │
┌─────────▼─────────┐  ┌────────▼────────┐  ┌─────────▼─────────────┐
│  Medienverarbeitung│  │  Analysemodule  │  │  Datenfusions-Engine  │
│  (Skalierbare      │  │  (GPU-basierte  │  │  (CPU-intensive       │
│   Vorverarbeitung) │  │   ML-Modelle)   │  │   Verarbeitung)       │
└─────────┬─────────┘  └────────┬────────┘  └─────────┬─────────────┘
          │                     │                      │
┌─────────▼─────────────────────▼──────────────────────▼─────────────┐
│                        Datenspeicher-Schicht                        │
│  (Dokumentendatenbank, Vektordatenbank, Objektspeicher)            │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Microservices-Architektur

Das System ist in unabhängige Microservices aufgeteilt, die jeweils spezifische Funktionen erfüllen und unabhängig skaliert werden können:

1. **Upload-Service**: Verarbeitet Medien-Uploads und initiiert die Vorverarbeitung
2. **Preprocessing-Service**: Führt Medientyperkennung, Deduplizierung und Formatkonvertierung durch
3. **Job-Scheduler**: Verwaltet die Analyse-Warteschlange und Ressourcenzuweisung
4. **GPU-Manager**: Verwaltet lokale und Cloud-GPU-Ressourcen
5. **Analyse-Services**: Spezialisierte Dienste für Video-, Bild- und Audioanalyse
6. **Datenfusions-Service**: Führt multimodale Datenfusion durch
7. **Dossier-Service**: Erstellt und verwaltet Dossiers
8. **Speicher-Service**: Verwaltet die langfristige Datenspeicherung
9. **Monitoring-Service**: Überwacht Systemleistung und -gesundheit

## 2. Horizontale Skalierung

### 2.1 Containerisierung und Orchestrierung

#### Kubernetes-basierte Orchestrierung

Das AIMA-System verwendet Kubernetes für die Container-Orchestrierung mit folgenden Komponenten:

- **Deployment-Konfigurationen**: Definieren die gewünschte Anzahl von Replikaten für jeden Microservice
- **Horizontal Pod Autoscaler (HPA)**: Automatische Skalierung basierend auf CPU/Speicherauslastung
- **Custom Metrics Autoscaler**: Skalierung basierend auf anwendungsspezifischen Metriken (z.B. Warteschlangenlänge)
- **Node Affinity Rules**: Optimale Platzierung von Pods basierend auf Hardware-Anforderungen

```yaml
# Beispiel für einen Horizontal Pod Autoscaler für den Preprocessing-Service
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: preprocessing-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: preprocessing-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: queue_length
      target:
        type: AverageValue
        averageValue: 10
```

#### Containerisierungsstrategie

- **Basis-Images**: Optimierte Basis-Images mit vorinstallierten Abhängigkeiten
- **Multi-Stage Builds**: Reduzierung der Image-Größe durch Trennung von Build- und Runtime-Umgebungen
- **Resource Limits**: Definierte CPU- und Speicherlimits für jeden Container
- **Health Checks**: Liveness- und Readiness-Probes für zuverlässige Selbstheilung

### 2.2 Skalierungsstrategien für verschiedene Komponenten

#### Stateless Services

Die meisten AIMA-Microservices sind zustandslos (stateless) und können einfach horizontal skaliert werden:

- **API-Gateway**: Skalierung basierend auf Anfragerate und Latenz
- **Preprocessing-Service**: Skalierung basierend auf Upload-Volumen und Warteschlangenlänge
- **Analyse-Services**: Skalierung basierend auf Jobwarteschlange und verfügbaren GPU-Ressourcen

#### Stateful Services

Einige Komponenten erfordern zustandsbehaftete (stateful) Skalierung:

- **Datenbanken**: Verwendung von Sharding und Replikation
- **Objektspeicher**: Verteilte Speichersysteme mit automatischer Skalierung
- **Warteschlangen**: Partitionierte Nachrichtenwarteschlangen für hohen Durchsatz

```python
class ScalingManager:
    def __init__(self, kubernetes_client, metrics_client):
        self.k8s_client = kubernetes_client
        self.metrics_client = metrics_client
        self.scaling_policies = self._load_scaling_policies()
    
    def _load_scaling_policies(self):
        """Lädt Skalierungsrichtlinien aus der Konfiguration"""
        # In einer realen Implementierung würden diese aus einer Konfigurationsdatei oder DB geladen
        return {
            'preprocessing-service': {
                'min_replicas': 3,
                'max_replicas': 20,
                'metrics': [
                    {'type': 'cpu', 'target_utilization': 70},
                    {'type': 'memory', 'target_utilization': 80},
                    {'type': 'queue_length', 'target_value': 10}
                ],
                'scale_up_cooldown': 60,  # Sekunden
                'scale_down_cooldown': 300  # Sekunden
            },
            'video-analysis-service': {
                'min_replicas': 2,
                'max_replicas': 10,
                'metrics': [
                    {'type': 'cpu', 'target_utilization': 80},
                    {'type': 'gpu_utilization', 'target_utilization': 85},
                    {'type': 'job_queue', 'target_value': 5}
                ],
                'scale_up_cooldown': 120,
                'scale_down_cooldown': 600
            },
            # Weitere Dienste...
        }
    
    def evaluate_scaling_needs(self):
        """Bewertet Skalierungsbedarf für alle Dienste"""
        scaling_actions = []
        
        for service_name, policy in self.scaling_policies.items():
            current_metrics = self.metrics_client.get_service_metrics(service_name)
            current_replicas = self.k8s_client.get_replica_count(service_name)
            
            # Berechne gewünschte Replikatanzahl basierend auf Metriken
            desired_replicas = self._calculate_desired_replicas(
                service_name, current_replicas, current_metrics, policy
            )
            
            # Prüfe Cooldown-Perioden
            last_scaling = self.k8s_client.get_last_scaling_time(service_name)
            now = datetime.now()
            
            if desired_replicas > current_replicas:
                # Scale-Up
                cooldown_period = policy['scale_up_cooldown']
                if (now - last_scaling).total_seconds() > cooldown_period:
                    scaling_actions.append({
                        'service': service_name,
                        'current_replicas': current_replicas,
                        'desired_replicas': desired_replicas,
                        'action': 'scale_up',
                        'reason': self._get_scaling_reason(current_metrics, policy)
                    })
            elif desired_replicas < current_replicas:
                # Scale-Down
                cooldown_period = policy['scale_down_cooldown']
                if (now - last_scaling).total_seconds() > cooldown_period:
                    scaling_actions.append({
                        'service': service_name,
                        'current_replicas': current_replicas,
                        'desired_replicas': desired_replicas,
                        'action': 'scale_down',
                        'reason': self._get_scaling_reason(current_metrics, policy)
                    })
        
        return scaling_actions
    
    def _calculate_desired_replicas(self, service_name, current_replicas, metrics, policy):
        """Berechnet die gewünschte Anzahl von Replikaten basierend auf Metriken"""
        replica_suggestions = []
        
        for metric_policy in policy['metrics']:
            metric_type = metric_policy['type']
            
            if metric_type in metrics:
                current_value = metrics[metric_type]
                
                if 'target_utilization' in metric_policy:
                    # Auslastungsbasierte Metrik (z.B. CPU, Speicher)
                    target = metric_policy['target_utilization']
                    suggested_replicas = math.ceil(current_replicas * (current_value / target))
                elif 'target_value' in metric_policy:
                    # Wertbasierte Metrik (z.B. Warteschlangenlänge)
                    target = metric_policy['target_value']
                    # Einfache lineare Skalierung basierend auf Warteschlangenlänge
                    suggested_replicas = math.ceil(current_value / target)
                
                replica_suggestions.append(suggested_replicas)
        
        if not replica_suggestions:
            return current_replicas
        
        # Wähle die höchste Replikatanzahl aus allen Metrikvorschlägen
        desired_replicas = max(replica_suggestions)
        
        # Begrenze auf Min/Max-Werte aus der Richtlinie
        desired_replicas = max(policy['min_replicas'], min(policy['max_replicas'], desired_replicas))
        
        return desired_replicas
    
    def _get_scaling_reason(self, metrics, policy):
        """Ermittelt den Grund für die Skalierungsentscheidung"""
        reasons = []
        
        for metric_policy in policy['metrics']:
            metric_type = metric_policy['type']
            
            if metric_type in metrics:
                current_value = metrics[metric_type]
                
                if 'target_utilization' in metric_policy:
                    target = metric_policy['target_utilization']
                    if current_value > target:
                        reasons.append(f"{metric_type} utilization {current_value}% > target {target}%")
                    elif current_value < target * 0.7:  # 30% unter Ziel
                        reasons.append(f"{metric_type} utilization {current_value}% < target {target}%")
                
                elif 'target_value' in metric_policy:
                    target = metric_policy['target_value']
                    if current_value > target:
                        reasons.append(f"{metric_type} value {current_value} > target {target}")
                    elif current_value < target * 0.7:  # 30% unter Ziel
                        reasons.append(f"{metric_type} value {current_value} < target {target}")
        
        return ", ".join(reasons) if reasons else "Unknown reason"
    
    def apply_scaling_actions(self, scaling_actions):
        """Wendet Skalierungsaktionen an"""
        for action in scaling_actions:
            service_name = action['service']
            desired_replicas = action['desired_replicas']
            
            logging.info(f"Scaling {service_name} from {action['current_replicas']} to {desired_replicas} replicas. Reason: {action['reason']}")
            
            try:
                self.k8s_client.scale_deployment(
                    service_name, 
                    desired_replicas,
                    reason=action['reason']
                )
            except Exception as e:
                logging.error(f"Failed to scale {service_name}: {str(e)}")
```

## 3. Vertikale Skalierung

### 3.1 Ressourcenoptimierung

#### Automatische Ressourcenanpassung

Für bestimmte Komponenten wird eine vertikale Skalierung implementiert:

- **Datenbanken**: Automatische Anpassung von CPU, Speicher und Festplattenkapazität
- **GPU-Instanzen**: Auswahl der optimalen GPU-Größe basierend auf Workload-Anforderungen
- **Spezialisierte Workloads**: Anpassung der Ressourcen für rechenintensive Aufgaben

#### Ressourcenklassen

Definierte Ressourcenklassen für verschiedene Workload-Typen:

| Ressourcenklasse | CPU | Speicher | GPU | Anwendungsfall |
|-----------------|-----|----------|-----|----------------|
| Small           | 2   | 4 GB     | -   | Leichte Vorverarbeitung |
| Medium          | 4   | 8 GB     | -   | Standard-Vorverarbeitung, Datenfusion |
| Large           | 8   | 16 GB    | -   | Schwere Vorverarbeitung, komplexe Datenfusion |
| GPU-Small       | 4   | 16 GB    | T4  | Einfache Bildanalyse |
| GPU-Medium      | 8   | 32 GB    | RTX 4090 | Standard-Video/Bildanalyse |
| GPU-Large       | 16  | 64 GB    | A100 | Komplexe Video/Bildanalyse, große Modelle |

### 3.2 Adaptive Ressourcenzuweisung

```python
class ResourceOptimizer:
    def __init__(self, resource_manager, job_profiler):
        self.resource_manager = resource_manager
        self.job_profiler = job_profiler
        self.resource_classes = self._define_resource_classes()
    
    def _define_resource_classes(self):
        """Definiert verfügbare Ressourcenklassen"""
        return {
            'small': {
                'cpu': 2,
                'memory': '4Gi',
                'gpu': None,
                'cost_factor': 1.0
            },
            'medium': {
                'cpu': 4,
                'memory': '8Gi',
                'gpu': None,
                'cost_factor': 2.0
            },
            'large': {
                'cpu': 8,
                'memory': '16Gi',
                'gpu': None,
                'cost_factor': 4.0
            },
            'gpu-small': {
                'cpu': 4,
                'memory': '16Gi',
                'gpu': 'nvidia-t4',
                'gpu_memory': '16Gi',
                'cost_factor': 8.0
            },
            'gpu-medium': {
                'cpu': 8,
                'memory': '32Gi',
                'gpu': 'nvidia-rtx-4090',
                'gpu_memory': '24Gi',
                'cost_factor': 16.0
            },
            'gpu-large': {
                'cpu': 16,
                'memory': '64Gi',
                'gpu': 'nvidia-a100',
                'gpu_memory': '80Gi',
                'cost_factor': 32.0
            }
        }
    
    def optimize_resources_for_job(self, job):
        """Optimiert Ressourcen für einen bestimmten Job"""
        # Analysiere Job-Anforderungen
        job_type = job['type']  # z.B. 'video_analysis', 'audio_analysis'
        job_size = self._estimate_job_size(job)
        job_priority = job.get('priority', 'normal')
        
        # Hole historische Profildaten für ähnliche Jobs
        profile_data = self.job_profiler.get_similar_job_profiles(
            job_type, job_size, limit=10
        )
        
        # Bestimme optimale Ressourcenklasse basierend auf Profildaten
        if profile_data:
            recommended_class = self._analyze_profile_data(profile_data, job_priority)
        else:
            # Fallback auf Standardempfehlungen, wenn keine Profildaten verfügbar sind
            recommended_class = self._get_default_resource_class(job_type, job_size, job_priority)
        
        # Prüfe Verfügbarkeit der empfohlenen Ressourcen
        if not self.resource_manager.check_resource_availability(recommended_class):
            # Finde alternative Ressourcenklasse, wenn empfohlene nicht verfügbar ist
            alternative_class = self._find_alternative_resource_class(recommended_class)
            logging.warning(f"Recommended resource class {recommended_class} not available, using {alternative_class} instead")
            recommended_class = alternative_class
        
        # Berechne geschätzte Kosten und Ausführungszeit
        cost_estimate = self._estimate_cost(job, recommended_class)
        time_estimate = self._estimate_execution_time(job, recommended_class)
        
        return {
            'job_id': job['job_id'],
            'recommended_resource_class': recommended_class,
            'resource_specs': self.resource_classes[recommended_class],
            'estimated_cost': cost_estimate,
            'estimated_execution_time': time_estimate,
            'reasoning': self._generate_recommendation_reasoning(job, recommended_class, profile_data)
        }
    
    def _estimate_job_size(self, job):
        """Schätzt die Größe eines Jobs basierend auf Eingabedaten"""
        if job['type'] == 'video_analysis':
            # Für Videoanalyse: Basierend auf Dauer, Auflösung und Komplexität
            duration_seconds = job.get('metadata', {}).get('duration_seconds', 0)
            resolution = job.get('metadata', {}).get('resolution', '1080p')
            complexity = job.get('analysis_complexity', 'standard')
            
            # Einfache Größenschätzung
            if resolution in ['4k', '2160p']:
                resolution_factor = 4.0
            elif resolution in ['1440p', '2k']:
                resolution_factor = 2.0
            elif resolution in ['1080p', 'hd']:
                resolution_factor = 1.0
            else:  # 720p oder niedriger
                resolution_factor = 0.5
            
            if complexity == 'high':
                complexity_factor = 2.0
            elif complexity == 'low':
                complexity_factor = 0.5
            else:  # 'standard'
                complexity_factor = 1.0
            
            size_score = duration_seconds * resolution_factor * complexity_factor / 60.0  # Normalisiert auf Minuten
            
            # Kategorisiere in klein, mittel, groß
            if size_score < 10:
                return 'small'
            elif size_score < 60:
                return 'medium'
            else:
                return 'large'
                
        elif job['type'] == 'image_analysis':
            # Für Bildanalyse: Basierend auf Anzahl der Bilder, Auflösung und Komplexität
            image_count = job.get('metadata', {}).get('image_count', 1)
            avg_resolution = job.get('metadata', {}).get('avg_resolution', '1080p')
            complexity = job.get('analysis_complexity', 'standard')
            
            # Ähnliche Logik wie bei Video
            # ...
            
            return 'medium'  # Vereinfacht
            
        elif job['type'] == 'audio_analysis':
            # Für Audioanalyse: Basierend auf Dauer und Komplexität
            duration_seconds = job.get('metadata', {}).get('duration_seconds', 0)
            complexity = job.get('analysis_complexity', 'standard')
            
            # ...
            
            return 'small'  # Vereinfacht
            
        else:
            # Standardfall
            return 'medium'
    
    def _analyze_profile_data(self, profile_data, job_priority):
        """Analysiert Profildaten, um die optimale Ressourcenklasse zu bestimmen"""
        # Gruppiere Profildaten nach Ressourcenklasse
        performance_by_class = {}
        
        for profile in profile_data:
            resource_class = profile['resource_class']
            
            if resource_class not in performance_by_class:
                performance_by_class[resource_class] = {
                    'execution_times': [],
                    'success_rate': 0,
                    'cost': []
                }
            
            performance_by_class[resource_class]['execution_times'].append(profile['execution_time_seconds'])
            performance_by_class[resource_class]['cost'].append(profile['cost'])
            
            if profile['status'] == 'completed':
                performance_by_class[resource_class]['success_rate'] += 1
        
        # Berechne Durchschnittswerte für jede Klasse
        for class_name, data in performance_by_class.items():
            data['avg_execution_time'] = sum(data['execution_times']) / len(data['execution_times'])
            data['avg_cost'] = sum(data['cost']) / len(data['cost'])
            data['success_rate'] = (data['success_rate'] / len(data['execution_times'])) * 100
        
        # Wähle optimale Klasse basierend auf Priorität
        if job_priority == 'high':
            # Für hohe Priorität: Optimiere für Geschwindigkeit, ignoriere Kosten weitgehend
            sorted_classes = sorted(performance_by_class.items(), 
                                   key=lambda x: (x[1]['avg_execution_time'], -x[1]['success_rate']))
        elif job_priority == 'low':
            # Für niedrige Priorität: Optimiere für Kosten
            sorted_classes = sorted(performance_by_class.items(), 
                                   key=lambda x: (x[1]['avg_cost'], x[1]['avg_execution_time']))
        else:  # 'normal'
            # Für normale Priorität: Ausgewogenes Verhältnis von Kosten und Geschwindigkeit
            sorted_classes = sorted(performance_by_class.items(), 
                                   key=lambda x: (x[1]['avg_execution_time'] * x[1]['avg_cost'], -x[1]['success_rate']))
        
        # Wähle die beste Klasse
        if sorted_classes:
            return sorted_classes[0][0]
        else:
            # Fallback, wenn keine Daten verfügbar sind
            return self._get_default_resource_class('unknown', 'medium', job_priority)
```

## 4. Lastverteilung

### 4.1 Intelligentes Job-Scheduling

#### Prioritätsbasiertes Scheduling

Das AIMA-System implementiert ein mehrstufiges Scheduling-System:

- **Prioritätsklassen**: Kritisch, Hoch, Normal, Niedrig, Batch
- **Fairness-Mechanismen**: Verhindert Verhungern von Jobs niedriger Priorität
- **Deadline-basiertes Scheduling**: Berücksichtigung von Benutzer-Deadlines
- **Ressourcenreservierung**: Vorab-Reservierung von Ressourcen für kritische Jobs

#### Adaptive Warteschlangenverwaltung

```python
class JobScheduler:
    def __init__(self, resource_manager, queue_manager):
        self.resource_manager = resource_manager
        self.queue_manager = queue_manager
        self.scheduling_interval = 30  # Sekunden
        self.fairness_threshold = 600  # Sekunden (10 Minuten)
        self.priority_weights = {
            'critical': 100,
            'high': 50,
            'normal': 10,
            'low': 5,
            'batch': 1
        }
    
    def start_scheduling_loop(self):
        """Startet die Scheduling-Schleife"""
        while True:
            try:
                self.schedule_pending_jobs()
            except Exception as e:
                logging.error(f"Error in scheduling loop: {str(e)}")
            
            time.sleep(self.scheduling_interval)
    
    def schedule_pending_jobs(self):
        """Plant ausstehende Jobs basierend auf Priorität und verfügbaren Ressourcen"""
        # Hole alle ausstehenden Jobs aus allen Warteschlangen
        pending_jobs = self.queue_manager.get_all_pending_jobs()
        
        if not pending_jobs:
            logging.debug("No pending jobs to schedule")
            return
        
        # Sortiere Jobs nach effektiver Priorität
        sorted_jobs = self._sort_jobs_by_effective_priority(pending_jobs)
        
        # Hole verfügbare Ressourcen
        available_resources = self.resource_manager.get_available_resources()
        
        # Versuche, Jobs zu planen
        scheduled_jobs = []
        for job in sorted_jobs:
            # Prüfe, ob ausreichende Ressourcen verfügbar sind
            required_resources = job['resource_requirements']
            
            matching_resource = self._find_matching_resource(
                required_resources, available_resources
            )
            
            if matching_resource:
                # Ressource gefunden, plane Job
                scheduled_job = self._schedule_job(job, matching_resource)
                scheduled_jobs.append(scheduled_job)
                
                # Aktualisiere verfügbare Ressourcen
                self._update_available_resources(available_resources, matching_resource)
                
                # Wenn es sich um einen kritischen Job handelt, priorisiere ihn stark
                if job['priority'] == 'critical':
                    break  # Fokussiere auf diesen einen kritischen Job
        
        logging.info(f"Scheduled {len(scheduled_jobs)} jobs out of {len(pending_jobs)} pending jobs")
        
        # Aktualisiere Warteschlangen-Statistiken
        self.queue_manager.update_queue_statistics()
    
    def _sort_jobs_by_effective_priority(self, jobs):
        """Sortiert Jobs nach effektiver Priorität, die Wartezeit berücksichtigt"""
        now = datetime.now()
        
        # Berechne effektive Priorität für jeden Job
        for job in jobs:
            base_priority = self.priority_weights.get(job['priority'], 1)
            wait_time = (now - job['queued_at']).total_seconds()
            
            # Erhöhe Priorität basierend auf Wartezeit
            wait_factor = 1.0
            if wait_time > self.fairness_threshold:
                # Erhöhe Priorität für lange wartende Jobs
                wait_factor = 1.0 + (wait_time - self.fairness_threshold) / self.fairness_threshold
                wait_factor = min(wait_factor, 10.0)  # Begrenze den Faktor
            
            # Berücksichtige Deadline, falls vorhanden
            deadline_factor = 1.0
            if 'deadline' in job and job['deadline']:
                time_to_deadline = (job['deadline'] - now).total_seconds()
                if time_to_deadline > 0:
                    # Je näher an der Deadline, desto höher die Priorität
                    deadline_factor = max(1.0, 100.0 / max(1, time_to_deadline / 60))  # Minuten bis Deadline
            
            # Berechne effektive Priorität
            job['effective_priority'] = base_priority * wait_factor * deadline_factor
        
        # Sortiere nach effektiver Priorität (absteigend)
        return sorted(jobs, key=lambda x: x['effective_priority'], reverse=True)
    
    def _find_matching_resource(self, required_resources, available_resources):
        """Findet eine passende Ressource für die Anforderungen"""
        for resource in available_resources:
            if self._resource_meets_requirements(resource, required_resources):
                return resource
        
        return None
    
    def _resource_meets_requirements(self, resource, requirements):
        """Prüft, ob eine Ressource die Anforderungen erfüllt"""
        # Prüfe CPU
        if 'cpu' in requirements and resource['available_cpu'] < requirements['cpu']:
            return False
        
        # Prüfe Speicher
        if 'memory' in requirements and resource['available_memory'] < requirements['memory']:
            return False
        
        # Prüfe GPU
        if 'gpu' in requirements and requirements['gpu']:
            if 'available_gpus' not in resource or not resource['available_gpus']:
                return False
            
            # Prüfe GPU-Typ, falls angegeben
            if 'gpu_type' in requirements and requirements['gpu_type']:
                matching_gpu = False
                for gpu in resource['available_gpus']:
                    if gpu['type'] == requirements['gpu_type']:
                        matching_gpu = True
                        break
                
                if not matching_gpu:
                    return False
            
            # Prüfe GPU-Speicher
            if 'gpu_memory' in requirements:
                matching_gpu = False
                for gpu in resource['available_gpus']:
                    if gpu['available_memory'] >= requirements['gpu_memory']:
                        matching_gpu = True
                        break
                
                if not matching_gpu:
                    return False
        
        return True
    
    def _schedule_job(self, job, resource):
        """Plant einen Job auf einer bestimmten Ressource"""
        job_id = job['job_id']
        resource_id = resource['resource_id']
        
        logging.info(f"Scheduling job {job_id} on resource {resource_id}")
        
        # Aktualisiere Job-Status
        self.queue_manager.update_job_status(
            job_id, 
            'scheduled', 
            {
                'resource_id': resource_id,
                'scheduled_at': datetime.now(),
                'estimated_start_time': datetime.now() + timedelta(seconds=10)  # Geschätzte Startzeit
            }
        )
        
        # Weise Ressource zu
        allocation_result = self.resource_manager.allocate_resource(
            resource_id,
            job_id,
            job['resource_requirements']
        )
        
        # Starte Job-Ausführung
        execution_result = self.resource_manager.start_job_execution(job_id, resource_id)
        
        return {
            'job_id': job_id,
            'resource_id': resource_id,
            'allocation_result': allocation_result,
            'execution_result': execution_result
        }
    
    def _update_available_resources(self, available_resources, allocated_resource):
        """Aktualisiert die Liste der verfügbaren Ressourcen nach einer Zuweisung"""
        # Entferne zugewiesene Ressource aus der Liste
        for i, resource in enumerate(available_resources):
            if resource['resource_id'] == allocated_resource['resource_id']:
                del available_resources[i]
                break
```

### 4.2 Lastverteilung zwischen lokalen und Cloud-Ressourcen

#### Hybride Ressourcenverwaltung

Das System implementiert eine intelligente Verteilung zwischen lokalen und Cloud-Ressourcen:

- **Kostenoptimierung**: Bevorzugung lokaler Ressourcen für kosteneffiziente Verarbeitung
- **Burst-Kapazität**: Automatische Nutzung von Cloud-Ressourcen bei Spitzenlasten
- **Datenlokalität**: Berücksichtigung des Speicherorts der Daten bei der Ressourcenzuweisung
- **Compliance-Anforderungen**: Berücksichtigung von Datenschutzanforderungen

#### Adaptive Schwellenwerte

```python
class HybridResourceManager:
    def __init__(self, local_resource_manager, cloud_resource_manager, config):
        self.local_manager = local_resource_manager
        self.cloud_manager = cloud_resource_manager
        self.config = config
        self.usage_history = []
        self.history_window = 24 * 60 * 60  # 24 Stunden in Sekunden
        self.last_threshold_update = datetime.now()
        self.threshold_update_interval = 3600  # 1 Stunde in Sekunden
    
    def get_resource_allocation_decision(self, job):
        """Entscheidet, ob ein Job lokal oder in der Cloud ausgeführt werden soll"""
        # Prüfe Datenschutzanforderungen
        if job.get('data_confidentiality', 'public') == 'confidential':
            # Vertrauliche Daten müssen lokal verarbeitet werden
            return {'decision': 'local', 'reason': 'Data confidentiality requirements'}
        
        # Prüfe aktuelle Auslastung lokaler Ressourcen
        local_utilization = self.local_manager.get_current_utilization()
        
        # Hole aktuelle Schwellenwerte
        thresholds = self._get_current_thresholds()
        
        # Prüfe Dringlichkeit des Jobs
        if job.get('priority', 'normal') == 'critical':
            # Kritische Jobs: Verwende Cloud, wenn lokale Ressourcen über 50% ausgelastet sind
            if local_utilization > thresholds['critical_job_local_max']:
                return {'decision': 'cloud', 'reason': 'Critical job, high local utilization'}
        
        # Prüfe Warteschlangenlänge
        local_queue_length = self.local_manager.get_queue_length()
        estimated_wait_time = self.local_manager.estimate_wait_time(job)
        
        if estimated_wait_time > thresholds['max_wait_time_seconds']:
            return {'decision': 'cloud', 'reason': f'Estimated wait time ({estimated_wait_time}s) exceeds threshold'}
        
        # Prüfe Ressourcenanforderungen
        if not self.local_manager.can_satisfy_requirements(job['resource_requirements']):
            return {'decision': 'cloud', 'reason': 'Local resources cannot satisfy requirements'}
        
        # Prüfe Kosteneffizienz
        local_cost = self.local_manager.estimate_job_cost(job)
        cloud_cost = self.cloud_manager.estimate_job_cost(job)
        
        # Berücksichtige Kostenschwellenwert
        if cloud_cost < local_cost * thresholds['cost_efficiency_factor']:
            return {'decision': 'cloud', 'reason': 'Cloud execution more cost-effective'}
        
        # Standardentscheidung: Lokale Ausführung bevorzugen
        return {'decision': 'local', 'reason': 'Default to local execution'}
    
    def _get_current_thresholds(self):
        """Holt aktuelle Schwellenwerte, aktualisiert sie bei Bedarf"""
        now = datetime.now()
        
        # Prüfe, ob Schwellenwerte aktualisiert werden müssen
        if (now - self.last_threshold_update).total_seconds() > self.threshold_update_interval:
            self._update_adaptive_thresholds()
            self.last_threshold_update = now
        
        return {
            'critical_job_local_max': self.config.get('critical_job_local_max', 0.5),
            'max_wait_time_seconds': self.config.get('max_wait_time_seconds', 1800),  # 30 Minuten
            'cost_efficiency_factor': self.config.get('cost_efficiency_factor', 0.8),
            'local_utilization_threshold': self.config.get('local_utilization_threshold', 0.8)
        }
    
    def _update_adaptive_thresholds(self):
        """Aktualisiert Schwellenwerte basierend auf historischen Daten"""
        # Bereinige alte Einträge aus dem Verlauf
        now = datetime.now()
        self.usage_history = [entry for entry in self.usage_history 
                             if (now - entry['timestamp']).total_seconds() <= self.history_window]
        
        if not self.usage_history:
            return  # Keine historischen Daten verfügbar
        
        # Analysiere Nutzungsmuster
        utilization_values = [entry['local_utilization'] for entry in self.usage_history]
        avg_utilization = sum(utilization_values) / len(utilization_values)
        peak_utilization = max(utilization_values)
        
        # Analysiere Wartezeitenmuster
        wait_times = [entry['avg_wait_time'] for entry in self.usage_history if 'avg_wait_time' in entry]
        if wait_times:
            avg_wait_time = sum(wait_times) / len(wait_times)
            peak_wait_time = max(wait_times)
        else:
            avg_wait_time = 0
            peak_wait_time = 0
        
        # Analysiere Kosteneffizienz
        cost_ratios = [entry['cloud_cost'] / entry['local_cost'] if entry['local_cost'] > 0 else 1.0 
                      for entry in self.usage_history if 'cloud_cost' in entry and 'local_cost' in entry]
        if cost_ratios:
            avg_cost_ratio = sum(cost_ratios) / len(cost_ratios)
        else:
            avg_cost_ratio = 1.0
        
        # Aktualisiere Schwellenwerte basierend auf Analyse
        # Erhöhe Schwellenwert für lokale Auslastung, wenn durchschnittliche Auslastung niedrig ist
        if avg_utilization < 0.5:
            new_utilization_threshold = min(0.9, self.config.get('local_utilization_threshold', 0.8) + 0.05)
        elif avg_utilization > 0.8:
            new_utilization_threshold = max(0.6, self.config.get('local_utilization_threshold', 0.8) - 0.05)
        else:
            new_utilization_threshold = self.config.get('local_utilization_threshold', 0.8)
        
        # Passe Wartezeitschwellenwert an
        if peak_wait_time > 0:
            new_wait_time_threshold = min(3600, max(600, peak_wait_time * 0.8))  # Zwischen 10 Minuten und 1 Stunde
        else:
            new_wait_time_threshold = self.config.get('max_wait_time_seconds', 1800)
        
        # Passe Kosteneffizienzschwellenwert an
        if avg_cost_ratio < 0.7:
            # Cloud ist im Durchschnitt günstiger, senke Schwellenwert
            new_cost_efficiency_factor = max(0.6, self.config.get('cost_efficiency_factor', 0.8) - 0.05)
        elif avg_cost_ratio > 1.2:
            # Lokal ist im Durchschnitt günstiger, erhöhe Schwellenwert
            new_cost_efficiency_factor = min(0.95, self.config.get('cost_efficiency_factor', 0.8) + 0.05)
        else:
            new_cost_efficiency_factor = self.config.get('cost_efficiency_factor', 0.8)
        
        # Aktualisiere Konfiguration
        self.config['local_utilization_threshold'] = new_utilization_threshold
        self.config['max_wait_time_seconds'] = new_wait_time_threshold
        self.config['cost_efficiency_factor'] = new_cost_efficiency_factor
        
        logging.info(f"Updated adaptive thresholds: utilization={new_utilization_threshold}, "
                    f"wait_time={new_wait_time_threshold}s, cost_factor={new_cost_efficiency_factor}")
    
    def record_usage_statistics(self):
        """Zeichnet aktuelle Nutzungsstatistiken auf"""
        now = datetime.now()
        
        # Sammle aktuelle Statistiken
        stats = {
            'timestamp': now,
            'local_utilization': self.local_manager.get_current_utilization(),
            'cloud_utilization': self.cloud_manager.get_current_utilization(),
            'local_queue_length': self.local_manager.get_queue_length(),
            'cloud_queue_length': self.cloud_manager.get_queue_length(),
            'avg_wait_time': self.local_manager.get_average_wait_time()
        }
        
        # Füge Kostenstatistiken hinzu, wenn verfügbar
        local_cost_stats = self.local_manager.get_cost_statistics()
        cloud_cost_stats = self.cloud_manager.get_cost_statistics()
        
        if local_cost_stats and cloud_cost_stats:
            stats['local_cost'] = local_cost_stats['average_cost_per_job']
            stats['cloud_cost'] = cloud_cost_stats['average_cost_per_job']
        
        # Füge zu Verlauf hinzu
        self.usage_history.append(stats)
        
        # Bereinige alte Einträge
        self.usage_history = [entry for entry in self.usage_history 
                             if (now - entry['timestamp']).total_seconds() <= self.history_window]
```

## 5. Datenflussoptimierung

### 5.1 Pipelined Processing

#### Streaming-Verarbeitung

Das AIMA-System implementiert eine Streaming-Verarbeitung für effiziente Datenflüsse:

- **Inkrementelle Verarbeitung**: Verarbeitung von Daten, sobald sie verfügbar sind
- **Parallele Pipelines**: Gleichzeitige Verarbeitung mehrerer Datenströme
- **Backpressure-Mechanismen**: Verhindert Überlastung einzelner Komponenten

#### Datenflussdiagramm

```
┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
│  Medien-  │    │   Vor-    │    │  Analyse- │    │   Nach-   │
│  Upload   │───►│verarbeitung│───►│  Pipeline │───►│verarbeitung│
└───────────┘    └───────────┘    └───────────┘    └───────────┘
                                       │
                                       ▼
                                  ┌───────────┐
                                  │  Zwischen-│
                                  │ ergebnisse│
                                  └───────────┘
                                       │
                                       ▼
┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
│  Dossier- │    │   Daten-  │    │ Temporäre │    │ Ergebnis- │
│ Erstellung│◄───│   fusion  │◄───│ Ergebnisse│◄───│ Sammlung  │
└───────────┘    └───────────┘    └───────────┘    └───────────┘
```

### 5.2 Datenlokalität

#### Optimierte Datenspeicherung

- **Caching-Strategien**: Intelligentes Caching häufig verwendeter Daten
- **Datenpartitionierung**: Partitionierung von Daten basierend auf Zugriffsmustern
- **Datenreplikation**: Strategische Replikation von Daten für verbesserte Verfügbarkeit

```python
class DataLocalityOptimizer:
    def __init__(self, storage_manager, job_analyzer):
        self.storage_manager = storage_manager
        self.job_analyzer = job_analyzer
        self.cache_manager = CacheManager()
        self.data_access_patterns = {}
    
    def optimize_data_placement(self, job):
        """Optimiert die Datenplatzierung für einen Job"""
        # Analysiere Datenzugriffsmuster des Jobs
        data_requirements = self.job_analyzer.get_data_requirements(job)
        
        # Bestimme optimalen Speicherort für Eingabedaten
        optimal_locations = {}
        for data_item in data_requirements['input_data']:
            data_id = data_item['data_id']
            data_size = data_item['size_bytes']
            data_type = data_item['type']
            
            # Hole aktuelle Speicherorte
            current_locations = self.storage_manager.get_data_locations(data_id)
            
            # Bestimme optimalen Speicherort basierend auf Job-Ausführungsort und Datengröße
            if job['execution_location'] == 'local':
                # Für lokale Ausführung: Bevorzuge lokalen Speicher
                if 'local' in current_locations:
                    optimal_locations[data_id] = 'local'
                else:
                    # Daten müssen transferiert werden
                    if data_size > 1024 * 1024 * 1024:  # > 1 GB
                        # Große Daten: Plane Transfer im Voraus
                        self._schedule_data_transfer(data_id, 'cloud', 'local', job['job_id'])
                        optimal_locations[data_id] = 'transferring_to_local'
                    else:
                        # Kleine Daten: Direkter Transfer während der Ausführung
                        optimal_locations[data_id] = 'cloud_with_transfer'
            else:  # 'cloud'
                # Für Cloud-Ausführung: Bevorzuge Cloud-Speicher
                if 'cloud' in current_locations:
                    optimal_locations[data_id] = 'cloud'
                else:
                    # Daten müssen transferiert werden
                    if data_size > 1024 * 1024 * 1024:  # > 1 GB
                        # Große Daten: Plane Transfer im Voraus
                        self._schedule_data_transfer(data_id, 'local', 'cloud', job['job_id'])
                        optimal_locations[data_id] = 'transferring_to_cloud'
                    else:
                        # Kleine Daten: Direkter Transfer während der Ausführung
                        optimal_locations[data_id] = 'local_with_transfer'
        
        # Bestimme optimalen Speicherort für Ausgabedaten
        for data_item in data_requirements['output_data']:
            data_id = data_item['data_id']
            data_size = data_item.get('estimated_size_bytes', 0)
            data_type = data_item['type']
            
            # Bestimme optimalen Speicherort basierend auf nachfolgenden Verarbeitungsschritten
            next_steps = self.job_analyzer.get_next_processing_steps(job, data_id)
            
            if next_steps:
                # Es gibt nachfolgende Verarbeitungsschritte
                next_locations = [step['execution_location'] for step in next_steps]
                
                if all(loc == 'local' for loc in next_locations):
                    # Alle nachfolgenden Schritte sind lokal
                    optimal_locations[data_id] = 'local'
                elif all(loc == 'cloud' for loc in next_locations):
                    # Alle nachfolgenden Schritte sind in der Cloud
                    optimal_locations[data_id] = 'cloud'
                else:
                    # Gemischte Standorte: Speichere an beiden Orten
                    optimal_locations[data_id] = 'both'
            else:
                # Keine nachfolgenden Schritte: Speichere am Ausführungsort
                optimal_locations[data_id] = job['execution_location']
        
        # Aktualisiere Datenzugriffsmuster
        self._update_access_patterns(job, data_requirements)
        
        return {
            'job_id': job['job_id'],
            'optimal_data_locations': optimal_locations,
            'data_transfers_scheduled': [k for k, v in optimal_locations.items() 
                                        if 'transferring' in v]
        }
    
    def _schedule_data_transfer(self, data_id, source, destination, job_id):
        """Plant einen Datentransfer"""
        transfer_id = f"transfer_{uuid.uuid4().hex[:8]}"
        
        transfer_job = {
            'transfer_id': transfer_id,
            'data_id': data_id,
            'source': source,
            'destination': destination,
            'related_job_id': job_id,
            'status': 'scheduled',
            'priority': 'high',  # Hohe Priorität für Datentransfers
            'scheduled_at': datetime.now()
        }
        
        self.storage_manager.schedule_data_transfer(transfer_job)
        
        logging.info(f"Scheduled data transfer {transfer_id} for data {data_id} from {source} to {destination}")
        
        return transfer_id
    
    def _update_access_patterns(self, job, data_requirements):
        """Aktualisiert Datenzugriffsmuster"""
        now = datetime.now()
        
        # Aktualisiere für Eingabedaten
        for data_item in data_requirements['input_data']:
            data_id = data_item['data_id']
            
            if data_id not in self.data_access_patterns:
                self.data_access_patterns[data_id] = {
                    'access_count': 0,
                    'last_access': None,
                    'access_history': [],
                    'job_types': set()
                }
            
            # Aktualisiere Zugriffsmuster
            self.data_access_patterns[data_id]['access_count'] += 1
            self.data_access_patterns[data_id]['last_access'] = now
            self.data_access_patterns[data_id]['job_types'].add(job['type'])
            
            # Füge zum Zugriffsverlauf hinzu (begrenzt auf die letzten 100 Zugriffe)
            self.data_access_patterns[data_id]['access_history'].append({
                'timestamp': now,
                'job_id': job['job_id'],
                'job_type': job['type']
            })
            
            if len(self.data_access_patterns[data_id]['access_history']) > 100:
                self.data_access_patterns[data_id]['access_history'].pop(0)
        
        # Analysiere Zugriffsmuster für Caching-Entscheidungen
        self._update_cache_decisions()
    
    def _update_cache_decisions(self):
        """Aktualisiert Caching-Entscheidungen basierend auf Zugriffsmustern"""
        # Identifiziere häufig verwendete Daten für Caching
        cache_candidates = []
        
        for data_id, pattern in self.data_access_patterns.items():
            # Prüfe, ob die Daten bereits im Cache sind
            if self.cache_manager.is_cached(data_id):
                continue
            
            # Berechne Zugriffsfrequenz (Zugriffe pro Stunde in den letzten 24 Stunden)
            recent_accesses = [access for access in pattern['access_history'] 
                              if (datetime.now() - access['timestamp']).total_seconds() < 24 * 3600]
            
            if not recent_accesses:
                continue
            
            access_frequency = len(recent_accesses) / 24.0  # Zugriffe pro Stunde
            
            # Berechne Vielfalt der Jobtypen
            job_type_diversity = len(pattern['job_types'])
            
            # Berechne Cache-Priorität
            cache_priority = access_frequency * (1 + 0.1 * job_type_diversity)
            
            # Füge zu Cache-Kandidaten hinzu, wenn Priorität hoch genug ist
            if cache_priority > 0.5:  # Mindestens ein Zugriff alle 2 Stunden
                data_info = self.storage_manager.get_data_info(data_id)
                
                cache_candidates.append({
                    'data_id': data_id,
                    'priority': cache_priority,
                    'size_bytes': data_info['size_bytes'],
                    'last_access': pattern['last_access']
                })
        
        # Sortiere Kandidaten nach Priorität
        cache_candidates.sort(key=lambda x: x['priority'], reverse=True)
        
        # Aktualisiere Cache
        for candidate in cache_candidates:
            # Prüfe, ob genug Cache-Speicher verfügbar ist
            if self.cache_manager.has_space_for(candidate['size_bytes']):
                self.cache_manager.cache_data(candidate['data_id'], candidate['size_bytes'])
                logging.info(f"Added data {candidate['data_id']} to cache with priority {candidate['priority']}")
```

## 6. Fehlertoleranz und Wiederherstellung

### 6.1 Fehlererkennungs- und Wiederherstellungsmechanismen

#### Fehlerklassifizierung

Das System klassifiziert Fehler in verschiedene Kategorien:

- **Transiente Fehler**: Vorübergehende Fehler, die durch Wiederholung behoben werden können
- **Persistente Fehler**: Dauerhafte Fehler, die alternative Strategien erfordern
- **Systemfehler**: Fehler auf Systemebene, die Failover-Mechanismen erfordern

#### Wiederherstellungsstrategien

```python
class FaultToleranceManager:
    def __init__(self, job_manager, resource_manager, checkpoint_manager):
        self.job_manager = job_manager
        self.resource_manager = resource_manager
        self.checkpoint_manager = checkpoint_manager
        self.error_patterns = {}
        self.max_retry_attempts = 3
    
    def handle_job_failure(self, job_id, error_info):
        """Behandelt einen fehlgeschlagenen Job"""
        # Hole Job-Details
        job = self.job_manager.get_job(job_id)
        
        if not job:
            logging.error(f"Cannot handle failure for unknown job {job_id}")
            return {'status': 'error', 'message': 'Unknown job'}
        
        # Klassifiziere Fehler
        error_type = self._classify_error(error_info)
        
        # Aktualisiere Fehlermuster
        self._update_error_patterns(job, error_info, error_type)
        
        # Wähle Wiederherstellungsstrategie basierend auf Fehlertyp
        if error_type == 'transient':
            return self._handle_transient_error(job, error_info)
        elif error_type == 'persistent':
            return self._handle_persistent_error(job, error_info)
        elif error_type == 'system':
            return self._handle_system_error(job, error_info)
        else:  # 'unknown'
            return self._handle_unknown_error(job, error_info)
    
    def _classify_error(self, error_info):
        """Klassifiziert einen Fehler basierend auf Fehlermeldung und Kontext"""
        error_message = error_info.get('message', '').lower()
        error_code = error_info.get('code', '')
        
        # Transiente Fehler (vorübergehend, können durch Wiederholung behoben werden)
        transient_patterns = [
            'timeout', 'connection reset', 'network', 'temporary', 
            'resource temporarily unavailable', 'too many requests',
            'service unavailable', 'retry', 'overload'
        ]
        
        # Persistente Fehler (dauerhaft, erfordern alternative Strategien)
        persistent_patterns = [
            'permission denied', 'not found', 'invalid input', 
            'out of memory', 'disk full', 'quota exceeded',
            'invalid credentials', 'authentication failed'
        ]
        
        # Systemfehler (erfordern Failover)
        system_patterns = [
            'system failure', 'critical error', 'hardware failure',
            'host down', 'power failure', 'kernel panic',
            'segmentation fault', 'fatal error'
        ]
        
        # Prüfe auf bekannte Muster
        for pattern in transient_patterns:
            if pattern in error_message:
                return 'transient'
        
        for pattern in persistent_patterns:
            if pattern in error_message:
                return 'persistent'
        
        for pattern in system_patterns:
            if pattern in error_message:
                return 'system'
        
        # Prüfe auf bekannte Fehlercodes
        if error_code in ['ETIMEDOUT', 'ECONNRESET', 'ECONNREFUSED', '429', '503']:
            return 'transient'
        elif error_code in ['EACCES', 'EPERM', 'ENOENT', '403', '404']:
            return 'persistent'
        elif error_code in ['ENOMEM', 'ENOSPC', '507']:
            return 'system'
        
        # Standardfall: Unbekannter Fehler
        return 'unknown'
    
    def _handle_transient_error(self, job, error_info):
        """Behandelt einen transienten Fehler durch Wiederholung"""
        job_id = job['job_id']
        retry_count = job.get('retry_count', 0) + 1
        
        if retry_count <= self.max_retry_attempts:
            # Berechne exponentiellen Backoff für Wiederholungsversuch
            backoff_seconds = min(60, 2 ** retry_count)  # Max 60 Sekunden
            
            # Hole letzten Checkpoint, falls vorhanden
            checkpoint = self.checkpoint_manager.get_latest_checkpoint(job_id)
            
            # Plane Wiederholungsversuch
            retry_job = self.job_manager.clone_job(job_id, {
                'retry_count': retry_count,
                'original_job_id': job.get('original_job_id', job_id),
                'checkpoint_id': checkpoint['checkpoint_id'] if checkpoint else None,
                'scheduled_at': datetime.now() + timedelta(seconds=backoff_seconds),
                'error_history': job.get('error_history', []) + [{
                    'timestamp': datetime.now(),
                    'error_type': 'transient',
                    'error_info': error_info,
                    'action': 'retry'
                }]
            })
            
            logging.info(f"Scheduled retry {retry_count}/{self.max_retry_attempts} for job {job_id} after {backoff_seconds}s")
            
            return {
                'status': 'retry_scheduled',
                'retry_job_id': retry_job['job_id'],
                'retry_count': retry_count,
                'backoff_seconds': backoff_seconds
            }
        else:
            # Maximale Wiederholungsversuche erreicht, behandle als persistenten Fehler
            logging.warning(f"Max retry attempts ({self.max_retry_attempts}) reached for job {job_id}, treating as persistent error")
            return self._handle_persistent_error(job, error_info)
    
    def _handle_persistent_error(self, job, error_info):
        """Behandelt einen persistenten Fehler durch alternative Strategien"""
        job_id = job['job_id']
        
        # Versuche, eine alternative Ressource zu finden
        alternative_resource = self.resource_manager.find_alternative_resource(job['resource_requirements'])
        
        if alternative_resource:
            # Hole letzten Checkpoint, falls vorhanden
            checkpoint = self.checkpoint_manager.get_latest_checkpoint(job_id)
            
            # Erstelle neuen Job mit alternativer Ressource
            alternative_job = self.job_manager.clone_job(job_id, {
                'resource_id': alternative_resource['resource_id'],
                'original_job_id': job.get('original_job_id', job_id),
                'checkpoint_id': checkpoint['checkpoint_id'] if checkpoint else None,
                'scheduled_at': datetime.now(),
                'error_history': job.get('error_history', []) + [{
                    'timestamp': datetime.now(),
                    'error_type': 'persistent',
                    'error_info': error_info,
                    'action': 'alternative_resource'
                }]
            })
            
            logging.info(f"Rescheduled job {job_id} on alternative resource {alternative_resource['resource_id']}")
            
            return {
                'status': 'rescheduled',
                'alternative_job_id': alternative_job['job_id'],
                'alternative_resource_id': alternative_resource['resource_id']
            }
        else:
            # Keine alternative Ressource verfügbar, markiere Job als fehlgeschlagen
            self.job_manager.update_job_status(job_id, 'failed', {
                'error_type': 'persistent',
                'error_info': error_info,
                'failed_at': datetime.now()
            })
            
            logging.error(f"No alternative resource available for job {job_id}, marking as failed")
            
            return {
                'status': 'failed',
                'reason': 'No alternative resource available'
            }
    
    def _handle_system_error(self, job, error_info):
        """Behandelt einen Systemfehler durch Failover"""
        job_id = job['job_id']
        
        # Prüfe, ob Failover zu Cloud möglich ist
        if job.get('execution_location', 'local') == 'local' and not job.get('cloud_restricted', False):
            # Versuche Failover zu Cloud
            cloud_resource = self.resource_manager.find_cloud_resource(job['resource_requirements'])
            
            if cloud_resource:
                # Hole letzten Checkpoint, falls vorhanden
                checkpoint = self.checkpoint_manager.get_latest_checkpoint(job_id)
                
                # Erstelle neuen Job in der Cloud
                cloud_job = self.job_manager.clone_job(job_id, {
                    'resource_id': cloud_resource['resource_id'],
                    'execution_location': 'cloud',
                    'original_job_id': job.get('original_job_id', job_id),
                    'checkpoint_id': checkpoint['checkpoint_id'] if checkpoint else None,
                    'scheduled_at': datetime.now(),
                    'error_history': job.get('error_history', []) + [{
                        'timestamp': datetime.now(),
                        'error_type': 'system',
                        'error_info': error_info,
                        'action': 'cloud_failover'
                    }]
                })
                
                logging.info(f"Performed cloud failover for job {job_id} to resource {cloud_resource['resource_id']}")
                
                return {
                    'status': 'cloud_failover',
                    'cloud_job_id': cloud_job['job_id'],
                    'cloud_resource_id': cloud_resource['resource_id']
                }
        
        # Kein Failover möglich oder bereits in der Cloud, behandle als persistenten Fehler
        return self._handle_persistent_error(job, error_info)
    
    def _handle_unknown_error(self, job, error_info):
        """Behandelt einen unbekannten Fehler"""
        # Für unbekannte Fehler: Versuche einmal zu wiederholen, dann als persistent behandeln
        job_id = job['job_id']
        retry_count = job.get('retry_count', 0)
        
        if retry_count == 0:
            # Erster Versuch: Behandle wie transienten Fehler
            return self._handle_transient_error(job, error_info)
        else:
            # Bereits wiederholt: Behandle wie persistenten Fehler
            return self._handle_persistent_error(job, error_info)
    
    def _update_error_patterns(self, job, error_info, error_type):
        """Aktualisiert Fehlermuster für zukünftige Klassifizierung"""
        error_message = error_info.get('message', '')
        error_code = error_info.get('code', '')
        
        if not error_message and not error_code:
            return  # Keine ausreichenden Informationen
        
        # Erstelle Schlüssel für Fehlermuster
        pattern_key = f"{error_code}:{error_message[:50]}"
        
        if pattern_key not in self.error_patterns:
            self.error_patterns[pattern_key] = {
                'occurrences': 0,
                'first_seen': datetime.now(),
                'last_seen': datetime.now(),
                'job_types': set(),
                'error_types': {},
                'resolution_success': {}
            }
        
        # Aktualisiere Muster
        pattern = self.error_patterns[pattern_key]
        pattern['occurrences'] += 1
        pattern['last_seen'] = datetime.now()
        pattern['job_types'].add(job['type'])
        
        # Zähle Fehlertypen
        if error_type not in pattern['error_types']:
            pattern['error_types'][error_type] = 0
        pattern['error_types'][error_type] += 1