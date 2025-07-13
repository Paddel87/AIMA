# Metriken-Erfassung und -Bereitstellung

Dieses Dokument spezifiziert die Erfassung, Verarbeitung und Bereitstellung von GPU-Nutzungsmetriken und anderen Systemmetriken im AIMA-System.

## 1. Übersicht

Die Metriken-Erfassung ist ein zentraler Bestandteil des AIMA-Systems und dient mehreren Zwecken:

- **Ressourcenoptimierung**: Identifikation von Engpässen und Optimierungspotentialen
- **Kostenüberwachung**: Transparenz über Ressourcenverbrauch und entstehende Kosten
- **Leistungsanalyse**: Bewertung der Systemleistung und Identifikation von Verbesserungsmöglichkeiten
- **Fehlerdiagnose**: Unterstützung bei der Identifikation und Behebung von Problemen
- **Kapazitätsplanung**: Datenbasierte Entscheidungen für zukünftige Ressourcenanforderungen

## 2. Erfasste Metriken

### 2.1 GPU-Metriken

| Metrik | Beschreibung | Einheit | Erfassungsintervall |
|--------|-------------|---------|---------------------|
| GPU-Auslastung | Prozentsatz der GPU-Rechenkapazität, die genutzt wird | % | 10 Sekunden |
| GPU-Speichernutzung | Menge des belegten GPU-Speichers | MB/GB | 10 Sekunden |
| GPU-Speicherauslastung | Prozentsatz des genutzten GPU-Speichers | % | 10 Sekunden |
| GPU-Temperatur | Betriebstemperatur der GPU | °C | 30 Sekunden |
| GPU-Leistungsaufnahme | Stromverbrauch der GPU | Watt | 30 Sekunden |
| CUDA-Kernel-Ausführungszeit | Zeit, die für die Ausführung von CUDA-Kernels benötigt wird | ms | Pro Kernel-Aufruf |
| Tensor-Core-Nutzung | Nutzung spezialisierter Tensor-Cores (bei unterstützten GPUs) | % | 10 Sekunden |
| PCIe-Durchsatz | Datenübertragungsrate zwischen CPU und GPU | MB/s | 30 Sekunden |

### 2.2 Jobspezifische Metriken

| Metrik | Beschreibung | Einheit | Erfassungsintervall |
|--------|-------------|---------|---------------------|
| Verarbeitungszeit pro Frame | Zeit für die Verarbeitung eines einzelnen Frames | ms | Pro Frame |
| Durchschnittliche Inferenzzeit | Durchschnittliche Zeit für einen Inferenzschritt | ms | Pro Batch |
| Batch-Verarbeitungszeit | Zeit für die Verarbeitung eines Batches | ms | Pro Batch |
| Modellladedauer | Zeit zum Laden eines Modells in den GPU-Speicher | ms | Pro Modellladung |
| Datentransferzeit | Zeit für die Übertragung von Daten zwischen CPU und GPU | ms | Pro Transfer |
| Warteschlangenlänge | Anzahl der Jobs in der Warteschlange | Anzahl | 10 Sekunden |
| Wartedauer | Zeit, die ein Job in der Warteschlange verbringt | Sekunden | Pro Job |

### 2.3 Systemmetriken

| Metrik | Beschreibung | Einheit | Erfassungsintervall |
|--------|-------------|---------|---------------------|
| CPU-Auslastung | Prozentsatz der CPU-Kapazität, die genutzt wird | % | 10 Sekunden |
| RAM-Nutzung | Menge des genutzten Arbeitsspeichers | MB/GB | 10 Sekunden |
| Festplattennutzung | Belegter Speicherplatz | GB/TB | 5 Minuten |
| Netzwerkdurchsatz | Datenübertragungsrate über das Netzwerk | MB/s | 30 Sekunden |
| Containeranzahl | Anzahl der aktiven Container | Anzahl | 1 Minute |
| Pod-Status | Status der Kubernetes-Pods | Status | 30 Sekunden |

### 2.4 Kosten- und Abrechnungsmetriken

| Metrik | Beschreibung | Einheit | Erfassungsintervall |
|--------|-------------|---------|---------------------|
| GPU-Stunden | Gesamtnutzungsdauer der GPUs | Stunden | Stündlich |
| Geschätzte Kosten | Geschätzte Kosten basierend auf aktueller Nutzung | EUR | Stündlich |
| Kosten pro Job | Tatsächliche Kosten eines abgeschlossenen Jobs | EUR | Pro Job |
| Kosten pro Medienminute | Kosten pro Minute verarbeiteten Medienmaterials | EUR | Pro Job |
| Budget-Auslastung | Prozentsatz des verbrauchten Budgets | % | Täglich |

