# Contributing

DisWhisper welcomes improvements to recognition, Discord reliability, accessibility, and native desktop usability. Start with a focused issue or pull request and describe the user-visible problem.

## Development

Use Python 3.12. Create a virtual environment and install `pip install -e ".[dev]"`. Install the .NET 8 SDK on Windows, then run `scripts/setup_companion.ps1`. The companion starts its own backend and stores settings in your local app-data folder.

On macOS, use Xcode 15+ and `scripts/setup_macos.sh`, then `scripts/run_macos.sh`. Open the committed `companion/macos/DisWhisperCompanion/DisWhisperCompanion.xcodeproj` for AppKit work. `project.yml` is its XcodeGen source; regenerate the project after adding/removing source or resource files. `swift test --package-path companion/macos/DisWhisperCompanion` verifies the native IPC client.

For an isolated first-run profile, launch the companion with `--preview`. This uses a separate process key, data folder, and port 8767. Do not copy real credentials or transcripts into test fixtures.

Before submitting:

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
.\.venv\Scripts\python -m ruff check diswhisper tests scripts
dotnet build companion/windows/DisWhisper.Companion/DisWhisper.Companion.csproj -c Release -p:Platform=x64
```

Tests isolate developer environment settings and mock network/model calls. Add regression coverage for bugs that can lose transcripts, corrupt settings, expose credentials, or break lifecycle behavior. Keep routine presentation changes lightweight.

## Portable Windows release

On Windows x64 with Python 3.12 and the .NET 8 SDK:

```powershell
.\scripts\build_windows.ps1
```

The script creates an isolated build environment from `requirements-windows.lock`, runs the tests, publishes a self-contained WinUI app, freezes the backend with PyInstaller, collects dependency notices and matching native-library sources, and creates ZIPs plus SHA-256 checksums in `dist/`. Model weights, private configuration, logs, transcripts, and GPU libraries are excluded. Publish both the portable and third-party source archives; see THIRD_PARTY_NOTICES.md for the combined binary license.

The `release.yml` workflow performs the same build for version tags or a manual workflow run. A manual run produces artifacts; version tags publish a GitHub release. The current release is unsigned.

## Portable macOS build

Run `scripts/build_macos.sh` on a Mac with Xcode 15+ and uv. It creates an isolated Python 3.12 environment from `requirements-macos.lock`, runs Python and Swift tests, builds the AppKit `.app`, bundles the frozen backend, audits Ventura compatibility and library paths, exercises its local API, collects notices and matching source archives, and creates a ZIP and checksum in `dist/`. Run on each architecture for arm64 and Intel packages. `--app-only` builds a source-development UI; `--skip-install` reuses a prepared packaging environment.

Local builds use ad-hoc signatures. Publishing a notarized Mac release requires the maintainer's Apple Developer ID and notarization credentials. The manual `macos-build.yml` workflow creates downloadable build artifacts without publishing a release. See [docs/macos-quickstart.md](docs/macos-quickstart.md).

## Project conventions

- Python owns audio, Discord sessions, model downloads, and configuration.
- WinUI owns navigation, appearance, and the child process it starts.
- AppKit owns the same workspace on macOS, with native keyboard/menu-bar behavior and shutdown limited to its own child process.
- Keep settings backward compatible; add defaults and environment mappings for new fields.
- Never return secret values from the IPC API or log bot tokens/API keys.
- Preserve a local transcript before attempting a Discord upload.
- Respect reduced motion and keyboard navigation.
- Keep the Windows and macOS layouts and workflows coherent; use native AppKit for Mac UI changes.

Contributions are submitted under the project's 0BSD license. Keep upstream license notices for copied third-party code. Report security issues privately as described in SECURITY.md.
