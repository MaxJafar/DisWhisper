@echo off
title DisWhisper Companion App Launcher
cd /d "%~dp0.."
echo ==============================================
echo   DisWhisper WinUI 3 Companion App Launcher   
echo ==============================================

set PROJECT_PATH=companion\windows\DisWhisper.Companion\DisWhisper.Companion.csproj
set EXE_PATH=companion\windows\DisWhisper.Companion\bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\DisWhisper.Companion.exe

if exist "%EXE_PATH%" (
    echo Launching compiled WinUI 3 Companion App...
    start "" "%EXE_PATH%"
) else (
    echo Executable not found. Running with dotnet run...
    dotnet run --project "%PROJECT_PATH%" -c Release -p:Platform=x64 -p:RuntimeIdentifier=win-x64
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo If build failed, run 'powershell -ExecutionPolicy Bypass -File scripts\setup_companion.ps1'
    pause
)
