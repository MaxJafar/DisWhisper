import Foundation

struct TranscriptItem {
    let filename: String
    let path: String
    let sizeBytes: Int
    let modified: String
    init(json: [String: Any]) {
        filename = json.string("filename")
        path = json.string("path")
        sizeBytes = json.integer("size_bytes")
        modified = json.string("modified")
    }
    var title: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = formatter.date(from: modified) ?? ISO8601DateFormatter().date(from: modified)
        guard let date else { return filename }
        let display = DateFormatter()
        display.dateFormat = "MMM d · HH:mm"
        return display.string(from: date)
    }
    var caption: String { "Markdown · \(max(1, sizeBytes / 1024).formatted()) KB" }
}

struct LiveTranscript {
    let speaker: String
    let text: String
    let time: String
    init(json: [String: Any]) {
        speaker = json.string("speaker", default: "Speaker")
        text = json.string("text")
        let date = Date(timeIntervalSince1970: json.number("timestamp", default: Date().timeIntervalSince1970))
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        time = formatter.string(from: date)
    }
}

struct DiscordServer {
    let id: String
    let name: String
}

struct DiscordConnectionInfo {
    let botName: String
    let inviteURL: String
    let servers: [DiscordServer]
    init(json: [String: Any]) {
        botName = json.string("bot_name")
        inviteURL = json.string("invite_url")
        servers = (json["servers"] as? [[String: Any]] ?? []).map {
            DiscordServer(id: $0.string("id"), name: $0.string("name"))
        }
    }
}
