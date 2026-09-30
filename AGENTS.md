# AGENTS.md — DisWhisper Developer & Multi-Platform Architecture Guide

Welcome to the **DisWhisper** engineering manual. This document guides AI agents and contributors on codebase conventions, IPC protocol design, and the technical roadmap for the **macOS AppKit Companion App**.

---

## 🏛️ System Architecture Overview

DisWhisper follows a decoupled, client-server architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                 DisWhisper Python Core                      │
│                                                             │
│  - Discord Voice Ingestion (discord-ext-voice-recv)         │
│  - Per-Speaker 2.5s Audio Buffers & RMS Silence Gating      │
│  - Local Models: Alibaba SenseVoice (<100ms) & Whisper-v3   │
│  - Cloud STT: Groq Whisper (LPU ~200ms) & OpenAI Whisper    │
│  - AI Summaries: Groq / OpenAI / Gemini / Ollama (Local)    │
│  - Embedded REST & WebSocket IPC Server (127.0.0.1:8765)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
               Standard REST & WebSocket IPC
               (http://127.0.0.1:8765)
                               │
         ┌─────────────────────┴─────────────────────┐
         ▼                                           ▼
┌─────────────────────────────┐             ┌─────────────────────────────┐
│    Windows Companion App    │             │      macOS Companion App    │
│  (WinUI 3 / XAML / .NET 8)  │             │   (Native Swift & AppKit)   │
│                             │             │                             │
│  - Fluent Design & Mica     │             │  - Native AppKit & Liquid   │
│  - Model Download Manager   │             │  - Apple Silicon Neural     │
│  - Real-Time Hardware Gauges│             │    Engine (CoreML / MLX)    │
│  - Cloud API Key Vault      │             │  - Menu Bar & NSSplitView   │
└─────────────────────────────┘             └─────────────────────────────┘
```

---

## 🍎 macOS AppKit Companion App Blueprint (Roadmap for Mac Device)

When polishing this project from your Mac, implement the companion app inside `companion/macos/` using **native Swift and AppKit**. 

### 1. Target Environment
- **Platform:** macOS 13.0+ (Ventura, Sonoma, Sequoia)
- **Toolchain:** Xcode 15+ / Swift 5.9+
- **Frameworks:** `AppKit`, `Combine`, `Foundation`, `Network`, `UniformTypeIdentifiers`

### 2. Directory Layout
```
companion/macos/
└── DisWhisperCompanion/
    ├── DisWhisperCompanion.xcodeproj
    ├── Sources/
    │   ├── App/
    │   │   ├── AppDelegate.swift
    │   │   └── MenuBarController.swift      # Optional menu bar status item
    │   ├── Models/
    │   │   ├── DisWhisperStatus.swift
    │   │   ├── ModelInfo.swift
    │   │   └── TranscriptItem.swift
    │   ├── Services/
    │   │   ├── DisWhisperClient.swift       # URLSession REST & WebSocket client
    │   │   └── ProcessManager.swift         # Starts/stops python backend subprocess
    │   ├── ViewControllers/
    │   │   ├── MainWindowController.swift   # NSWindowController with transparent titlebar
    │   │   ├── MainSplitViewController.swift# NSSplitViewController (Sidebar + Content)
    │   │   ├── SidebarViewController.swift  # NSOutlineView navigation
    │   │   ├── DashboardViewController.swift# Active bot stats & audio gauges
    │   │   ├── ModelsViewController.swift   # SenseVoice/Whisper/Ollama downloader
    │   │   ├── CloudViewController.swift    # Groq, OpenAI, Gemini key management
    │   │   ├── SettingsViewController.swift # Sliders for chunking & silence thresholds
    │   │   └── SummariesViewController.swift# AI meeting notes viewer
    │   └── Views/
    │       ├── MetricCardView.swift         # NSView with vibrant material & rounded corners
    │       └── WaveformVisualizer.swift     # CoreAnimation real-time speaking pulse
    └── Resources/
        ├── Assets.xcassets                  # App icon, SF Symbols
        └── Info.plist
```

### 3. Native AppKit Window & Aesthetic Principles
- **Window Chrome:** Set `window.titlebarAppearsTransparent = true` and `window.styleMask.insert(.fullSizeContentView)`.
- **Materials:** Use `NSVisualEffectView` with `.behindWindow` blending mode and `.underWindowBackground` material to achieve the signature macOS translucent frosted-glass aesthetic.
- **Navigation:** Implement `NSSplitViewController` where the sidebar houses an `NSOutlineView` using SF Symbols (`waveform`, `cpu`, `cloud`, `gearshape`, `doc.text.magnifyingglass`).
- **Menu Bar Companion:** Optionally instantiate `NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)` so users can monitor voice channel activity and trigger summaries directly from their macOS menu bar.

### 4. Apple Silicon (M1/M2/M3/M4) Optimizations
- **CoreML & MLX:** When running the Python core on macOS, agents should leverage the Apple Neural Engine (ANE) via `mlx-audio` or `whisper.cpp` CoreML models, enabling zero-fan-noise transcription on MacBooks.
- **Metal Acceleration:** CTranslate2 / PyTorch supports `device="mps"` (Metal Performance Shaders) on macOS.

---

## 📡 IPC REST & WebSocket API Specification

Both the **WinUI 3** app and the **macOS AppKit** app communicate with the Python backend via `http://127.0.0.1:8765`:

