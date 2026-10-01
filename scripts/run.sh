#!/usr/bin/env bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/.."

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

if [ -x .venv/bin/python ]; then
    exec .venv/bin/python -m diswhisper.main "$@"
fi
exec python3 -m diswhisper.main "$@"
