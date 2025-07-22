# AIMA GPU Orchestration Service

🚀 **Phase 2.2: Job- und GPU-Orchestrierung** - Gestartet am 22.07.2025

Ein umfassender GPU-Orchestrierungsservice für die Verwaltung von KI-Workloads über mehrere Cloud-Anbieter hinweg, einschließlich RunPod, Vast.ai und AWS.

## 🎯 Überblick

Der AIMA GPU Orchestration Service bietet:

- **Job Queue Management**: Intelligente Warteschlangenverwaltung und Scheduling
- **Multi-Provider GPU Orchestration**: Unterstützung für RunPod, Vast.ai und AWS
- **Kostenoptimierung**: Automatische Anbieterauswahl basierend auf Kosten und Verfügbarkeit
- **LLaVA & Llama Integration**: Spezialisierte Templates für LLaVA-1.6 (34B) und Llama 3.1 (70B)
- **Real-time Monitoring**: Prometheus-Metriken und Grafana-Dashboards
- **Auto-Scaling**: Automatische Skalierung basierend auf Workload

## 🏗️ Architektur

### GPU Cluster Konfiguration
- **6x RTX 4090** (144GB VRAM gesamt)
- **4x GPUs** für LLaVA-1.6 (34B)
- **2x GPUs** für Llama 3.1 (70B)
- **Load Balancing** zwischen Instanzen

### Technische Komponenten
- **FastAPI** - REST API Framework
- **PostgreSQL** - Primäre Datenbank
- **Redis** - Caching und Session Management
- **RabbitMQ** - Message Queue für Job Processing
- **Kubernetes** - Container Orchestration
- **Terraform** - Infrastructure as Code
- **Prometheus & Grafana** - Monitoring und Metriken

## 🚀 Schnellstart

### Voraussetzungen

- Python 3.11+
- Docker & Docker Compose
- kubectl (für Kubernetes Integration)
- Terraform (für Infrastructure Management)

### Installation

1. **Repository klonen**
   ```bash
   git clone https://github.com/aima/gpu-orchestration.git
   cd gpu-orchestration
   ```

2. **Umgebungsvariablen konfigurieren**
   ```bash
   cp .env.example .env
   # Bearbeite .env mit deinen API-Schlüsseln
   ```

3. **Services mit Docker Compose starten**
   ```bash
   docker-compose up -d
   ```

4. **Datenbank initialisieren**
   ```bash
   docker-compose exec gpu-orchestration python start_service.py --init-db
   ```

### Lokale Entwicklung

