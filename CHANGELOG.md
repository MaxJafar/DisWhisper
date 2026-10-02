# Changelog

## 0.2.1

- Native Swift/AppKit macOS app with the Windows workspace, a branded menu bar icon, keyboard navigation, and matching light/dark themes.
- macOS login Keychain credential storage, a portable Python backend, and bundled Discord Opus support.
- Windows installer with Start menu and optional desktop shortcuts, plus a portable ZIP.
- macOS disk images with an Applications shortcut for Apple Silicon and Intel, plus portable ZIPs.
- Shared release workflow that tests all three builds before publishing installers, checksums, and matching third-party sources.
- Actual AppKit UI screenshot and installation instructions for both platforms.

## 0.2.0

- Native Windows workspace with guided Discord setup, themes, reduced motion, keyboard navigation, a tray icon, and desktop shortcuts.
- Companion-managed backend that stays available before a bot or model is configured; explicit connect/disconnect and finish-meeting controls.
- Searchable model downloads for Whisper, SenseVoice, Vosk, and optional Ollama models, with availability, cancellation, and activation.
- Searchable Markdown transcript library and optional local/cloud meeting notes.
- Automatic dedicated Discord channel, safe meeting controls, bounded queues, final-audio draining, and completed-transcript sharing.
- Updated encrypted Discord voice handling with DAVE support.
- Loopback-only API, secret-free configuration responses, Windows DPAPI credential storage, and safe transcript previews.
- CPU defaults and early fallback when Windows CUDA libraries are unavailable.
- Portable Windows x64 packaging, CI, dependency notices, branding, and public documentation.
- Original project source and branding released under 0BSD.
