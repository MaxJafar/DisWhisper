#!/bin/bash
# Package the tested app with a drag-to-Applications shortcut.
set -euo pipefail
if [[ $# -ne 2 ]]; then echo "Usage: create_macos_dmg.sh RELEASE_FOLDER OUTPUT.dmg" >&2; exit 1; fi
DISWHISPER_DMG_RELEASE="$1"
DISWHISPER_DMG_OUTPUT="$2"
codesign --verify --deep --strict "$DISWHISPER_DMG_RELEASE/DisWhisper.app"
DISWHISPER_DMG_STAGE="$(mktemp -d "${TMPDIR:-/tmp}/diswhisper-dmg.XXXXXX")"
trap 'rm -rf "$DISWHISPER_DMG_STAGE"' EXIT
ditto "$DISWHISPER_DMG_RELEASE/DisWhisper.app" "$DISWHISPER_DMG_STAGE/DisWhisper.app"
ln -s /Applications "$DISWHISPER_DMG_STAGE/Applications"
mkdir "$DISWHISPER_DMG_STAGE/Documentation"
cp "$DISWHISPER_DMG_RELEASE/START HERE.md" "$DISWHISPER_DMG_RELEASE/LICENSE" \
    "$DISWHISPER_DMG_RELEASE/THIRD_PARTY_NOTICES.md" "$DISWHISPER_DMG_STAGE/Documentation/"
hdiutil create -volname DisWhisper -srcfolder "$DISWHISPER_DMG_STAGE" -ov -format UDZO "$DISWHISPER_DMG_OUTPUT"
hdiutil verify "$DISWHISPER_DMG_OUTPUT"
(cd "$(dirname "$DISWHISPER_DMG_OUTPUT")" && shasum -a 256 "$(basename "$DISWHISPER_DMG_OUTPUT")") > "$DISWHISPER_DMG_OUTPUT.sha256"
