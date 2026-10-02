import Combine
import Foundation

struct BackendEvent {
    let name: String
    let data: [String: Any]
}

struct APIError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
    static func response(_ data: Data, status: Int) -> APIError {
        let json = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] ?? [:]
        var message = json.string("error", default: "The local service returned HTTP \(status).")
        if let fields = json["fields"] as? [[String: Any]] {
            message += fields.map { "\n\($0.string("field")): \($0.string("message"))" }.joined()
        }
        return APIError(message: message)
    }
}

@MainActor
final class DisWhisperClient: ObservableObject {
    let baseURL: URL
    let isDemo: Bool
    @Published private(set) var status = DisWhisperStatus()
    @Published private(set) var liveTranscripts: [LiveTranscript] = []
    let events = PassthroughSubject<BackendEvent, Never>()
    private let session: URLSession
    private var pollingTask: Task<Void, Never>?
    private var eventsTask: Task<Void, Never>?
    private var socket: URLSessionWebSocketTask?

    init(port: Int = 8765, demo: Bool = false, session: URLSession? = nil) {
        baseURL = URL(string: "http://127.0.0.1:\(port)")!
        isDemo = demo
        let configuration = URLSessionConfiguration.ephemeral
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.timeoutIntervalForRequest = 30
        self.session = session ?? URLSession(configuration: configuration)
        if demo {
            status = DemoData.status
            liveTranscripts = DemoData.snippets
        }
    }

    func request(_ path: String, method: String = "GET", body: [String: Any]? = nil,
                 timeout: TimeInterval = 30) async throws -> [String: Any] {
        if isDemo { return try DemoData.response(path, method: method, body: body) }
        let url = baseURL.appendingPathComponent("api").appendingPathComponent(path)
        var request = URLRequest(url: url, timeoutInterval: timeout)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError(message: "The service returned an invalid response.") }
        guard (200..<300).contains(http.statusCode) else { throw APIError.response(data, status: http.statusCode) }
        guard data.count <= 8 * 1024 * 1024,
              let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw APIError(message: "The service returned invalid JSON.")
        }
        return json
    }

    @discardableResult
    func refreshStatus(timeout: TimeInterval = 3) async -> DisWhisperStatus {
        if isDemo { status = DemoData.status; return status }
        do { status = DisWhisperStatus(json: try await request("status", timeout: timeout)) }
        catch { status = DisWhisperStatus() }
        return status
    }

    func config() async throws -> [String: Any] { try await request("config") }
    func updateConfig(_ updates: [String: Any]) async throws {
        _ = try await request("config", method: "POST", body: updates)
        await refreshStatus()
    }
    func models() async throws -> [ModelInfo] {
        let json = try await request("models")
        return (json["models"] as? [[String: Any]] ?? []).map(ModelInfo.init)
    }
    func progress() async throws -> [String: DownloadProgress] {
        try await request("models/progress", timeout: 5).compactMapValues {
            ($0 as? [String: Any]).map(DownloadProgress.init)
        }
    }
    func control(_ route: String, body: [String: Any] = [:]) async throws {
        _ = try await request(route, method: "POST", body: body, timeout: 120)
        await refreshStatus()
    }
    func transcripts() async throws -> (items: [TranscriptItem], directory: String) {
        let json = try await request("transcripts")
        return ((json["transcripts"] as? [[String: Any]] ?? []).map(TranscriptItem.init), json.string("directory"))
    }
    func transcript(_ filename: String) async throws -> String {
        guard !filename.contains("/"), !filename.contains("\\"), filename.hasSuffix(".md") else {
            throw APIError(message: "Choose a Markdown transcript from the library.")
        }
        return try await request("transcripts/" + filename).string("content")
    }
    func validateDiscord(_ token: String) async throws -> DiscordConnectionInfo {
        DiscordConnectionInfo(json: try await request("discord/validate", method: "POST", body: ["token": token]))
    }
    func summarize(text: String, provider: String, model: String?) async throws -> String {
        var body: [String: Any] = ["transcript_text": text, "provider": provider == "local" ? "local" : "cloud"]
        if provider != "local" { body["cloud_platform"] = provider }
        if let model { body["model"] = model }
        return try await request("summarize", method: "POST", body: body, timeout: 300).string("summary")
    }
    func checkCloudKey(_ key: String, provider: String) async throws {
        if isDemo { throw APIError(message: "Open the regular workspace to check a real API key.") }
        let address = provider == "groq" ? "https://api.groq.com/openai/v1/models" : "https://api.openai.com/v1/models"
        var request = URLRequest(url: URL(string: address)!, timeoutInterval: 15)
        request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        do {
            let (_, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                throw APIError(message: "The provider returned HTTP \((response as? HTTPURLResponse)?.statusCode ?? 0). Check the key and account.")
            }
        } catch { throw APIError(message: error.localizedDescription.replacingOccurrences(of: key, with: "[credential]")) }
    }

    func start() {
        guard pollingTask == nil, !isDemo else { return }
        pollingTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await self.refreshStatus()
                do { try await Task.sleep(nanoseconds: 2_000_000_000) } catch { return }
            }
        }
        eventsTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                let url = URL(string: "ws://127.0.0.1:\(self.baseURL.port!)/api/events")!
                let socket = self.session.webSocketTask(with: url)
                socket.maximumMessageSize = 1024 * 1024
                self.socket = socket
                socket.resume()
                do {
                    while !Task.isCancelled {
                        let message = try await socket.receive()
                        let data: Data
                        switch message {
                        case .string(let text): data = Data(text.utf8)
                        case .data(let bytes): data = bytes
                        @unknown default: continue
                        }
                        if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                           let name = json["event"] as? String, let body = json["data"] as? [String: Any] {
                            if name == "transcript_snippet" {
                                self.liveTranscripts.append(LiveTranscript(json: body))
                                if self.liveTranscripts.count > 100 { self.liveTranscripts.removeFirst(self.liveTranscripts.count - 100) }
                            }
                            self.events.send(BackendEvent(name: name, data: body))
                            if ["bot_status", "engine_switched", "connected", "config_updated"].contains(name) {
                                await self.refreshStatus()
                            }
                        }
                    }
                } catch { /* Polling keeps connection state accurate during reconnects. */ }
                socket.cancel(with: .goingAway, reason: nil)
                do { try await Task.sleep(nanoseconds: 3_000_000_000) } catch { return }
            }
        }
    }
    func stop() {
        pollingTask?.cancel(); pollingTask = nil
        eventsTask?.cancel(); eventsTask = nil
        socket?.cancel(with: .goingAway, reason: nil); socket = nil
    }
}
