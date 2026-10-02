import Foundation

struct DisWhisperStatus {
    var status = "offline"
    var botUser = "Not connected"
    var voiceConnected = false
    var voiceChannel = ""
    var engineName = "Whisper"
    var modelName = "base"
    var device = "cpu"
    var computeType = "int8"
    var queueDepth = 0
    var activeSpeakerBuffers = 0
    var uptimeSeconds = 0
    var engineLoaded = false
    var error = ""
    var tokenConfigured = false
    var managed = false
    var language = "auto"
    var sessionId = ""
    var processId = 0

    init(json: [String: Any] = [:]) {
        status = json.string("status", default: status)
        botUser = json.string("bot_user", default: botUser)
        voiceConnected = json.flag("voice_connected")
        voiceChannel = json.string("voice_channel")
        engineName = json.string("engine_name", default: engineName)
        modelName = json.string("model_name", default: modelName)
        device = json.string("device", default: device)
        computeType = json.string("compute_type", default: computeType)
        queueDepth = json.integer("queue_depth")
        activeSpeakerBuffers = json.integer("active_speaker_buffers")
        uptimeSeconds = json.integer("uptime_seconds")
        engineLoaded = json.flag("engine_loaded")
        error = json.string("error")
        tokenConfigured = json.flag("token_configured")
        managed = json.flag("managed")
        language = json.string("language", default: language)
        sessionId = json.string("session_id")
        processId = json.integer("process_id")
    }

    var sidebarText: String {
        if voiceConnected { return "Transcribing a meeting" }
        switch status {
        case "online": return "Connected to Discord"
        case "starting": return "Loading speech model"
        case "connecting": return "Connecting to Discord"
        case "idle": return "Local service ready"
        case "error": return "Needs your attention"
        default: return "Local service offline"
        }
    }
}

extension Dictionary where Key == String, Value == Any {
    func string(_ key: String, default fallback: String = "") -> String {
        self[key] as? String ?? fallback
    }
    func flag(_ key: String, default fallback: Bool = false) -> Bool {
        (self[key] as? NSNumber)?.boolValue ?? fallback
    }
    func integer(_ key: String, default fallback: Int = 0) -> Int {
        (self[key] as? NSNumber)?.intValue ?? fallback
    }
    func number(_ key: String, default fallback: Double = 0) -> Double {
        (self[key] as? NSNumber)?.doubleValue ?? fallback
    }
}
