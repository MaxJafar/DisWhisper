import Foundation

struct ModelInfo {
    let id: String
    let name: String
    let category: String
    let description: String
    let languages: [String]
    let sizeMB: Int
    var downloaded: Bool
    let downloadable: Bool
    let available: Bool
    let active: Bool
    let sourceURL: String

    init(json: [String: Any]) {
        id = json.string("id")
        name = json.string("name")
        category = json.string("category")
        description = json.string("description")
        languages = json["languages"] as? [String] ?? []
        sizeMB = json.integer("size_mb")
        downloaded = json.flag("downloaded")
        downloadable = json.flag("downloadable")
        available = json.flag("available", default: true)
        active = json.flag("active")
        sourceURL = json.string("source_url")
    }

    var details: String {
        languages.joined(separator: ", ") + " · " + (sizeMB == 0 ? "Cloud API" : "~\(sizeMB.formatted()) MB download")
    }
    var activationLabel: String { active ? "Selected" : category == "local_llm" ? "Use for notes" : "Use model" }
    func statusText(progress: DownloadProgress?) -> String {
        if let progress {
            switch progress.status {
            case "downloading": return progress.detail + (progress.percent.map { " (\($0)%)" } ?? "…")
            case "failed": return "Download failed: \(progress.error)"
            case "cancelled": return "Download interrupted. Retry to resume."
            default: break
            }
        }
        if !available { return "Ollama is offline. Start Ollama, then refresh." }
        if active { return downloaded ? "Selected model" : "Selected · download to begin" }
        if downloaded { return downloadable ? "Installed" : "API key configured" }
        return downloadable ? "Ready to download" : "Configure an API key in Cloud providers"
    }
}

struct DownloadProgress {
    var status: String
    var percent: Int?
    var detail: String
    var error: String
    init(json: [String: Any]) {
        status = json.string("status")
        percent = (json["percent"] as? NSNumber)?.intValue
        detail = json.string("detail")
        error = json.string("error")
    }
}
