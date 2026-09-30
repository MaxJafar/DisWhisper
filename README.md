# DisWhisper 🎙️

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Whisper Model](https://img.shields.io/badge/Whisper-Large--v3-brightgreen.svg)](https://github.com/openai/whisper)
[![faster-whisper](https://img.shields.io/badge/Engine-CTranslate2-orange.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.0+-5865F2.svg)](https://discordpy.readthedocs.io/)

**DisWhisper** is a self-hosted, 100% free, and private Discord meeting transcriber bot powered by **Whisper Large-v3** (via `faster-whisper` and CTranslate2). 

It connects to your Discord voice channel, captures separate audio streams per speaker, buffers and downsamples audio into temporal slices, filters out silence, and streams live real-time transcripts into a designated text channel without lag or rate-limit spam.

---

## 🌟 Key Features

- **Local Real-Time Transcription:** Runs directly on your local hardware using `faster-whisper` (CTranslate2) with CUDA acceleration and `float16` precision, achieving end-to-end latency under 3 seconds.
- **User-Isolated Audio Buffering:** Decodes raw OPUS packets and isolates distinct PCM audio streams for each speaker by User ID.
- **Adaptive Silence Gating:** Computes Root Mean Square (RMS) amplitude per 2.5-second temporal chunk; silent chunks are immediately dropped to save GPU cycles and VRAM.
- **Live Output Interface with Debouncing:** Posts live transcripts to `#live-transcript` and automatically appends speech if the same user continues talking within a 5-second window.
- **Automatic Meeting Exporter:** Formats and exports clean Markdown meeting transcripts with timestamps and participant summaries to the `transcripts/` directory, and attaches the file directly to Discord when `/leave` is called.
- **CUDA OOM Recovery & CPU Fallback:** Gracefully recovers from GPU memory exhaustion, purges CUDA cache, and provides an automatic CPU fallback (`int8`).
- **Slash Commands:** Clean Discord interactions via `/join`, `/leave`, `/status`, and `/export`.

---

## 🏗️ System Architecture

```
[Discord Voice Channel]
         │ (48kHz Stereo OPUS Packets)
         ▼
[discord-ext-voice-recv + DisWhisperSink]
         │ (Decoded 16-bit PCM per User)
         ▼
[Audio Resampler]
         │ (Stereo -> Mono Averaging, 3:1 Downsample to 16kHz float32)
         ▼
[User-Isolated Audio Buffers]
         │ (2.5-second Temporal Slicing)
         │ ───> [RMS Silence Gating] ───> (< 0.01 RMS: Dropped)
         ▼ (Non-silent 16kHz Chunks)
[asyncio.Queue]
         │
         ▼
[CTranslate2 / faster-whisper Large-v3]
         │ (asyncio.to_thread Background Worker)
         ▼
[Real-Time Dispatcher]
         ├─► [Discord #live-transcript] (Debounced message editing)
         └─► [Markdown File Logger] (Saved to transcripts/meeting_*.md)
```

---

## 💻 Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **GPU** | NVIDIA GTX 1660 (6GB) | NVIDIA RTX 3060 / 4060 / 5060 (8GB+) |
| **VRAM** | 4GB (for `small` / `medium`) | 6GB–8GB (for `large-v3` with `float16`) |
| **CPU Fallback** | 4-core Modern CPU (`int8`) | 8-core CPU |
| **RAM** | 8 GB | 16 GB |
| **Disk** | ~4 GB (for Large-v3 model cache) | SSD |
| **OS** | Windows 10/11, Linux (Ubuntu 20.04+), macOS | Any |

---

## 📋 Prerequisites

1. **Python 3.10 or higher**
2. **FFmpeg** installed and accessible in your system `PATH`:
   - **Windows:** `winget install Gyan.FFmpeg` or download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
   - **Linux:** `sudo apt-get install -y ffmpeg`
   - **macOS:** `brew install ffmpeg`
3. **NVIDIA CUDA Toolkit & Drivers** (for GPU acceleration).

---

## 🚀 Quick Start Guide

### 1. Clone & Setup

```bash
git clone https://github.com/your-username/DisWhisper.git
cd DisWhisper
```

### 2. Run Automated Environment Checker & Installer

Run the included automated pre-flight setup script:

```bash
python scripts/install_dependencies.py
```

This validates your Python version, verifies FFmpeg, checks your NVIDIA GPU/CUDA capability, and installs all dependencies from `requirements.txt`.

### 3. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a **New Application**.
2. Navigate to the **Bot** tab:
   - Click **Add Bot**.
   - Under **Privileged Gateway Intents**, enable:
     - ✅ **Server Members Intent**
     - ✅ **Message Content Intent**
   - Click **Reset Token** and copy your **Bot Token**.
3. Navigate to **OAuth2 > URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions:
     - `Connect`
     - `Speak`
     - `Use Voice Activity`
     - `Send Messages`
     - `Manage Channels` (optional, for auto-creating `#live-transcript`)
     - `Attach Files`
     - `Read Message History`
4. Copy the generated invite link and authorize the bot to your Discord server.

### 4. Configure DisWhisper

Copy the example environment configuration:

```bash
# On Windows
copy .env.example .env

# On Linux/macOS
cp .env.example .env
```

Open `.env` in any text editor and fill in your token:

```env
DISCORD_TOKEN=your_discord_bot_token_here
GUILD_ID=your_guild_id_here  # Optional: speeds up slash command sync instantly
```

### 5. Launch the Bot

- **Windows:** Double-click `scripts\run.bat` or run:
  ```powershell
  python -m diswhisper.main
  ```
- **Linux/macOS:** Run `scripts/run.sh` or:
  ```bash
  python3 -m diswhisper.main
  ```

---

## 🎮 Slash Commands

| Command | Description |
|---------|-------------|
| `/join` | Connects DisWhisper to your current voice channel, sets up `#live-transcript`, and starts real-time transcription. |
| `/leave` | Stops recording, disconnects from voice, finalizes the session, and uploads the `.md` transcript file to Discord. |
| `/status` | Shows real-time metrics: active voice channel, GPU VRAM usage, queue size, and active speakers. |
| `/export` | Exports a snapshot of the ongoing meeting transcript without disconnecting. |

---

## ⚙️ Configuration Reference

All settings can be configured via environment variables in `.env` or in `config.json`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | *Required* | Discord Bot Token from Developer Portal. |
| `GUILD_ID` | `null` | Server ID for instant command sync. If omitted, global sync applies. |
| `TRANSCRIPT_CHANNEL_NAME`| `live-transcript` | Name of the text channel for real-time text output. |
| `WHISPER_MODEL_SIZE` | `large-v3` | Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`). |
| `DEVICE` | `cuda` | Hardware target: `cuda` or `cpu`. Auto-falls back to CPU if CUDA fails. |
| `COMPUTE_TYPE` | `float16` | Precision: `float16` (CUDA recommended), `int8_float16`, `int8`, `float32`. |
| `LANGUAGE` | `en` | Spoken language ISO code (`en`, `es`, `fr`, etc.) or empty for auto-detect. |
| `CHUNKING_DURATION_SEC`| `2.5` | Temporal chunk slice duration in seconds (2.0–3.0s recommended). |
| `SILENCE_THRESHOLD` | `0.01` | RMS amplitude threshold. Chunks quieter than this are dropped. |
| `CONTINUOUS_SPEECH_TIMEOUT_SEC` | `5.0` | Debounce window in seconds to append speech to the same message block. |
| `AUTO_SAVE_TRANSCRIPTS` | `true` | Save session markdown files to `transcripts/` folder. |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

---

## 🧪 Running Unit Tests

DisWhisper includes a full test suite validating audio decimation, channel downmixing, RMS gating, and configuration loading:

```bash
pytest tests/ -v
```

---

## 🛠️ Troubleshooting

### Missing FFmpeg
- If you see `RuntimeError: ffmpeg was not found`:
  Make sure FFmpeg is installed and added to your system `PATH`. Test it in your terminal by running `ffmpeg -version`.

### PyNaCl or Opus Library Warning
- `discord-ext-voice-recv` and `discord.py` require `pynacl`. Run:
  ```bash
  pip install pynacl
  ```
  On Windows, `pynacl` wheels are pre-compiled and install seamlessly.

### CUDA Out of Memory (OOM)
- If your GPU has less than 6GB VRAM, switch `WHISPER_MODEL_SIZE` in `.env`:
  ```env
  WHISPER_MODEL_SIZE=large-v3-turbo
  # OR
  WHISPER_MODEL_SIZE=medium
  ```
  `large-v3-turbo` runs up to 4x faster with minimal quality difference and lower VRAM usage.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
