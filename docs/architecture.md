# Architecture and platform roadmap

The Python core handles Discord voice ingestion, DAVE decryption, per-speaker buffers, silence gating, bounded inference queues, model downloads, Markdown exports, and optional summaries.

The Windows companion is a native WinUI 3/.NET 8 application. It talks to a loopback HTTP/WebSocket service, caches the last 100 live snippets for navigation, and owns the backend subprocess it launches. Configuration and downloaded models live outside the release directory. The runtime starts the API before it needs a token or speech model.

Meeting termination flushes buffered speech, drains queued inference, writes the Markdown file, and then attempts the Discord upload. An upload failure does not discard the saved file. One backend instance transcribes one voice channel at a time.

## Windows presentation

Use native controls and transitions, Mica when supported, responsive NavigationView, consistent spacing, explicit progress/error states, and system-aware reduced motion. Keep credentials in password fields and return only credential-presence flags through IPC.

## macOS next

The macOS companion is planned in `companion/macos/` using Swift 5.9+, AppKit, Combine, Foundation, Network, and UniformTypeIdentifiers on macOS 13+. It should reuse the existing IPC protocol with URLSession, an NSSplitViewController sidebar, NSVisualEffectView materials, and an optional menu-bar status item.

Apple Silicon inference needs a dedicated MLX/CoreML or whisper.cpp provider. The existing CTranslate2 Whisper backend supports CPU/CUDA, not Apple's MPS device. Do not label a CPU run as Neural Engine/Metal acceleration. Provider readiness, downloads, and cancellation should be validated before adding a new provider to the UI.

The macOS UI and Apple-specific acceleration are roadmap work, not part of the current Windows release.
