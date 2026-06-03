@echo off
cd /d "%~dp0"

echo ============================================
echo  Rebuild: services 21-27 (Vyper OP platform)
echo ============================================
echo.

echo [1] Building 21-code4rena...
docker compose build 21-code4rena

echo [2] Building 22-sherlock...
docker compose build 22-sherlock

echo [3] Building 23-cantina...
docker compose build 23-cantina

echo [4] Building 24-hats...
docker compose build 24-hats

echo [5] Building 25-source-starknet...
docker compose build 25-source-starknet

echo [6] Building 27-scanner-cairo...
docker compose build 27-scanner-cairo

echo.
echo [7] Starting all new services...
docker compose up -d 21-code4rena 22-sherlock 23-cantina 24-hats 25-source-starknet 27-scanner-cairo

echo.
echo ============================================
echo  Done — ports:
echo    21-code4rena      :8022
echo    22-sherlock        :8023
echo    23-cantina         :8024
echo    24-hats            :8025
echo    25-source-starknet :8026
echo    27-scanner-cairo   :8028
echo ============================================
pause