## 3. Erfassungsmethoden

### 3.1 Technische Implementierung

Die Metriken werden durch eine Kombination verschiedener Technologien erfasst:

```python
# Beispiel für die Implementierung eines GPU-Metrik-Collectors mit NVIDIA Management Library (NVML)
import pynvml
import time
import json
from datetime import datetime

class GPUMetricsCollector:
    def __init__(self, collection_interval=10, output_file=None, prometheus_endpoint=None):
        self.collection_interval = collection_interval  # in Sekunden
        self.output_file = output_file
        self.prometheus_endpoint = prometheus_endpoint
        self.metrics = []
        pynvml.nvmlInit()
        self.device_count = pynvml.nvmlDeviceGetCount()
        
    def collect_metrics(self):
        timestamp = datetime.now().isoformat()
        gpu_metrics = []
        
        for i in range(self.device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            
            # Basis-Informationen
            name = pynvml.nvmlDeviceGetName(handle)
            
            # Auslastung
            utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_util = utilization.gpu
            mem_util = utilization.memory
            
            # Speicher
            memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
            mem_total = memory.total / 1024**2  # MB
            mem_used = memory.used / 1024**2    # MB
            mem_free = memory.free / 1024**2    # MB
            
            # Temperatur und Leistung
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Watt
            
            gpu_metric = {
                "device_id": i,
                "name": name,
                "utilization": gpu_util,
                "memory_utilization": mem_util,
                "memory_total_mb": mem_total,
                "memory_used_mb": mem_used,
                "memory_free_mb": mem_free,
                "temperature_c": temp,
                "power_usage_watts": power
            }
            
            gpu_metrics.append(gpu_metric)
        
        metric_entry = {
            "timestamp": timestamp,
            "gpu_metrics": gpu_metrics
        }
        
        self.metrics.append(metric_entry)
        
        # Speichern oder Exportieren der Metriken
        if self.output_file:
            self._write_to_file()
        
        if self.prometheus_endpoint:
            self._export_to_prometheus(metric_entry)
    
    def _write_to_file(self):
        with open(self.output_file, 'w') as f:
            json.dump(self.metrics, f, indent=2)
    
    def _export_to_prometheus(self, metric_entry):
        # Implementierung des Prometheus-Exports
        # Hier würden die Metriken in das Prometheus-Format konvertiert
        # und an den konfigurierten Endpunkt gesendet
        pass
    
    def start_collection(self, duration=None):
        """Startet die Metrikensammlung für eine bestimmte Dauer oder unbegrenzt."""
        start_time = time.time()
        try:
            while duration is None or time.time() - start_time < duration:
                self.collect_metrics()
                time.sleep(self.collection_interval)
        except KeyboardInterrupt:
            print("Metrikensammlung wurde manuell beendet.")
        finally:
            pynvml.nvmlShutdown()
            if self.output_file:
                self._write_to_file()

# Verwendungsbeispiel
if __name__ == "__main__":
    collector = GPUMetricsCollector(
        collection_interval=10,
        output_file="gpu_metrics.json"
    )
    collector.start_collection(duration=3600)  # Sammle für eine Stunde
```

### 3.2 Integrationen mit Monitoring-Tools

Das AIMA-System integriert sich mit folgenden Monitoring-Tools:

1. **Prometheus**: Für die Erfassung und Speicherung von Zeitreihendaten
2. **Grafana**: Für die Visualisierung und Dashboards
3. **Kubernetes Metrics Server**: Für Container- und Pod-Metriken
4. **NVIDIA Data Center GPU Manager (DCGM)**: Für detaillierte GPU-Metriken
5. **OpenTelemetry**: Für verteiltes Tracing und Metriken-Sammlung

```yaml
# Beispiel für eine Prometheus-Konfiguration zur Erfassung von GPU-Metriken
scrape_configs:
  - job_name: 'gpu_metrics'
    scrape_interval: 10s
    static_configs:
      - targets: ['gpu-exporter:9400']
        labels:
          service: 'aima-gpu-metrics'
  
  - job_name: 'aima_services'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: aima-.*
        action: keep
      - source_labels: [__meta_kubernetes_pod_label_component]
        target_label: component
```

## 4. Datenverarbeitung und -speicherung

### 4.1 Aggregation und Sampling

Um die Datenmenge zu reduzieren und gleichzeitig aussagekräftige Informationen zu bewahren, werden folgende Aggregationsstrategien angewendet:

