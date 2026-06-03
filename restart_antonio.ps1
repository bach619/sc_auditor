# Restart Antonio + Dashboard setelah code changes
# Run: .\restart_antonio.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RESTART ANTONIO + DASHBOARD" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop
Write-Host "[1/3] Stopping services..." -ForegroundColor Yellow
docker-compose stop 14-agent 15-dashboard
Write-Host ""

# Build
Write-Host "[2/3] Rebuilding images..." -ForegroundColor Yellow
docker-compose build --no-cache 14-agent 15-dashboard
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Start
Write-Host "[3/3] Starting services..." -ForegroundColor Yellow
docker-compose up -d 14-agent 15-dashboard
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Start failed!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Wait for agent to initialize
Write-Host "Waiting 20s for Antonio to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# Check status
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  STATUS" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
docker-compose ps 14-agent 15-dashboard

# Quick health check
Write-Host ""
Write-Host "Health check 14-agent..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8021/health" -TimeoutSec 5
    Write-Host "  Status: $($health.data.status)" -ForegroundColor Green
    Write-Host "  Version: $($health.data.version)" -ForegroundColor Green
    Write-Host "  Skills loaded: $($health.data.skills_loaded)" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: 14-agent health check failed. Cek log:" -ForegroundColor Red
    Write-Host "  docker-compose logs --tail=30 14-agent" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done! Dashboard: http://localhost:8000" -ForegroundColor Green
Write-Host "Antonio chat:  http://localhost:8021/agent/chat" -ForegroundColor Green
