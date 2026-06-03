# Vyper - Build All Docker Images
# ================================
# Script ini build SEMUA Docker images di project Vyper:
#   1. Base image (Dockerfile.base)
#   2. Semua 17 microservice dari docker-compose.yml
#   3. Standalone images (Dockerfile.forge, Dockerfile.tui)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VYPER - BUILD ALL DOCKER IMAGES" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -- Step 0: Check Docker --
Write-Host "[1/4] Checking Docker availability..." -ForegroundColor Yellow
$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker not found. Please install Docker Desktop." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Docker: $dockerVersion" -ForegroundColor Green

$composeVersion = docker-compose --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [..] docker-compose not found, trying docker compose..." -ForegroundColor Yellow
    $composeVersion = docker compose version 2>&1
    $useComposeV2 = $true
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: docker-compose not found." -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] Docker Compose V2: $composeVersion" -ForegroundColor Green
} else {
    $useComposeV2 = $false
    Write-Host "  [OK] Docker Compose: $composeVersion" -ForegroundColor Green
}

$startTime = Get-Date

# -- Step 1: Build Base Image --
Write-Host ""
Write-Host "[2/4] Building base image (vyper-base)..." -ForegroundColor Yellow
Write-Host "  From: Dockerfile.base" -ForegroundColor Gray
docker build -t vyper-base:latest -f Dockerfile.base . 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] Base image build FAILED" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] vyper-base:latest built successfully" -ForegroundColor Green

# -- Step 2: Build All Compose Services --
Write-Host ""
Write-Host "[3/4] Building all microservice images via docker-compose..." -ForegroundColor Yellow
Write-Host "  Services:" -ForegroundColor Gray
Write-Host "    01-config, 02-immunefi, 03-source, 04-scanner" -ForegroundColor Gray
Write-Host "    04a-slither, 04b-echidna, 04c-forge, 04d-halmos, 04e-manticore" -ForegroundColor Gray
Write-Host "    05-mythril, 06-ai, 07-classifier, 08-exploit" -ForegroundColor Gray
Write-Host "    09-reporter, 10-notifier, 11-orchestrator, 12-webhook" -ForegroundColor Gray
Write-Host "    13-upkeep, 14-agent, 15-dashboard, 16-submission, 17-experience" -ForegroundColor Gray

if ($useComposeV2) {
    docker compose build 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
} else {
    docker-compose build 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "  [!] Some services may have failed. Check logs above." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] All compose services built successfully" -ForegroundColor Green
}

# -- Step 3: Build Standalone Images --
Write-Host ""
Write-Host "[4/4] Building standalone images..." -ForegroundColor Yellow

Write-Host "  Building vyper-forge-runner..." -ForegroundColor Gray
docker build -t vyper-forge-runner:latest -f services/08-exploit/Dockerfile.forge . 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] vyper-forge-runner:latest built" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] vyper-forge-runner build FAILED" -ForegroundColor Red
}

Write-Host "  Building vyper-tui..." -ForegroundColor Gray
docker build -t vyper-tui:latest -f cli/Dockerfile.tui . 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] vyper-tui:latest built" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] vyper-tui build FAILED" -ForegroundColor Red
}

# -- Summary --
$endTime = Get-Date
$duration = $endTime - $startTime
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BUILD SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

docker images --filter "reference=vyper-*" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}"
Write-Host ""
Write-Host "Total time: $($duration.Minutes)m $($duration.Seconds)s" -ForegroundColor Cyan
Write-Host "Build complete!" -ForegroundColor Cyan
