@echo off
echo ============================================
echo  Rebuild: 15-dashboard + 11-orchestrator
echo  (Audit Monitor Terminal + SSE Broadcast)
echo ============================================
echo.

cd /d "%~dp0"

echo [1/2] Building 15-dashboard (frontend + backend)...
docker compose build 15-dashboard
if %ERRORLEVEL% neq 0 goto :error

echo.
echo [2/2] Building 11-orchestrator (pipeline broadcast)...
docker compose build 11-orchestrator
if %ERRORLEVEL% neq 0 goto :error

echo.
echo [3/3] Restarting containers...
docker compose up -d 15-dashboard 11-orchestrator
if %ERRORLEVEL% neq 0 goto :error

echo.
echo ============================================
echo  SUCCESS - Containers rebuilt and running
echo  Buka: http://localhost:8000/agent
echo ============================================
pause
exit /b 0

:error
echo.
echo ============================================
echo  ERROR - Build gagal. Cek log di atas.
echo ============================================
pause
exit /b 1
