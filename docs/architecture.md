# Architecture and platform roadmap

The Python core handles Discord voice ingestion, DAVE decryption, per-speaker buffers, silence gating, bounded inference queues, model downloads, Markdown exports, and optional summaries.

The Windows companion is a native WinUI 3/.NET 8 application. It talks to a loopback HTTP/WebSocket service, caches the last 100 live snippets for navigation, and owns the backend subprocess it launches. Configuration and downloaded models live outside the release directory. The runtime starts the API before it needs a token or speech model.

Meeting termination flushes buffered speech, drains queued inference, writes the Markdown file, and then attempts the Discord upload. An upload failure does not discard the saved file. One backend instance transcribes one voice channel at a time.

## Windows presentation

Use native controls and transitions, Mica when supported, responsive NavigationView, consistent spacing, explicit progress/error states, and system-aware reduced motion. Keep credentials in password fields and return only credential-presence flags through IPC.

## macOS companion

The macOS companion in `companion/macos/DisWhisperCompanion/` uses Swift 5.9+, AppKit, Combine, and Foundation on macOS 13+. It implements the Windows companion's seven pages, spacing, violet/charcoal palette, card geometry, and workflows with native AppKit controls. URLSession provides REST and reconnecting WebSocket IPC; NSSplitViewController/NSOutlineView provide navigation, NSVisualEffectView provides sidebar material, and NSStatusBar keeps meeting controls available after the window closes.

The process manager starts a bundled PyInstaller backend or the source `.venv`, gives it a unique session ID, and stores its profile under `~/Library/Application Support/DisWhisper/Data`. It checks both the session and PID before requesting shutdown. An existing externally launched service is attached without claiming process ownership. Credentials use login-Keychain items addressed by opaque configuration references; replacements and failed writes clean up newly orphaned items.

`requirements-macos.lock` pins Ventura-compatible native wheels, including Vosk's upstream macOS universal2 release. The build uses standalone Python instead of a Homebrew framework, bundles the PyAV wheel's Opus decoder, and audits every Mach-O library for deployment targets and external paths. The Xcode project is committed; SwiftPM runs client regression tests. See [the Mac quickstart](macos-quickstart.md).

Apple Silicon inference needs a dedicated MLX/CoreML or whisper.cpp provider. The existing CTranslate2 Whisper backend supports CPU/CUDA, not Apple's MPS device. Do not label a CPU run as Neural Engine/Metal acceleration. Provider readiness, downloads, and cancellation should be validated before adding a new provider to the UI.

The AppKit companion is implemented. Apple-specific speech acceleration remains roadmap work; current local speech runs on CPU. The arm64 build has been validated on an Apple Silicon Mac, while Intel and macOS 13 hardware still need platform-specific runtime verification.
