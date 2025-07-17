#!/bin/bash
# AIMA System Build Script (Linux/macOS)
# Löst das Problem der fehlenden Dependency-Installation beim Build

set -e  # Exit on any error

echo "🏗️ AIMA System Build - Bottom-to-Top Approach"
echo "Dieses Skript löst das Problem der fehlgeschlagenen Builds durch korrekte Dependency-Installation"

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

# Funktion für farbigen Output
log_info() { echo -e "${CYAN}$1${NC}"; }
log_success() { echo -e "${GREEN}$1${NC}"; }
log_warning() { echo -e "${YELLOW}$1${NC}"; }
log_error() { echo -e "${RED}$1${NC}"; }
log_gray() { echo -e "${GRAY}$1${NC}"; }

# Schritt 1: Cleanup vorheriger Builds
log_info "\n🧹 Cleanup vorheriger Builds..."
docker-compose down --remove-orphans --volumes 2>/dev/null || true
docker system prune -f 2>/dev/null || true

# Schritt 2: Infrastruktur-Layer (Bottom)
log_info "\n🏗️ Phase 1: Infrastruktur-Layer starten..."
log_gray "Starte: PostgreSQL, Redis, RabbitMQ, MinIO, Monitoring"

docker-compose up -d postgres redis rabbitmq minio prometheus grafana traefik

# Warten auf Infrastruktur
log_warning "⏳ Warte auf Infrastruktur-Services (30s)..."
sleep 30

# Health-Check für kritische Services
log_info "\n🔍 Health-Check für Infrastruktur..."

# PostgreSQL Check
postgres_ready=false
for i in {1..10}; do
    if docker exec aima-postgres pg_isready -U aima_user -d aima >/dev/null 2>&1; then
        log_success "✅ PostgreSQL ist bereit"
        postgres_ready=true
        break
    fi
    log_warning "⏳ PostgreSQL noch nicht bereit (Versuch $i/10)..."
    sleep 5
done

if [ "$postgres_ready" = false ]; then
    log_error "❌ PostgreSQL konnte nicht gestartet werden"
    exit 1
fi

# Redis Check
redis_ready=false
for i in {1..5}; do
    if docker exec aima-redis redis-cli -a aima_password ping 2>/dev/null | grep -q "PONG"; then
        log_success "✅ Redis ist bereit"
        redis_ready=true
        break
    fi
    log_warning "⏳ Redis noch nicht bereit (Versuch $i/5)..."
    sleep 3
done

if [ "$redis_ready" = false ]; then
    log_error "❌ Redis konnte nicht gestartet werden"
    exit 1
fi

# Schritt 3: Foundation Services (Middle-Layer)
log_info "\n🏢 Phase 2: Foundation Services bauen und starten..."
log_gray "Baue: User Management Service"

# User Management Service mit expliziter Dependency-Installation
docker-compose build user-management
docker-compose up -d user-management

# Warten auf User Management
log_warning "⏳ Warte auf User Management Service (20s)..."
sleep 20

# User Management Health-Check
user_mgmt_ready=false
for i in {1..10}; do
    if curl -f -s "http://localhost:8001/api/v1/health/" >/dev/null 2>&1; then
        log_success "✅ User Management Service ist bereit"
        user_mgmt_ready=true
        break
    fi
    log_warning "⏳ User Management noch nicht bereit (Versuch $i/10)..."
    sleep 5
done

if [ "$user_mgmt_ready" = false ]; then
    log_error "❌ User Management Service konnte nicht gestartet werden"
    log_warning "📋 Logs anzeigen:"
    docker-compose logs user-management
    exit 1
fi

# Configuration Management Service
log_gray "\n🔧 Baue Configuration Management Service..."

docker-compose build configuration-management
docker-compose up -d configuration-management

# Warten auf Configuration Management
log_warning "⏳ Warte auf Configuration Management Service (20s)..."
sleep 20

# Configuration Management Health-Check
config_mgmt_ready=false
for i in {1..10}; do
    if curl -f -s "http://localhost:8002/health" >/dev/null 2>&1; then
        log_success "✅ Configuration Management Service ist bereit"
        config_mgmt_ready=true
        break
    fi
    log_warning "⏳ Configuration Management noch nicht bereit (Versuch $i/10)..."
    sleep 5
done

if [ "$config_mgmt_ready" = false ]; then
    log_error "❌ Configuration Management Service konnte nicht gestartet werden"
    log_warning "📋 Logs anzeigen:"
    docker-compose logs configuration-management
    exit 1
fi

# Schritt 4: System-Status anzeigen
log_success "\n🎉 AIMA System erfolgreich gestartet!"
log_info "\n📊 Service-Status:"
echo "🌐 API Gateway (Traefik): http://localhost:8080"
echo "👥 User Management: http://localhost:8001/api/v1/health/"
echo "⚙️ Configuration Management: http://localhost:8002/health"
echo "📊 Grafana Dashboard: http://localhost:3000 (admin/aima_password)"
echo "🔍 Prometheus: http://localhost:9090"
echo "🐰 RabbitMQ Management: http://localhost:15672 (aima_user/aima_password)"
echo "📦 MinIO Console: http://localhost:9001 (aima_user/aima_password)"

log_success "\n✅ Alle Services laufen erfolgreich nach Bottom-to-Top-Prinzip!"
log_info "\n📋 Nützliche Befehle:"
log_gray "   docker-compose logs <service-name>  # Logs anzeigen"
log_gray "   docker-compose ps                   # Service-Status"
log_gray "   docker-compose down                 # System stoppen"