#!/bin/bash
set -euo pipefail
DISWHISPER_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DISWHISPER_ROOT"
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "This script prepares the native macOS companion." >&2
    exit 1
fi
if command -v uv >/dev/null 2>&1; then
    uv python install 3.12
    DISWHISPER_PYTHON="$(uv python find --managed-python 3.12)"
    if [[ ! -x .venv/bin/python ]]; then uv venv --python "$DISWHISPER_PYTHON" .venv; fi
    uv pip install --python .venv/bin/python -r requirements-macos.lock
    uv pip install --python .venv/bin/python --no-deps -e .
else
    DISWHISPER_PYTHON="${DISWHISPER_BUILD_PYTHON:-python3.12}"
    if [[ ! -x .venv/bin/python ]]; then "$DISWHISPER_PYTHON" -m venv .venv; fi
    .venv/bin/python -m pip install -r requirements-macos.lock
    .venv/bin/python -m pip install --no-deps -e .
fi
.venv/bin/python -c 'from diswhisper.audio.opus import ensure_opus_loaded; import davey, sherpa_onnx, vosk; ensure_opus_loaded(); print("Native voice and speech dependencies ready.")'
echo "Backend ready. Run scripts/run_macos.sh to open DisWhisper."
