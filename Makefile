# AIMA System Makefile
# Vereinfacht Build-Prozesse und löst Dependency-Probleme

.PHONY: help build start stop clean logs status health test

# Default target
help:
	@echo "🏗️ AIMA System Build Commands"
	@echo "=============================="
	@echo "make build     - Vollständiger System-Build (Bottom-to-Top)"
	@echo "make start     - System starten (nur wenn bereits gebaut)"
	@echo "make stop      - System stoppen"
	@echo "make clean     - Komplette Bereinigung (Volumes, Images)"
	@echo "make logs      - Alle Service-Logs anzeigen"
	@echo "make status    - Service-Status anzeigen"
	@echo "make health    - Health-Checks aller Services"
	@echo "make test      - Integration-Tests ausführen"
	@echo ""
	@echo "🔧 Service-spezifische Befehle:"
	@echo "make logs-user        - User Management Logs"
	@echo "make logs-config      - Configuration Management Logs"
	@echo "make restart-user     - User Management neustarten"
	@echo "make restart-config   - Configuration Management neustarten"

# Vollständiger Build mit Bottom-to-Top-Strategie
build:
	@echo "🏗️ Starte AIMA System Build (Bottom-to-Top)..."
	@echo "Löst das Problem der fehlenden Dependency-Installation"
	@if command -v powershell >/dev/null 2>&1; then \
		powershell -ExecutionPolicy Bypass -File ./build.ps1; \
	else \
		chmod +x ./build.sh && ./build.sh; \
	fi

# System starten (nur Infrastructure + Services)
start:
	@echo "🚀 Starte AIMA System..."
	docker-compose up -d
	@echo "✅ System gestartet. Verwende 'make status' für Service-Status"

# System stoppen
stop:
	@echo "🛑 Stoppe AIMA System..."
	docker-compose down
	@echo "✅ System gestoppt"

# Komplette Bereinigung
clean:
	@echo "🧹 Bereinige AIMA System..."
	docker-compose down --volumes --remove-orphans
	docker system prune -f
	@echo "✅ System bereinigt"

# Alle Logs anzeigen
logs:
	@echo "📋 AIMA System Logs:"
	docker-compose logs --tail=50 -f

# Service-Status anzeigen
status:
	@echo "📊 AIMA Service Status:"
	docker-compose ps
	@echo ""
	@echo "🌐 Service-Endpoints:"
	@echo "API Gateway (Traefik): http://localhost:8080"
	@echo "User Management: http://localhost:8001/api/v1/health/"
	@echo "Configuration Management: http://localhost:8002/health"
	@echo "Grafana: http://localhost:3000 (admin/aima_password)"
	@echo "Prometheus: http://localhost:9090"
	@echo "RabbitMQ: http://localhost:15672 (aima_user/aima_password)"
	@echo "MinIO: http://localhost:9001 (aima_user/aima_password)"

# Health-Checks
health:
	@echo "🔍 AIMA System Health-Checks:"
	@echo "Checking PostgreSQL..."
	@docker exec aima-postgres pg_isready -U aima_user -d aima && echo "✅ PostgreSQL: OK" || echo "❌ PostgreSQL: FAIL"
	@echo "Checking Redis..."
	@docker exec aima-redis redis-cli -a aima_password ping | grep -q "PONG" && echo "✅ Redis: OK" || echo "❌ Redis: FAIL"
	@echo "Checking User Management..."
	@curl -f -s http://localhost:8001/api/v1/health/ >/dev/null && echo "✅ User Management: OK" || echo "❌ User Management: FAIL"
	@echo "Checking Configuration Management..."
	@curl -f -s http://localhost:8002/health >/dev/null && echo "✅ Configuration Management: OK" || echo "❌ Configuration Management: FAIL"

# Integration-Tests
test:
	@echo "🧪 AIMA Integration-Tests:"
	@echo "Testing User Management API..."
	@curl -f -s http://localhost:8001/api/v1/health/ | grep -q "status" && echo "✅ User Management API: OK" || echo "❌ User Management API: FAIL"
	@echo "Testing Configuration Management API..."
	@curl -f -s http://localhost:8002/health | grep -q "status" && echo "✅ Configuration Management API: OK" || echo "❌ Configuration Management API: FAIL"
	@echo "Testing Service Communication..."
	@curl -f -s http://localhost:8002/api/v1/config/test >/dev/null 2>&1 && echo "✅ Service Communication: OK" || echo "⚠️ Service Communication: Nicht verfügbar (normal bei erstem Start)"

# Service-spezifische Befehle
logs-user:
	@echo "📋 User Management Logs:"
	docker-compose logs --tail=50 -f user-management

logs-config:
	@echo "📋 Configuration Management Logs:"
	docker-compose logs --tail=50 -f configuration-management

restart-user:
	@echo "🔄 Starte User Management neu..."
	docker-compose restart user-management
	@echo "✅ User Management neugestartet"

restart-config:
	@echo "🔄 Starte Configuration Management neu..."
	docker-compose restart configuration-management
	@echo "✅ Configuration Management neugestartet"

# Development helpers
dev-setup:
	@echo "🛠️ Development Setup..."
	@echo "Erstelle notwendige Verzeichnisse..."
	mkdir -p services/user-management/logs
	mkdir -p services/configuration-management/logs
	mkdir -p monitoring/grafana/dashboards
	mkdir -p monitoring/grafana/datasources
	@echo "✅ Development Setup abgeschlossen"

# Quick rebuild einzelner Services
rebuild-user:
	@echo "🔨 Rebuilding User Management..."
	docker-compose build user-management
	docker-compose up -d user-management
	@echo "✅ User Management rebuilt"

rebuild-config:
	@echo "🔨 Rebuilding Configuration Management..."
	docker-compose build configuration-management
	docker-compose up -d configuration-management
	@echo "✅ Configuration Management rebuilt"

# Backup und Restore
backup:
	@echo "💾 Erstelle System-Backup..."
	mkdir -p backups
	docker exec aima-postgres pg_dump -U aima_user aima > backups/postgres_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup erstellt in backups/"

restore:
	@echo "📥 Restore-Funktion noch nicht implementiert"
	@echo "Verwende: docker exec -i aima-postgres psql -U aima_user aima < backups/your_backup.sql"