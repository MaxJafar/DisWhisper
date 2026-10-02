#!/bin/bash
# Build a portable native AppKit app for the machine's architecture. Never package app data.
set -euo pipefail
DISWHISPER_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DISWHISPER_ROOT"
DISWHISPER_APP_ONLY=false
DISWHISPER_SKIP_INSTALL=false
for option in "$@"; do
    case "$option" in
        --app-only) DISWHISPER_APP_ONLY=true ;;
        --skip-install) DISWHISPER_SKIP_INSTALL=true ;;
        *) echo "Usage: scripts/build_macos.sh [--app-only] [--skip-install]" >&2; exit 1 ;;
    esac
done
if [[ "$(uname -s)" != "Darwin" ]]; then echo "Build on macOS with Xcode 15 or newer." >&2; exit 1; fi
DISWHISPER_ARCH="$(uname -m)"
DISWHISPER_VERSION="$(sed -nE 's/^version = "([0-9]+\.[0-9]+\.[0-9]+)"$/\1/p' pyproject.toml)"
if [[ ! "$DISWHISPER_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo "Invalid project release version." >&2; exit 1; fi
DISWHISPER_RELEASE="dist/DisWhisper-$DISWHISPER_VERSION-macos-$DISWHISPER_ARCH"
DISWHISPER_APP="$DISWHISPER_RELEASE/DisWhisper.app"
DISWHISPER_ENV=".cache/macos-package-venv"
DISWHISPER_PYTHON="$DISWHISPER_ENV/bin/python"

if ! $DISWHISPER_APP_ONLY; then
    if [[ ! -x "$DISWHISPER_PYTHON" ]]; then
        if ! command -v uv >/dev/null 2>&1; then echo "Install uv to obtain a portable Python 3.12 runtime (see docs/macos-quickstart.md)." >&2; exit 1; fi
        if [[ -n "${DISWHISPER_BUILD_PYTHON:-}" ]]; then
            uv venv --python "$DISWHISPER_BUILD_PYTHON" "$DISWHISPER_ENV"
        else
            uv python install 3.12
            uv venv --managed-python --python 3.12 "$DISWHISPER_ENV"
        fi
    fi
    if ! $DISWHISPER_SKIP_INSTALL; then
        if command -v uv >/dev/null 2>&1; then
            uv pip install --python "$DISWHISPER_PYTHON" -r requirements-macos.lock
            uv pip install --python "$DISWHISPER_PYTHON" --no-deps .
        else
            "$DISWHISPER_PYTHON" -m pip install -r requirements-macos.lock
            "$DISWHISPER_PYTHON" -m pip install --no-deps .
        fi
    fi
    "$DISWHISPER_PYTHON" -m pytest tests/ -v
    "$DISWHISPER_PYTHON" -m ruff check diswhisper tests scripts
fi
swift test --package-path companion/macos/DisWhisperCompanion
xcodebuild -quiet -project companion/macos/DisWhisperCompanion/DisWhisperCompanion.xcodeproj \
    -scheme DisWhisperCompanion -configuration Release -derivedDataPath .cache/macos-derived \
    CODE_SIGNING_ALLOWED=NO ARCHS="$DISWHISPER_ARCH" ONLY_ACTIVE_ARCH=YES build
mkdir -p "$DISWHISPER_RELEASE"
# Remove only the generated application bundle, never configuration or meeting files.
if [[ -d "$DISWHISPER_APP" ]]; then rm -rf "$DISWHISPER_APP"; fi
ditto .cache/macos-derived/Build/Products/Release/DisWhisper.app "$DISWHISPER_APP"
cp LICENSE THIRD_PARTY_NOTICES.md "$DISWHISPER_RELEASE/"
cp docs/macos-quickstart.md "$DISWHISPER_RELEASE/START HERE.md"

if ! $DISWHISPER_APP_ONLY; then
    "$DISWHISPER_PYTHON" -m PyInstaller --noconfirm --clean \
        --distpath .cache/macos-frozen --workpath .cache/macos-pyinstaller packaging/backend-macos.spec
    ditto .cache/macos-frozen/diswhisper-backend "$DISWHISPER_APP/Contents/Resources/backend"
    "$DISWHISPER_PYTHON" scripts/collect_licenses.py "$DISWHISPER_APP/Contents/Resources/licenses/python"
    DISWHISPER_PYTHON_LICENSE="$($DISWHISPER_PYTHON -c 'import sys; from pathlib import Path; print(Path(sys.base_prefix) / "lib/python3.12/LICENSE.txt")')"
    cp "$DISWHISPER_PYTHON_LICENSE" "$DISWHISPER_APP/Contents/Resources/licenses/python/PYTHON_LICENSE.txt"
    "$DISWHISPER_PYTHON" scripts/collect_native_sources.py \
        "$DISWHISPER_APP/Contents/Resources/licenses/native" \
        "dist/DisWhisper-$DISWHISPER_VERSION-macos-$DISWHISPER_ARCH-third-party-source.zip" --manifest packaging/vendor-sources-macos.json
    "$DISWHISPER_PYTHON" scripts/audit_macos_bundle.py "$DISWHISPER_APP"
    "$DISWHISPER_PYTHON" scripts/smoke_release.py "$DISWHISPER_APP/Contents/Resources/backend/diswhisper-backend"
fi
codesign --force --deep --sign - "$DISWHISPER_APP"
codesign --verify --deep --strict "$DISWHISPER_APP"
if $DISWHISPER_APP_ONLY; then
    echo "AppKit-only build ready: $DISWHISPER_APP (requires the source backend)."
else
    ditto -c -k --sequesterRsrc --keepParent "$DISWHISPER_RELEASE" "$DISWHISPER_RELEASE.zip"
    (cd dist && shasum -a 256 "DisWhisper-$DISWHISPER_VERSION-macos-$DISWHISPER_ARCH.zip") > "$DISWHISPER_RELEASE.zip.sha256"
    ./scripts/create_macos_dmg.sh "$DISWHISPER_RELEASE" "$DISWHISPER_RELEASE.dmg"
    echo "Portable macOS build ready: $DISWHISPER_RELEASE.zip"
fi
