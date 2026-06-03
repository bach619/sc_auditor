@echo off
cd /d "%~dp0"

echo ============================================
echo  Rebuild: services 18-23 (Vyper OP platform)
echo ============================================
echo.
echo  18-code4rena       :8022
echo  19-sherlock         :8023
echo  20-cantina          :8024
echo  21-hats             :8025
echo  22-source-starknet  :8026
echo  23-scanner-cairo    :8028
echo.

docker compose up -d --build 18-code4rena 19-sherlock 20-cantina 21-hats 22-source-starknet 23-scanner-cairo

echo.
echo ============================================
echo  Done
echo ============================================
pause
