# Local companion API

The default origin is `http://127.0.0.1:8765`. Preview uses port 8767. Responses and WebSocket events never include stored token/API-key values; config exposes `*_CONFIGURED` booleans. Unexpected Host headers and cross-origin requests are rejected.

| Method | Route | Purpose |
|---|---|---|
| GET | /api/status | Runtime state, bot, voice, model/device, queue, session/process identifiers |
| GET / POST | /api/config | Read redacted configuration / validate and atomically persist edited fields |
| POST | /api/discord/validate | Check a supplied or saved bot token; return bot identity, servers, and invite URL |
| POST | /api/bot/start | Load the selected model and start Discord in managed mode |
| POST | /api/bot/stop | Finish the meeting and disconnect the managed bot |
| POST | /api/meeting/finish | Finish the active meeting while keeping the bot online |
| POST | /api/system/shutdown | Request orderly shutdown of a managed backend |
| GET | /api/models | Model catalog with real availability, installation, source links, selection |
| POST | /api/models/download | Start a download: `{"model_id":"whisper-base"}` |
| POST | /api/models/cancel | Cancel a running download with the same model_id |
| GET | /api/models/progress | Per-model status, percent, stage, and error |
| POST | /api/models/activate | Select a downloaded model or configured provider |
| POST | /api/engine/switch | Compatible engine switch route |
| GET | /api/transcripts | Markdown files, sizes, dates, and the export directory |
| GET | /api/transcripts/{filename} | Safe Markdown preview, limited to 5 MiB |
| POST | /api/summarize | Optional local/cloud notes for supplied transcript text |
| WS | /api/events | Status/config/engine changes, snippets, and download progress |

Managed status states are `idle`, `starting`, `connecting`, `online`, and `error`. The companion reports `offline` when the service cannot be reached. Model selection does not imply model loading; `engine_loaded` makes that distinction explicit.

Configuration validation failures return HTTP 400 with field messages, without input values. Transcript reads reject directory traversal and paths outside the export directory. A managed runtime prevents changing the bot account/server while it is running.

For protocol details, inspect `diswhisper/api/server.py` and `diswhisper/config.py`. This API is for a trusted local desktop, not a public network service.