| Zeitraum | Aggregationsmethode | Aufbewahrungsdauer |
|----------|---------------------|--------------------|
| Echtzeit (< 1 Stunde) | Keine (Rohdaten) | 24 Stunden |
| Stündlich | Min, Max, Avg, 95. Perzentil | 7 Tage |
| Täglich | Min, Max, Avg, 95. Perzentil | 30 Tage |
| Monatlich | Min, Max, Avg, 95. Perzentil | 1 Jahr |
| Jährlich | Min, Max, Avg, 95. Perzentil | Unbegrenzt |

### 4.2 Speicherformat und -ort

Die Metriken werden in folgenden Formaten und an folgenden Orten gespeichert:

1. **Kurzfristige Speicherung**: Prometheus TSDB (Time Series Database)
2. **Langfristige Speicherung**: InfluxDB oder TimescaleDB
3. **Exportformate**: JSON, CSV, Prometheus Remote Write Format
4. **Speicherorte**:
   - Lokaler Speicher für kurzfristige Daten
   - Objektspeicher (S3, MinIO) für langfristige Archivierung
   - Verteilte Datenbank für hochverfügbaren Zugriff

### 4.3 Datenkomprimierung

Zur Reduzierung des Speicherbedarfs werden folgende Komprimierungstechniken eingesetzt:

- **Gorilla-Komprimierung** für Zeitreihendaten
- **Delta-Encoding** für aufeinanderfolgende Zeitstempel
- **Downsampling** für ältere Daten
- **Selektive Speicherung** basierend auf Relevanz und Varianz

## 5. Bereitstellung und Visualisierung

### 5.1 Dashboard-Konzept

Das AIMA-System bietet verschiedene Dashboards für unterschiedliche Benutzerrollen und Anwendungsfälle:

#### 5.1.1 Administratoren-Dashboard

