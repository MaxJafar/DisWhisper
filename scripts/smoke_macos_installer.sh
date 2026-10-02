#!/bin/bash
# Simulate dragging the app from a disk image, then test it with the image detached.
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Usage: smoke_macos_installer.sh INSTALLER.dmg" >&2; exit 1; fi
DISWHISPER_INSTALL_TEST="$(mktemp -d "${TMPDIR:-/tmp}/diswhisper-install.XXXXXX")"
DISWHISPER_INSTALL_MOUNTED=false
cleanup() {
    if $DISWHISPER_INSTALL_MOUNTED; then hdiutil detach "$DISWHISPER_INSTALL_TEST/mounted"; fi
    rm -rf "$DISWHISPER_INSTALL_TEST"
}
trap cleanup EXIT
mkdir "$DISWHISPER_INSTALL_TEST/mounted" "$DISWHISPER_INSTALL_TEST/installed"
hdiutil attach "$1" -nobrowse -readonly -mountpoint "$DISWHISPER_INSTALL_TEST/mounted"
DISWHISPER_INSTALL_MOUNTED=true
test "$(readlink "$DISWHISPER_INSTALL_TEST/mounted/Applications")" = /Applications
ditto "$DISWHISPER_INSTALL_TEST/mounted/DisWhisper.app" "$DISWHISPER_INSTALL_TEST/installed/DisWhisper.app"
hdiutil detach "$DISWHISPER_INSTALL_TEST/mounted"
DISWHISPER_INSTALL_MOUNTED=false
codesign --verify --deep --strict "$DISWHISPER_INSTALL_TEST/installed/DisWhisper.app"
.cache/macos-package-venv/bin/python scripts/smoke_release.py \
    "$DISWHISPER_INSTALL_TEST/installed/DisWhisper.app/Contents/Resources/backend/diswhisper-backend"
echo "Mac disk image passed: Applications shortcut, copied app signature, independent backend startup and shutdown."
