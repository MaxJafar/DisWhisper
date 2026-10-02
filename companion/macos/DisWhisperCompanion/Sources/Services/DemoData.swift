import Foundation

/// Explicitly opt-in sample data. Demo mode never connects, persists keys, or starts Python.
enum DemoData {
    static let status = DisWhisperStatus(json: [
        "status": "online", "bot_user": "DisWhisper", "voice_connected": true,
        "voice_channel": "Product room", "engine_name": "Whisper", "model_name": "base",
        "device": "cpu", "compute_type": "int8", "engine_loaded": true,
        "active_speaker_buffers": 3, "queue_depth": 0, "language": "en", "token_configured": true
    ])
    static let snippets = [
        LiveTranscript(json: ["speaker": "Alice", "text": "Let's make the next release feel like one workspace, on every platform.", "timestamp": 1_791_010_800]),
        LiveTranscript(json: ["speaker": "Max", "text": "Same familiar layout. Local speech models, and every conversation saved.", "timestamp": 1_791_010_815]),
        LiveTranscript(json: ["speaker": "Sam", "text": "I'll try the Mac build and share the meeting notes with the team.", "timestamp": 1_791_010_830])
    ]
    static let config: [String: Any] = [
        "DEVICE": "cpu", "COMPUTE_TYPE": "int8", "LANGUAGE": "en", "GUILD_ID": 1,
        "DISCORD_TOKEN_CONFIGURED": false, "GROQ_API_KEY_CONFIGURED": false, "OPENAI_API_KEY_CONFIGURED": false,
        "TRANSCRIPT_CHANNEL_NAME": "live-transcript", "AUTO_CREATE_TRANSCRIPT_CHANNEL": true,
        "AUTO_SAVE_TRANSCRIPTS": true, "AUTO_POST_TRANSCRIPTS": true, "AUTO_CONNECT_BOT": false,
        "AUTO_LEAVE_EMPTY_SEC": 60, "CHUNKING_DURATION_SEC": 2.5, "SILENCE_THRESHOLD": 0.01,
        "CONTINUOUS_SPEECH_TIMEOUT_SEC": 5, "LOCAL_SUMMARIZER_MODEL": "llama3.2:3b"
    ]
    static let transcript = "# Product catch-up\n\n## October 2, 2026\n\n**Alice:** Let's make the next release feel like one workspace, on every platform.\n\n**Max:** Same familiar layout. Local speech models, and every conversation saved.\n\n**Sam:** I'll try the Mac build and share the meeting notes with the team.\n"
    static func response(_ path: String, method: String, body: [String: Any]?) throws -> [String: Any] {
        if method == "POST" {
            if path == "summarize" { return ["summary": "# Meeting notes\n\nThe team reviewed the macOS companion.\n\n## Decisions\n- Keep a consistent layout across Windows and Mac.\n- Use local speech models by default.\n\n## Action items\n- Sam: try the Mac build and share feedback.\n\nSample notes from the demo conversation."] }
            throw APIError(message: "This is a demo conversation. Open the regular app to connect Discord or save changes.")
        }
        switch path {
        case "config": return config
        case "models/progress": return [:]
        case "models":
            let entries: [[String: Any]] = [
                ["id": "whisper-base", "name": "Whisper base", "description": "A lightweight multilingual model. A good place to start.", "size_mb": 145, "downloaded": true, "active": true],
                ["id": "whisper-tiny", "name": "Whisper tiny", "description": "The smallest Whisper model for quick, lightweight transcription.", "size_mb": 75],
                ["id": "whisper-small", "name": "Whisper small", "description": "More accuracy, with a little more memory and processing time.", "size_mb": 465],
                ["id": "sensevoice", "name": "SenseVoice small", "description": "Compact recognition with emotion and audio event tags.", "size_mb": 240]
            ]
            return ["models": entries.map { ["category": "local_stt", "languages": ["Multilingual"], "downloadable": true, "available": true, "source_url": "https://github.com/MaxJafar/DisWhisper"].merging($0) { _, value in value } }]
        case "transcripts": return ["transcripts": [["filename": "demo-meeting.md", "size_bytes": transcript.utf8.count, "modified": "2026-10-02T09:30:00Z"]], "directory": ""]
        case "transcripts/demo-meeting.md": return ["content": transcript]
        default: throw APIError(message: "This action is unavailable in the demo workspace.")
        }
    }
}
