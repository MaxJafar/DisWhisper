#!/usr/bin/env bash
set -e

echo "=============================================="
echo "  DisWhisper: Local Real-Time Transcriber     "
echo "=============================================="

if [ ! -f .env ] && [ ! -f config.json ]; then
    echo "[!] Warning: No .env or config.json found."
    echo "Copying .env.example to .env ..."
    cp .env.example .env
    echo "Please edit .env with your DISCORD_TOKEN before starting."
    exit 1
fi

python3 -m diswhisper.main
