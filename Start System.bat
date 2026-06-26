@echo off
REM ============================================================
REM  Freight AI Ops - Windows startup script
REM  Starts the full local stack via Docker Compose.
REM ============================================================

cd /d "%~dp0"

if not exist ".env" (
    echo No .env file found. Creating one from .env.example ...
    copy ".env.example" ".env" >nul
    echo.
    echo  IMPORTANT: open .env and set your ANTHROPIC_API_KEY and ADMIN_PASSWORD,
    echo  then run this script again.
    echo.
    pause
    exit /b 0
)

echo Starting Freight AI Ops (this may take a minute on first run)...
docker compose up -d --build

if %errorlevel% neq 0 (
    echo.
    echo Failed to start. Is Docker Desktop running?
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Freight AI Ops is starting up.
echo    Frontend : http://localhost:3000
echo    Backend  : http://localhost:8000/docs
echo ============================================================
echo.
echo Use "docker compose logs -f" to watch logs, or "docker compose down" to stop.
pause
