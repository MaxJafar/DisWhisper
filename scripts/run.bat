@echo off
title DisWhisper - Discord Meeting Transcriber
cd /d "%~dp0.."
echo ==============================================
echo   DisWhisper: Local Real-Time Transcriber
echo ==============================================

if not exist .env (
    if not exist config.json (
        echo [!] Warning: No .env or config.json found.
        echo Copying .env.example to .env ...
        copy .env.example .env
        echo Please edit .env with your DISCORD_TOKEN before starting.
        pause
        exit /b 1
    )
)

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m diswhisper.main %*
) else (
    python -m diswhisper.main %*
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bot stopped with error code %ERRORLEVEL%.
    pause
)
