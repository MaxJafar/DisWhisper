#!/bin/bash
set -euo pipefail
DISWHISPER_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DISWHISPER_ROOT"
DISWHISPER_PROJECT="companion/macos/DisWhisperCompanion/DisWhisperCompanion.xcodeproj"
xcodebuild -quiet -project "$DISWHISPER_PROJECT" -scheme DisWhisperCompanion \
    -configuration Debug -derivedDataPath .cache/macos-dev \
    CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES ONLY_ACTIVE_ARCH=YES build
open -n .cache/macos-dev/Build/Products/Debug/DisWhisper.app --args "$@"
