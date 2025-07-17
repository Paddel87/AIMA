# AIMA - AI Media Analysis

[![Version](https://img.shields.io/badge/version-0.3.1--alpha-blue.svg)](https://github.com/Paddel87/AIMA/releases/tag/v0.3.1-alpha)
[![License](https://img.shields.io/badge/license-TBD-lightgrey.svg)](#)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](#)
[![Development Status](https://img.shields.io/badge/status-alpha-orange.svg)](#)
[![AI Powered](https://img.shields.io/badge/AI-powered-purple.svg)](#)
[![GPU Ready](https://img.shields.io/badge/GPU-ready-green.svg)](#)
[![Microservices](https://img.shields.io/badge/architecture-microservices-blue.svg)](#)

🤖 **Künstliche Intelligenz für umfassende Medienanalyse**

AIMA ist ein fortschrittliches KI-System zur automatisierten Analyse von Audio-, Bild- und Videodateien. Das System nutzt modernste Machine Learning-Modelle und GPU-Computing für die Erkennung von Personen, Objekten, Emotionen und Kontextinformationen.

## 🎯 Vision

Dieses Projekt folgt einem **Vision Driven Development**-Ansatz, bei dem eine KI schrittweise die Systemarchitektur und technischen Details ausarbeitet. Die menschliche Rolle beschränkt sich auf die Definition der Zielrichtung und übergeordneten Prinzipien.

## 🚀 Hauptfunktionen

### 📸 Bildanalyse
- Personen- und Objekterkennung
- Emotionsanalyse
- Kontextinformationen
- Parallele Verarbeitung von Bildserien

### 🎥 Videoanalyse
- Bewegungserkennung
- Zeitliche Zusammenhänge
- Audio-Stream-Analyse
- Multimodale Fusion

### 🎵 Audioanalyse
- Spracherkennung
- Emotionsanalyse
- Nicht-linguistische Informationen
- Akustische Merkmale

### ☁️ GPU-Cloud-Integration
- Automatische GPU-Ressourcenverwaltung
- Container-basierte ML-Modell-Deployment
- Skalierbare Cloud-Infrastruktur
- Sichere Datenübertragung

## 🏗️ Systemarchitektur

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Medienupload  │───▶│  Vorverarbeitung │───▶│ GPU-Orchestrierung│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Ergebnisdossier │◀───│   Datenfusion   │◀───│  ML-Modell-Farm │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🧠 ML-Modelle

### Audio-Analyse
- **Whisper**: Spracherkennung
- **Emotion2Vec**: Emotionsanalyse
- **PANNs**: Akustische Szenenanalyse

### Bild-Analyse
- **RetinaFace**: Gesichtserkennung
- **ArcFace**: Gesichtsverifikation
- **HRNet**: Pose-Estimation
- **AlphaPose**: Körperhaltungsanalyse

### Video-Analyse
- **LLaVA**: Vision-Language-Verständnis
- **CLIP**: Multimodale Embeddings
- **InstructBLIP**: Instruktionsbasierte Analyse

### Multimodale Fusion
- **Llama 3.1**: Intelligente Datenfusion

## 📁 Projektstruktur

```
AIMA/
├── services/                          # Microservices
│   ├── user-management/               # Benutzerverwaltung
│   └── configuration-management/      # Konfigurationsverwaltung
├── database/                          # Datenbankinitialisierung
│   └── init/
├── monitoring/                        # Überwachung & Metriken
│   ├── grafana/
│   └── prometheus.yml
├── Dokumentation/                     # Umfassende Dokumentation
│   ├── Medienanalyse/
│   │   ├── AUDIOANALYSE.md
│   │   ├── BILDANALYSE.md
│   │   ├── VIDEOANALYSE.md
│   │   └── ML_MODELLE_BRAINSTORMING.md
│   ├── GPU-Administration/
│   │   └── GPU_INSTANZ_ADMINISTRATION.md
│   ├── System/
│   │   ├── SYSTEMFAEHIGKEITEN.md
│   │   ├── MODULARISIERUNG_ENTWURF.md
│   │   └── ...
│   └── UEBERSICHT.md
├── docker-compose.yml                 # Zentrale Service-Orchestrierung
├── build.ps1                         # Windows Build-Script
├── build.sh                          # Linux/macOS Build-Script
├── Makefile                          # Build-Automatisierung
├── BUILD_FIX_DOCUMENTATION.md        # Build-Infrastruktur Dokumentation
└── README.md
```

## 🛠️ Technologie-Stack

- **Backend**: Python 3.9+, FastAPI 0.104+
- **ML/AI**: PyTorch, Transformers, OpenCV
- **Datenbanken**: PostgreSQL, MongoDB, Vektordatenbanken
- **API Gateway**: Traefik (Load Balancing, SSL Termination)
- **Container**: Docker, Docker Compose
- **Build Tools**: PowerShell, Bash, Makefile
- **Monitoring**: Prometheus, Grafana
- **Cloud**: GPU-Instanzen (AWS, GCP, Azure)
- **Sicherheit**: End-to-End-Verschlüsselung

## 📋 Systemanforderungen

### Minimale Anforderungen
- **RAM**: 16 GB
- **Storage**: 100 GB SSD
- **GPU**: NVIDIA RTX 3080 oder besser
- **VRAM**: 12 GB+

### Empfohlene Anforderungen
- **RAM**: 32 GB+
- **Storage**: 500 GB NVMe SSD
- **GPU**: NVIDIA RTX 4090 oder Cloud-GPU
- **VRAM**: 24 GB+

## 🚦 Entwicklungsstatus

- ✅ **Konzeption**: Vollständig dokumentiert
- ✅ **Architektur**: Microservices-Architektur implementiert
- 🔄 **Implementation**: User Management & Configuration Management Services
- 🔄 **Build-Infrastruktur**: Docker-Compose, Traefik API Gateway
- ⏳ **ML-Pipeline**: Geplant
- ⏳ **GPU-Integration**: Geplant
- ⏳ **Testing**: Geplant

## 🚀 Schnellstart

### Voraussetzungen
- Docker & Docker Compose
- PowerShell (Windows) oder Bash (Linux/macOS)
- Make (optional)

### Installation & Start

```bash
# Repository klonen
git clone https://github.com/Paddel87/AIMA.git
cd AIMA

# Mit Build-Script (empfohlen)
./build.ps1    # Windows
./build.sh     # Linux/macOS

# Oder mit Makefile
make build
make up

# Oder direkt mit Docker Compose
docker-compose up --build
```

### Services
- **API Gateway**: http://localhost (Traefik Dashboard: http://localhost:8080)
- **User Management**: http://localhost/user-api/docs
- **Configuration Management**: http://localhost/config-api/docs
- **Monitoring**: http://localhost:3000 (Grafana)

## 🏢 Implementierte Services

### 👤 User Management Service
- **Port**: 8001 (intern), über API Gateway erreichbar
- **Features**: 
  - Benutzerregistrierung und -authentifizierung
  - JWT-Token-basierte Sicherheit
  - Rollenverwaltung
  - PostgreSQL-Integration mit Alembic-Migrationen
- **API**: FastAPI mit automatischer OpenAPI-Dokumentation
- **Health Check**: `/health` Endpoint

### ⚙️ Configuration Management Service
- **Port**: 8002 (intern), über API Gateway erreichbar
- **Features**:
  - Zentrale Konfigurationsverwaltung
  - Umgebungsspezifische Einstellungen
  - Service-Discovery-Integration
  - Dynamische Konfigurationsupdates
- **API**: FastAPI mit automatischer OpenAPI-Dokumentation
- **Health Check**: `/health` Endpoint

### 🌐 Traefik API Gateway
- **Port**: 80 (HTTP), 443 (HTTPS), 8080 (Dashboard)
- **Features**:
  - Automatisches Service Discovery
  - Load Balancing
  - SSL/TLS Termination
  - Request Routing basierend auf Pfaden
  - Health Check Integration

## 🔧 Build-Infrastruktur

### Bottom-to-Top Build-Strategie
Das AIMA-Projekt implementiert eine robuste "Bottom-to-Top" Build-Strategie:

1. **Datenbank-Services** (PostgreSQL, MongoDB)
2. **Core-Services** (User Management, Configuration Management)
3. **API Gateway** (Traefik)
4. **Monitoring** (Prometheus, Grafana)

### Build-Tools
- **`build.ps1`**: Windows PowerShell Build-Script mit Health Checks
- **`build.sh`**: Linux/macOS Bash Build-Script mit Health Checks
- **`Makefile`**: Plattformübergreifende Build-Automatisierung
- **`docker-compose.yml`**: Zentrale Service-Orchestrierung

### Verfügbare Build-Kommandos
```bash
# Vollständiger Build mit Health Checks
make build-and-start

# Services starten
make up

# Services stoppen
make down

# Logs anzeigen
make logs

# System bereinigen
make clean
```

### Health Check System
Jeder Service implementiert Health Check Endpoints:
- Automatische Verfügbarkeitsüberprüfung
- Dependency-basierte Startreihenfolge
- Robuste Fehlerbehandlung
- Detaillierte Logging-Ausgaben

## 📚 Dokumentation

Detaillierte Dokumentation finden Sie in den folgenden Bereichen:

- **[Build-Infrastruktur](BUILD_FIX_DOCUMENTATION.md)**: Build-System & Deployment
- **[Übersicht](Dokumentation/UEBERSICHT.md)**: Vollständige Systemübersicht
- **[Medienanalyse](Dokumentation/Medienanalyse/)**: Audio-, Bild- und Videoanalyse
- **[GPU-Administration](Dokumentation/GPU-Administration/)**: Cloud-GPU-Management
- **[Systemarchitektur](Dokumentation/System/)**: Technische Spezifikationen

## 🔒 Sicherheit

- End-to-End-Verschlüsselung aller Mediendateien
- Sichere GPU-Cloud-Kommunikation
- Automatische Datenlöschung nach Verarbeitung
- GDPR-konforme Datenverarbeitung

## 🤝 Beitragen

Dieses Projekt folgt einem KI-gesteuerten Entwicklungsansatz. Beiträge sind willkommen in Form von:

- Konzeptuelle Verbesserungen
- Dokumentationserweiterungen
- Architektur-Feedback
- Use-Case-Szenarien

## 📄 Lizenz

[Lizenz wird noch definiert]

## 📞 Kontakt

Für Fragen und Anregungen zum AIMA-Projekt:

- **GitHub**: [Paddel87/AIMA](https://github.com/Paddel87/AIMA)
- **Issues**: [GitHub Issues](https://github.com/Paddel87/AIMA/issues)

---

**AIMA** - *Intelligente Medienanalyse für die Zukunft* 🚀