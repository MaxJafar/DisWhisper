# DisWhisper architecture

The Python core handles Discord voice ingestion, DAVE decryption, per-speaker buffers, silence gating, bounded inference queues, model downloads, Markdown exports, and optional summaries.

The Windows companion is a native WinUI 3/.NET 8 application. It talks to a loopback HTTP/WebSocket service, caches the last 100 live snippets for navigation, and owns the backend subprocess it launches. Configuration and downloaded models live outside the release directory. The runtime starts the API before it needs a token or speech model.

Meeting termination flushes buffered speech, drains queued inference, writes the Markdown file, and then attempts the Discord upload. An upload failure does not discard the saved file. One backend instance transcribes one voice channel at a time.

## Windows presentation

The Windows app uses native controls and transitions, Mica when supported, responsive NavigationView, explicit progress/error states, and system-aware reduced motion. Credentials use password fields and Windows DPAPI; IPC returns only credential-presence flags.

## macOS companion

The macOS companion in `companion/macos/DisWhisperCompanion/` uses Swift 5.9+, AppKit, Combine, and Foundation on macOS 13+. It implements the Windows companion's seven pages, spacing, violet/charcoal palette, card geometry, and workflows with native AppKit controls. URLSession provides REST and reconnecting WebSocket IPC; NSSplitViewController/NSOutlineView provide navigation, NSVisualEffectView provides sidebar material, and NSStatusBar keeps meeting controls available after the window closes.

The process manager starts a bundled PyInstaller backend or the source `.venv`, gives it a unique session ID, and stores its profile under `~/Library/Application Support/DisWhisper/Data`. It checks both the session and PID before requesting shutdown. An existing externally launched service is attached without claiming process ownership. Credentials use login-Keychain items addressed by opaque configuration references; replacements and failed writes clean up newly orphaned items.

`requirements-macos.lock` pins Ventura-compatible native wheels, including Vosk's upstream macOS universal2 release. The build uses standalone Python instead of a Homebrew framework, bundles the PyAV wheel's Opus decoder, and audits every Mach-O library for deployment targets and external paths. The Xcode project is committed; SwiftPM runs client regression tests. See [the Mac quickstart](macos-quickstart.md).

Local speech inference on macOS runs on the CPU. CTranslate2 supports CPU/CUDA; the app does not currently include a Metal, CoreML, or MLX provider.

## Release packages

The release workflow builds the Windows x64 installer and portable ZIP, plus separate macOS arm64 and x86_64 DMGs and ZIPs. Packages include their backend runtime and dependency notices; SHA-256 checksum files and matching third-party source archives accompany the binaries. CI checks the Windows install/uninstall flow and each Mac app copied from its DMG, including signature verification and backend startup/shutdown. Build instructions are in [the contributor guide](../CONTRIBUTING.md).
