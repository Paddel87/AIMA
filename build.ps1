# AIMA System Build Script
# Löst das Problem der fehlenden Dependency-Installation beim Build

Write-Host "🏗️ AIMA System Build - Bottom-to-Top Approach" -ForegroundColor Green
Write-Host "Dieses Skript löst das Problem der fehlgeschlagenen Builds durch korrekte Dependency-Installation" -ForegroundColor Yellow

# Funktion für Fehlerbehandlung
function Test-LastExitCode {
    param([string]$ErrorMessage)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Fehler: $ErrorMessage" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# Schritt 1: Cleanup vorheriger Builds
Write-Host "\n🧹 Cleanup vorheriger Builds..." -ForegroundColor Cyan
docker-compose down --remove-orphans --volumes 2>$null
docker system prune -f 2>$null

# Schritt 2: Infrastruktur-Layer (Bottom)
Write-Host "\n🏗️ Phase 1: Infrastruktur-Layer starten..." -ForegroundColor Cyan
Write-Host "Starte: PostgreSQL, Redis, RabbitMQ, MinIO, Monitoring" -ForegroundColor Gray

docker-compose up -d postgres redis rabbitmq minio prometheus grafana traefik
Test-LastExitCode "Infrastruktur-Services konnten nicht gestartet werden"

# Warten auf Infrastruktur
Write-Host "⏳ Warte auf Infrastruktur-Services (30s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Health-Check für kritische Services
Write-Host "\n🔍 Health-Check für Infrastruktur..." -ForegroundColor Cyan

# PostgreSQL Check
$postgresReady = $false
for ($i = 1; $i -le 10; $i++) {
    try {
        $result = docker exec aima-postgres pg_isready -U aima_user -d aima 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ PostgreSQL ist bereit" -ForegroundColor Green
            $postgresReady = $true
            break
        }
    } catch {}
    Write-Host "⏳ PostgreSQL noch nicht bereit (Versuch $i/10)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

if (-not $postgresReady) {
    Write-Host "❌ PostgreSQL konnte nicht gestartet werden" -ForegroundColor Red
    exit 1
}

# Redis Check
$redisReady = $false
for ($i = 1; $i -le 5; $i++) {
    try {
        $result = docker exec aima-redis redis-cli -a aima_password ping 2>$null
        if ($result -eq "PONG") {
            Write-Host "✅ Redis ist bereit" -ForegroundColor Green
            $redisReady = $true
            break
        }
    } catch {}
    Write-Host "⏳ Redis noch nicht bereit (Versuch $i/5)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
}

if (-not $redisReady) {
    Write-Host "❌ Redis konnte nicht gestartet werden" -ForegroundColor Red
    exit 1
}

# Schritt 3: Foundation Services (Middle-Layer)
Write-Host "\n🏢 Phase 2: Foundation Services bauen und starten..." -ForegroundColor Cyan
Write-Host "Baue: User Management Service" -ForegroundColor Gray

# User Management Service mit expliziter Dependency-Installation
docker-compose build user-management
Test-LastExitCode "User Management Service Build fehlgeschlagen"

docker-compose up -d user-management
Test-LastExitCode "User Management Service konnte nicht gestartet werden"

# Warten auf User Management
Write-Host "⏳ Warte auf User Management Service (20s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# User Management Health-Check
$userMgmtReady = $false
for ($i = 1; $i -le 10; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8001/api/v1/health/" -TimeoutSec 5 -UseBasicParsing 2>$null
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ User Management Service ist bereit" -ForegroundColor Green
            $userMgmtReady = $true
            break
        }
    } catch {}
    Write-Host "⏳ User Management noch nicht bereit (Versuch $i/10)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

if (-not $userMgmtReady) {
    Write-Host "❌ User Management Service konnte nicht gestartet werden" -ForegroundColor Red
    Write-Host "📋 Logs anzeigen:" -ForegroundColor Yellow
    docker-compose logs user-management
    exit 1
}

# Configuration Management Service
Write-Host "\n🔧 Baue Configuration Management Service..." -ForegroundColor Gray

docker-compose build configuration-management
Test-LastExitCode "Configuration Management Service Build fehlgeschlagen"

docker-compose up -d configuration-management
Test-LastExitCode "Configuration Management Service konnte nicht gestartet werden"

# Warten auf Configuration Management
Write-Host "⏳ Warte auf Configuration Management Service (20s)..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# Configuration Management Health-Check
$configMgmtReady = $false
for ($i = 1; $i -le 10; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8002/health" -TimeoutSec 5 -UseBasicParsing 2>$null
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Configuration Management Service ist bereit" -ForegroundColor Green
            $configMgmtReady = $true
            break
        }
    } catch {}
    Write-Host "⏳ Configuration Management noch nicht bereit (Versuch $i/10)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}

if (-not $configMgmtReady) {
    Write-Host "❌ Configuration Management Service konnte nicht gestartet werden" -ForegroundColor Red
    Write-Host "📋 Logs anzeigen:" -ForegroundColor Yellow
    docker-compose logs configuration-management
    exit 1
}

# Schritt 4: System-Status anzeigen
Write-Host "\n🎉 AIMA System erfolgreich gestartet!" -ForegroundColor Green
Write-Host "\n📊 Service-Status:" -ForegroundColor Cyan
Write-Host "🌐 API Gateway (Traefik): http://localhost:8080" -ForegroundColor White
Write-Host "👥 User Management: http://localhost:8001/api/v1/health/" -ForegroundColor White
Write-Host "⚙️ Configuration Management: http://localhost:8002/health" -ForegroundColor White
Write-Host "📊 Grafana Dashboard: http://localhost:3000 (admin/aima_password)" -ForegroundColor White
Write-Host "🔍 Prometheus: http://localhost:9090" -ForegroundColor White
Write-Host "🐰 RabbitMQ Management: http://localhost:15672 (aima_user/aima_password)" -ForegroundColor White
Write-Host "📦 MinIO Console: http://localhost:9001 (aima_user/aima_password)" -ForegroundColor White

Write-Host "\n✅ Alle Services laufen erfolgreich nach Bottom-to-Top-Prinzip!" -ForegroundColor Green
Write-Host "\n📋 Nützliche Befehle:" -ForegroundColor Cyan
Write-Host "   docker-compose logs <service-name>  # Logs anzeigen" -ForegroundColor Gray
Write-Host "   docker-compose ps                   # Service-Status" -ForegroundColor Gray
Write-Host "   docker-compose down                 # System stoppen" -ForegroundColor Gray