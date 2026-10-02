# DisWhisper for macOS

The native Swift/AppKit companion uses the same pages, violet palette, cards, model catalog, and local API as the Windows app. It includes Home, Models, Transcripts, Connect Discord, Meeting notes, Cloud providers, and Settings. The DisWhisper speech-bubble icon appears in the macOS menu bar while the app runs and adapts to light or dark backgrounds. Click it to reopen the workspace, finish a meeting, open meeting notes, or quit. Closing the window keeps this icon and the bot running; **Quit DisWhisper** finishes the meeting and shuts down the backend it started.

## Install the app

1. Open the [latest release](https://github.com/MaxJafar/DisWhisper/releases/latest). Download **DisWhisper-0.2.1-macos-arm64.dmg** for an Apple Silicon Mac (M1 or newer), or **DisWhisper-0.2.1-macos-x86_64.dmg** for an Intel Mac.
2. Open the disk image, drag **DisWhisper.app** onto the **Applications** shortcut, eject the disk image, and open DisWhisper from Applications. Python and the speech/voice libraries are inside the app bundle; no Homebrew or separately installed Python is needed. Alternatively, extract the matching portable ZIP and move its app to Applications.
3. Open **Connect Discord**, paste your own bot token, and **Check connection**. Use **Invite bot**, check again, choose the server and language, then save.
4. In **Models**, download **Whisper base** and select **Use model**.
5. Connect the bot from **Home**, join a Discord voice channel, and use **`/join`**. Finish with **`/leave`** or **Finish meeting** in the app.

These builds use an ad-hoc signature, without an Apple Developer ID or notarization. If macOS blocks the downloaded application, use **Open Anyway** in **System Settings → Privacy & Security** after verifying the source and download checksum. See [Apple's first-launch instructions](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unidentified-developer-mh40616/mac). Notarized distribution requires the maintainer's Apple signing credentials.

**Requirements:** macOS 13 Ventura or newer; the download must match your Mac's architecture. Internet access is needed for Discord and initial model downloads. The native app and all bundled Mach-O deployment targets are checked for Ventura compatibility. The release workflow builds and tests arm64 and x86_64 on separate Mac runners; the local arm64 build was also exercised on macOS 26.6.2.

Whisper, SenseVoice, and Vosk run on the CPU. Ollama meeting notes are optional and use your separate Ollama installation. Groq/OpenAI are optional cloud providers. Apple-specific speech acceleration is future provider work; the companion reports the actual CPU/cloud device from the backend.

## Run from source

Install **Xcode 15+**, its command-line tools, and [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
git clone https://github.com/MaxJafar/DisWhisper.git
cd DisWhisper
./scripts/setup_macos.sh
./scripts/run_macos.sh
```

Setup installs Python 3.12 and the tested dependencies from `requirements-macos.lock`. If uv is unavailable, setup can use an existing `python3.12`; a full portable release uses uv's standalone runtime to avoid linking to a machine-specific Homebrew Python. `DISWHISPER_BUILD_PYTHON` can select a different build interpreter, which must pass the bundle portability audit.

Open `companion/macos/DisWhisperCompanion/DisWhisperCompanion.xcodeproj` for native development. The project is committed; XcodeGen is only needed when changing `project.yml`. Swift Package Manager provides a second build path and the IPC client tests:

```bash
swift test --package-path companion/macos/DisWhisperCompanion
```

## Build a portable app

```bash
./scripts/build_macos.sh
```

The script tests Python and Swift, builds AppKit, freezes the backend with PyInstaller, preserves dependency notices and corresponding native-library sources, checks library paths/deployment targets, exercises the packaged API, signs locally, and creates a disk image, portable ZIP, and SHA-256 checksums in `dist/`. Model weights, tokens, configuration, caches, and transcripts are excluded.

Use `--skip-install` to reuse a prepared release environment. Use `--app-only` for a UI build that connects to a source backend; that option does not produce a portable ZIP or disk image. Run the build separately on arm64 and x86_64 for both architectures. The standalone Mac workflow produces artifacts; the shared desktop release workflow publishes all platforms after their build and installation checks pass.

## Data and credentials

App data lives outside the bundle, so it survives app updates:

```text
~/Library/Application Support/DisWhisper/Data/
├── config.json
├── backend.log
├── models/
├── cache/
└── transcripts/
```

Tokens and API keys saved by the Mac backend go into your **login Keychain**. Configuration contains only opaque `keychain:v1:` references, and the API returns only presence flags. A profile copied from a different Mac or Windows account may need its credentials entered again. Legacy CLI `.env` values remain plain text until you replace them through the companion.

**Settings → Open app data** opens this folder. **Transcripts** can search, preview, copy, open a Markdown file, or pass it to Meeting notes. The local service uses `127.0.0.1:8765` and reconnects the WebSocket automatically. The app can also attach to an existing service; it only shuts down the child identified by its own launch session and process ID.

## Preview and documentation screenshot

```bash
# Real backend, separate profile and port 8767:
./scripts/run_macos.sh --preview

# Sample conversation; no Python, Discord, credentials, or API calls:
open -n dist/DisWhisper-0.2.1-macos-arm64/DisWhisper.app --args --demo
```

`--demo` shows a clearly labelled, in-memory example of the real AppKit UI. Saving configuration, connecting bots, downloading models, and checking real keys are disabled in that workspace. The README screenshot is an actual capture of this mode. `--page models` (or `home`, `transcripts`, `discord`, `summaries`, `cloud`, `settings`) opens a specific page for UI inspection.
