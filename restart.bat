@echo off
cd /d "%~dp0"

echo Restarting all Vyper containers...
docker compose restart
if %ERRORLEVEL% equ 0 (
    echo SUCCESS - All containers restarted
    echo Buka: http://localhost:8000/agent
) else (
    echo ERROR - Restart gagal
)
pause