![Administratoren-Dashboard](https://example.com/admin-dashboard.png)

Das Administratoren-Dashboard umfasst:

- Gesamtsystemübersicht mit Gesundheitsstatus
- GPU-Auslastung und -Verfügbarkeit in Echtzeit
- Warnungen und Alarme
- Ressourcennutzung nach Diensten und Benutzern
- Kapazitätsplanung und Trends

#### 5.1.2 Benutzer-Dashboard

Das Benutzer-Dashboard zeigt:

- Status eigener Jobs und Analysen
- Ressourcenverbrauch und geschätzte Kosten
- Historische Nutzung und Trends
- Leistungsmetriken für abgeschlossene Analysen

#### 5.1.3 Finanz-Dashboard

Das Finanz-Dashboard bietet:

- Kostenübersicht nach Diensten, Projekten und Benutzern
- Budget-Tracking und -Prognosen
- Kostenoptimierungsvorschläge
- Abrechnungsberichte

### 5.2 API-Zugriff

Das AIMA-System stellt eine REST-API für den programmatischen Zugriff auf Metriken bereit:

```python
# Beispiel für die API-Implementierung mit FastAPI
from fastapi import FastAPI, Query, Path, Depends, HTTPException
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
from .metrics_repository import MetricsRepository
from .auth import get_current_user, User

app = FastAPI(title="AIMA Metrics API")

class MetricResponse(BaseModel):
    timestamp: datetime
    metric_name: str
    value: float
    labels: dict

class AggregatedMetricResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    metric_name: str
    min_value: float
    max_value: float
    avg_value: float
    percentile_95: float
    labels: dict

@app.get("/metrics/raw/{metric_name}", response_model=List[MetricResponse])
async def get_raw_metrics(
    metric_name: str = Path(..., description="Name der Metrik"),
    start_time: datetime = Query(None, description="Startzeit (ISO-Format)"),
    end_time: datetime = Query(None, description="Endzeit (ISO-Format)"),
    labels: Optional[str] = Query(None, description="Filter nach Labels (Format: key1=value1,key2=value2)"),
    limit: int = Query(1000, description="Maximale Anzahl der zurückgegebenen Datenpunkte"),
    current_user: User = Depends(get_current_user)
):
    if start_time is None:
        start_time = datetime.now() - timedelta(hours=1)
    if end_time is None:
        end_time = datetime.now()
        
    # Konvertiere Labels-String in Dictionary
    label_dict = {}
    if labels:
        for label_pair in labels.split(','):
            key, value = label_pair.split('=')
            label_dict[key] = value
    
    # Prüfe Berechtigungen
    if not current_user.has_permission(f"metrics:read:{metric_name}"):
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Metrik")
    
    # Hole Daten aus Repository
    metrics_repo = MetricsRepository()
    raw_metrics = await metrics_repo.get_raw_metrics(
        metric_name=metric_name,
        start_time=start_time,
        end_time=end_time,
        labels=label_dict,
        limit=limit
    )
    
    return raw_metrics

@app.get("/metrics/aggregated/{metric_name}", response_model=List[AggregatedMetricResponse])
async def get_aggregated_metrics(
    metric_name: str = Path(..., description="Name der Metrik"),
    start_time: datetime = Query(None, description="Startzeit (ISO-Format)"),
    end_time: datetime = Query(None, description="Endzeit (ISO-Format)"),
    interval: str = Query("1h", description="Aggregationsintervall (z.B. 5m, 1h, 1d)"),
    labels: Optional[str] = Query(None, description="Filter nach Labels (Format: key1=value1,key2=value2)"),
    current_user: User = Depends(get_current_user)
):
    # Ähnliche Implementierung wie oben, aber mit Aggregation
    # ...
    pass
```

### 5.3 Benachrichtigungen und Alarme

Das AIMA-System implementiert ein umfassendes Benachrichtigungssystem für Metriken:

```python
# Beispiel für die Implementierung von Benachrichtigungsregeln
class AlertRule:
    def __init__(self, metric_name, condition, threshold, duration, severity, notification_channels):
        self.metric_name = metric_name
        self.condition = condition  # 'gt', 'lt', 'eq', etc.
        self.threshold = threshold
        self.duration = duration  # Wie lange die Bedingung erfüllt sein muss
        self.severity = severity  # 'critical', 'warning', 'info'
        self.notification_channels = notification_channels
        self.last_check = None
        self.is_firing = False
        self.firing_since = None
    
    def evaluate(self, metric_value, timestamp):
        condition_met = False
        
        if self.condition == 'gt':
            condition_met = metric_value > self.threshold
        elif self.condition == 'lt':
            condition_met = metric_value < self.threshold
        elif self.condition == 'eq':
            condition_met = metric_value == self.threshold
        # Weitere Bedingungen...
        
        if condition_met:
            if not self.is_firing:
                if self.firing_since is None:
                    self.firing_since = timestamp
                elif (timestamp - self.firing_since) >= self.duration:
                    self.is_firing = True
                    return True  # Alarm auslösen
        else:
            self.is_firing = False
            self.firing_since = None
        
        return False

class AlertManager:
    def __init__(self):
        self.rules = []
        self.notification_services = {}
    
    def add_rule(self, rule):
        self.rules.append(rule)
    
    def register_notification_service(self, name, service):
        self.notification_services[name] = service
    
    def process_metric(self, metric_name, metric_value, labels, timestamp):
        for rule in self.rules:
            if rule.metric_name == metric_name:
                if rule.evaluate(metric_value, timestamp):
                    self._send_alert(rule, metric_name, metric_value, labels, timestamp)
    
    def _send_alert(self, rule, metric_name, metric_value, labels, timestamp):
        alert = {
            "metric_name": metric_name,
            "value": metric_value,
            "threshold": rule.threshold,
            "condition": rule.condition,
            "severity": rule.severity,
            "labels": labels,
            "timestamp": timestamp,
            "message": f"{rule.severity.upper()}: {metric_name} is {rule.condition} {rule.threshold} (current value: {metric_value})"
        }
        
        for channel in rule.notification_channels:
            if channel in self.notification_services:
                self.notification_services[channel].send_alert(alert)
```

#### 5.3.1 Benachrichtigungskanäle

Das System unterstützt folgende Benachrichtigungskanäle:

- E-Mail
- Slack/Microsoft Teams
- SMS
- Push-Benachrichtigungen in der Web-UI
- Webhook-Integration für externe Systeme

#### 5.3.2 Alarmregeln

Vordefinierte Alarmregeln umfassen:

- GPU-Auslastung > 95% für mehr als 10 Minuten
- GPU-Temperatur > 85°C
- GPU-Speichernutzung > 90%
- Job-Warteschlange > 20 Jobs für mehr als 30 Minuten
- Fehlerrate > 5% in den letzten 5 Minuten

## 6. Anwendungsfälle

### 6.1 Leistungsoptimierung

Die erfassten Metriken werden für folgende Optimierungen genutzt:

1. **Batch-Größenoptimierung**: Anpassung der Batch-Größe basierend auf GPU-Speichernutzung und Verarbeitungszeit
2. **Modellauswahl**: Auswahl des optimalen Modells basierend auf Leistungs-/Genauigkeits-Tradeoff
3. **Ressourcenzuweisung**: Optimale Zuweisung von Jobs zu GPUs basierend auf Auslastungsprofilen
4. **Parallelisierungsgrad**: Anpassung der Anzahl paralleler Prozesse basierend auf Systemauslastung

### 6.2 Kostenoptimierung

Die Metriken unterstützen folgende Kostenoptimierungsstrategien:

1. **Anbieterauswahl**: Auswahl des kostengünstigsten Cloud-Anbieters basierend auf aktuellen Preisen und Leistungsanforderungen
2. **Spot-Instanzen**: Nutzung von Spot-Instanzen für nicht zeitkritische Jobs
3. **Autoscaling**: Automatische Skalierung basierend auf Auslastung und Warteschlangenlänge
4. **Ressourcenfreigabe**: Frühzeitige Freigabe ungenutzter Ressourcen

### 6.3 Fehlerdiagnose

Die Metriken werden für folgende Diagnoseaufgaben verwendet:

1. **Root-Cause-Analyse**: Identifikation der Ursache von Leistungsproblemen oder Fehlern
2. **Anomalieerkennung**: Erkennung ungewöhnlicher Muster in der Systemleistung
3. **Korrelationsanalyse**: Korrelation von Ereignissen über verschiedene Systemkomponenten hinweg
4. **Trendanalyse**: Identifikation langfristiger Trends und potenzieller zukünftiger Probleme

## 7. Datenschutz und Sicherheit

### 7.1 Datenschutzmaßnahmen

Folgende Maßnahmen stellen sicher, dass die Metrikenerfassung den Datenschutzanforderungen entspricht:

1. **Anonymisierung**: Keine Erfassung personenbezogener Daten in Metriken
2. **Aggregation**: Aggregation von Daten, um Rückschlüsse auf einzelne Benutzer zu verhindern
3. **Zugriffskontrollen**: Strikte Zugriffskontrollen für Metrikendaten
4. **Aufbewahrungsfristen**: Definierte Aufbewahrungsfristen für verschiedene Metrikentypen

### 7.2 Sicherheitsmaßnahmen

Folgende Sicherheitsmaßnahmen schützen die Metrikendaten:

1. **Verschlüsselung**: Verschlüsselung der Metrikendaten bei der Übertragung und Speicherung
2. **Authentifizierung**: Starke Authentifizierung für den Zugriff auf Metriken-APIs und -Dashboards
3. **Autorisierung**: Rollenbasierte Zugriffskontrollen für Metrikendaten
4. **Audit-Logging**: Protokollierung aller Zugriffe auf Metrikendaten

## 8. Implementierungsplan

### 8.1 Phasen

Die Implementierung der Metriken-Erfassung und -Bereitstellung erfolgt in folgenden Phasen:

#### Phase 1: Grundlegende Infrastruktur

- Einrichtung von Prometheus und Grafana
- Implementierung der GPU-Metrikenerfassung
- Erstellung grundlegender Dashboards
- Integration in die Kubernetes-Umgebung

#### Phase 2: Erweiterte Funktionen

- Implementierung der langfristigen Speicherung
- Entwicklung der Metriken-API
- Erstellung erweiterter Dashboards
- Implementierung des Benachrichtigungssystems

#### Phase 3: Optimierung und Integration

- Integration mit dem Kostenschätzungssystem
- Implementierung von Anomalieerkennung
- Optimierung der Datenerfassung und -speicherung
- Integration mit externen Monitoring-Systemen

### 8.2 Zeitplan

| Phase | Dauer | Abhängigkeiten |
|-------|-------|----------------|
| Phase 1 | 4 Wochen | Kubernetes-Infrastruktur |
| Phase 2 | 6 Wochen | Abschluss von Phase 1 |
| Phase 3 | 4 Wochen | Abschluss von Phase 2 |

## 9. Zusammenfassung

Die Metriken-Erfassung und -Bereitstellung im AIMA-System bietet eine umfassende Lösung für die Überwachung, Analyse und Optimierung der Systemleistung und -kosten. Durch die Kombination verschiedener Metriken, fortschrittlicher Verarbeitungs- und Visualisierungstechniken sowie intelligenter Alarmierung ermöglicht das System eine effiziente Ressourcennutzung, frühzeitige Problemerkennung und datenbasierte Entscheidungsfindung.

Die modulare Architektur und die Integration mit Standardtools wie Prometheus und Grafana gewährleisten Flexibilität, Skalierbarkeit und Zukunftssicherheit. Gleichzeitig stellen die implementierten Datenschutz- und Sicherheitsmaßnahmen sicher, dass die Metrikenerfassung den höchsten Standards entspricht.