1. **Virtuelle Umgebung erstellen**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # oder
   venv\Scripts\activate     # Windows
   ```

2. **Dependencies installieren**
   ```bash
   pip install -r requirements.txt
   ```

3. **Service starten**
   ```bash
   python start_service.py
   ```

## 📚 API Dokumentation

Nach dem Start ist die API-Dokumentation verfügbar unter:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Wichtige Endpoints

#### Job Management
- `POST /api/v1/jobs/submit` - Neuen Job einreichen
- `GET /api/v1/jobs/{job_id}` - Job-Status abrufen
- `GET /api/v1/jobs/` - Jobs auflisten
- `DELETE /api/v1/jobs/{job_id}` - Job abbrechen

#### GPU Instanzen
- `GET /api/v1/instances/` - Aktive Instanzen auflisten
- `GET /api/v1/instances/{instance_id}` - Instanz-Details
- `DELETE /api/v1/instances/{instance_id}` - Instanz beenden

#### Provider Management
- `GET /api/v1/providers/` - Verfügbare Provider
- `GET /api/v1/providers/{provider}/pricing` - Preise abrufen
- `GET /api/v1/providers/{provider}/status` - Provider-Status

#### Monitoring
- `GET /health` - Service Health Check
- `GET /metrics` - Prometheus Metriken
- `GET /api/v1/monitoring/dashboard` - Dashboard-Daten

## 🔧 Konfiguration

### GPU Provider Setup

#### RunPod
1. Account erstellen auf [RunPod](https://www.runpod.io)
2. API-Schlüssel generieren in den User Settings
3. `RUNPOD_API_KEY` in `.env` setzen

#### Vast.ai
1. Account erstellen auf [Vast.ai](https://console.vast.ai)
2. API-Schlüssel in Account Settings generieren
3. `VAST_API_KEY` in `.env` setzen

#### AWS
1. IAM User mit EC2-Berechtigungen erstellen
2. Access Key und Secret Key generieren
3. `AWS_ACCESS_KEY_ID` und `AWS_SECRET_ACCESS_KEY` setzen

### Job Templates

Vordefinierte Templates für häufige Anwendungsfälle:

#### LLaVA-1.6 34B Template
```json
{
  "name": "LLaVA-1.6 34B Analysis",
  "job_type": "llava",
  "config": {
    "model_name": "llava-v1.6-34b",
    "gpu_type": "RTX4090",
    "gpu_count": 4,
    "memory_gb": 96,
    "docker_image": "aima/llava:1.6-34b"
  }
}
```

#### Llama 3.1 70B Template
```json
{
  "name": "Llama 3.1 70B Text Generation",
  "job_type": "llama",
  "config": {
    "model_name": "llama-3.1-70b",
    "gpu_type": "RTX4090",
    "gpu_count": 2,
    "memory_gb": 48,
    "docker_image": "aima/llama:3.1-70b"
  }
}
```

## 📊 Monitoring

### Grafana Dashboards
Zugriff auf Grafana: http://localhost:3000
- **Username**: admin
- **Password**: admin

Verfügbare Dashboards:
- GPU Orchestration Overview
- Job Performance Metrics
- Provider Comparison
- Cost Analysis
- System Resources

### Prometheus Metriken
Zugriff auf Prometheus: http://localhost:9091

Wichtige Metriken:
- `gpu_jobs_total` - Gesamtanzahl Jobs
- `gpu_instances_active` - Aktive GPU-Instanzen
- `gpu_cost_hourly` - Stündliche Kosten
- `gpu_utilization_percent` - GPU-Auslastung

## 🔒 Sicherheit

### API-Authentifizierung
- JWT-Token basierte Authentifizierung
- Benutzer-spezifische Ressourcen-Quotas
- Rate Limiting für API-Endpoints

### Secrets Management
- Alle API-Schlüssel werden verschlüsselt gespeichert
- Umgebungsvariablen für sensible Daten
- Kubernetes Secrets für Production

## 🧪 Testing

### Unit Tests
```bash
pytest tests/unit/
```

### Integration Tests
```bash
pytest tests/integration/
```

### Load Tests
```bash
pytest tests/load/
```

## 📈 Performance

### Benchmarks
- **Job Submission**: < 100ms
- **Instance Creation**: 2-5 Minuten (abhängig vom Provider)
- **API Response Time**: < 50ms (95th percentile)
- **Throughput**: 1000+ Jobs/Stunde

### Skalierung
- **Horizontal Scaling**: Mehrere Service-Instanzen
- **Auto-Scaling**: Basierend auf Queue-Länge
- **Load Balancing**: Nginx/HAProxy Integration

## 🛠️ Entwicklung

### Code-Struktur
```
app/
├── api/           # FastAPI Router
├── core/          # Konfiguration & Database
├── models/        # SQLAlchemy Models
├── providers/     # GPU Provider Implementierungen
└── services/      # Business Logic
```

### Beitragen
1. Fork das Repository
2. Feature Branch erstellen (`git checkout -b feature/amazing-feature`)
3. Änderungen committen (`git commit -m 'Add amazing feature'`)
4. Branch pushen (`git push origin feature/amazing-feature`)
5. Pull Request erstellen

### Code Style
- **Black** für Code-Formatierung
- **isort** für Import-Sortierung
- **flake8** für Linting
- **mypy** für Type Checking

```bash
# Code formatieren
black app/
isort app/

# Linting
flake8 app/
mypy app/
```

## 📋 Roadmap

### Phase 2.2 (Aktuell) - Q3 2025
- [x] Job Management Module
- [x] GPU Orchestration Module
- [x] RunPod Integration
- [ ] Vast.ai Integration
- [ ] LLaVA-1.6 Container Images
- [ ] Load Balancing Implementation

### Phase 2.3 - Q4 2025
- [ ] AWS Integration
- [ ] Advanced Cost Optimization
- [ ] Multi-Region Support
- [ ] Enhanced Monitoring

### Phase 3.0 - Q1 2026
- [ ] Machine Learning Scheduling
- [ ] Predictive Scaling
- [ ] Advanced Analytics
- [ ] Multi-Tenant Support

## 🐛 Troubleshooting

### Häufige Probleme

#### Service startet nicht
```bash
# Logs überprüfen
docker-compose logs gpu-orchestration

# Datenbank-Verbindung testen
docker-compose exec postgres psql -U postgres -d gpu_orchestration
```

#### GPU Provider Fehler
```bash
# Provider-Status überprüfen
curl http://localhost:8000/api/v1/providers/runpod/status

# API-Schlüssel validieren
curl -H "Authorization: Bearer $RUNPOD_API_KEY" https://api.runpod.ai/graphql
```

#### Performance Probleme
```bash
# System-Metriken überprüfen
curl http://localhost:8000/api/v1/monitoring/metrics/system

# Datenbankverbindungen
docker-compose exec postgres psql -U postgres -c "SELECT * FROM pg_stat_activity;"
```

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/aima/gpu-orchestration/issues)
- **Dokumentation**: [Wiki](https://github.com/aima/gpu-orchestration/wiki)
- **Email**: team@aima.ai
- **Slack**: #gpu-orchestration

## 📄 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe [LICENSE](LICENSE) für Details.

## 🙏 Danksagungen

- RunPod Team für die ausgezeichnete GPU-Cloud-Plattform
- Vast.ai für kostengünstige GPU-Ressourcen
- FastAPI Community für das großartige Framework
- AIMA Team für die kontinuierliche Unterstützung

---

**AIMA GPU Orchestration Service** - Powering the Future of AI Workloads 🚀