### 1. Endpoints

| Method | Route | Description | Request Body | Response Body |
|---|---|---|---|---|
| `GET` | `/api/status` | Bot connection, active engine, speakers, memory | None | `{"status": "online", "voice_connected": bool, "engine_name": str, ...}` |
| `GET` | `/api/config` | Retrieve current application configuration | None | `{ "STT_ENGINE": "sensevoice", "CHUNKING_DURATION_SEC": 2.5, ... }` |
| `POST` | `/api/config` | Update settings and persist to `config.json` | JSON dictionary of config keys | `{"status": "success", "config": {...}}` |
| `GET` | `/api/models` | Inventory of local & cloud models | None | `{"models": [{"id": "sensevoice", "name": ..., "downloaded": bool}]}` |
| `POST` | `/api/models/download` | Trigger background model download | `{"model_id": "sensevoice"}` | `{"status": "download_started", "model_id": str}` |
| `GET` | `/api/models/progress`| Get download percentages | None | `{"sensevoice": {"status": "downloading", "percent": 45}}` |
| `POST` | `/api/engine/switch` | Hot-swap active STT engine live | `{"engine": "sensevoice" \| "whisper" \| "cloud"}` | `{"status": "success", "active_engine": str}` |
| `POST` | `/api/summarize` | Generate AI meeting notes | `{"transcript_text": str, "provider": "cloud"\|"local"}` | `{"status": "success", "summary": str}` |
| `GET` | `/api/transcripts` | List saved meeting transcripts | None | `{"transcripts": [{"filename": str, "path": str, "size_bytes": int}]}` |
| `WS` | `/api/events` | Real-time WebSocket event stream | None | Broadcasts JSON events |

### 2. WebSocket Event Payloads

```json
// Event: transcript_snippet
{
  "event": "transcript_snippet",
  "data": {
    "user_id": 123456789,
    "speaker": "Alice",
    "text": "😄 Let's review the quarterly roadmap.",
    "timestamp": 1727718000.0
  },
  "timestamp": "2026-09-30T21:45:00Z"
}

// Event: download_progress
{
  "event": "download_progress",
  "data": {
    "model_id": "sensevoice",
    "percent": 85,
    "status": "downloading"
  }
}

// Event: engine_switched
{
  "event": "engine_switched",
  "data": {
    "engine_name": "SenseVoice (Alibaba)",
    "model_name": "SenseVoiceSmall-int8",
    "device": "cpu"
  }
}
```

---

## 🛠️ Developer Workflow & Guidelines

1. **Testing Before Committing:** Always run `pytest tests/ -v` to ensure DSP decimation, RMS silence gating, cloud engines, and API endpoints pass without errors.
2. **Backward Compatibility:** When introducing new configuration fields in `diswhisper/config.py`, always provide sensible default values and add them to `env_mappings`.
3. **No External Secrets:** Never commit `.env` or `config.json` containing live Discord tokens or Cloud API keys.
