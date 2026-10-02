import AppKit
import Combine
import Foundation

@MainActor
final class ProcessManager: ObservableObject {
    let dataDirectory: URL
    let sessionId = UUID().uuidString
    @Published private(set) var lastError = ""
    private let client: DisWhisperClient
    private let preview: Bool
    private var process: Process?
    private var logHandle: FileHandle?
    private var starting = false
    var ownsBackend: Bool { process?.isRunning == true }

    init(client: DisWhisperClient, preview: Bool) {
        self.client = client; self.preview = preview
        dataDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("DisWhisper").appendingPathComponent(preview ? "Preview" : "Data")
    }

    @discardableResult
    func ensureRunning() async -> Bool {
        if client.isDemo { return true }
        if starting { return false }
        starting = true
        defer { starting = false }
        if await client.refreshStatus(timeout: 1).status != "offline" { lastError = ""; return true }
        if ownsBackend { return false }
        do {
            try FileManager.default.createDirectory(at: dataDirectory, withIntermediateDirectories: true,
                                                    attributes: [.posixPermissions: 0o700])
            let config = dataDirectory.appendingPathComponent("config.json")
            if !FileManager.default.fileExists(atPath: config.path) {
                let defaults: [String: Any] = ["DEVICE": "cpu", "API_SERVER_PORT": preview ? 8767 : 8765]
                try JSONSerialization.data(withJSONObject: defaults, options: .prettyPrinted).write(to: config, options: .atomic)
                try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: config.path)
            }
            let child = Process()
            let bundled = Bundle.main.resourceURL?.appendingPathComponent("backend/diswhisper-backend")
            var arguments: [String] = []
            if let bundled, FileManager.default.isExecutableFile(atPath: bundled.path) {
                child.executableURL = bundled
                child.currentDirectoryURL = dataDirectory
            } else if let root = Self.sourceRoot() {
                let python = ProcessInfo.processInfo.environment["DISWHISPER_PYTHON"].map { URL(fileURLWithPath: $0) }
                    ?? root.appendingPathComponent(".venv/bin/python")
                guard FileManager.default.isExecutableFile(atPath: python.path) else {
                    throw APIError(message: "Run scripts/setup_macos.sh once to install the Python backend, then retry the local service.")
                }
                child.executableURL = python
                child.currentDirectoryURL = root
                arguments = ["-u", "-m", "diswhisper.main"]
            } else {
                throw APIError(message: "The backend is missing. Use the complete macOS build, or run scripts/setup_macos.sh in the source folder.")
            }
            arguments += ["--companion", "--data-dir", dataDirectory.path, "--config", config.path, "--session-id", sessionId]
            child.arguments = arguments
            var environment = ProcessInfo.processInfo.environment
            environment["PYTHONUTF8"] = "1"
            environment["HF_HOME"] = dataDirectory.appendingPathComponent("cache/huggingface").path
            environment["HF_HUB_DISABLE_TELEMETRY"] = "1"
            environment["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
            environment["HF_HUB_DISABLE_XET"] = "1"
            environment["API_SERVER_HOST"] = "127.0.0.1"
            environment["API_SERVER_PORT"] = String(preview ? 8767 : 8765)
            environment["ENABLE_API_SERVER"] = "true"
            child.environment = environment
            let logURL = dataDirectory.appendingPathComponent("backend.log")
            if !FileManager.default.fileExists(atPath: logURL.path) {
                FileManager.default.createFile(atPath: logURL.path, contents: nil, attributes: [.posixPermissions: 0o600])
            }
            try logHandle?.close()
            logHandle = try FileHandle(forWritingTo: logURL)
            try logHandle?.seekToEnd()
            child.standardOutput = logHandle
            child.standardError = logHandle
            try child.run()
            process = child
            for _ in 0..<40 {
                if !child.isRunning { break }
                try await Task.sleep(nanoseconds: 400_000_000)
                let status = await client.refreshStatus(timeout: 1)
                if status.status != "offline" {
                    guard status.sessionId == sessionId, status.processId == Int(child.processIdentifier) else {
                        throw APIError(message: "Another service took the DisWhisper port. Close that copy, then retry.")
                    }
                    lastError = ""
                    return true
                }
            }
            throw APIError(message: "The local service did not start. Open app data from Settings and check backend.log.")
        } catch {
            if let process, process.isRunning { process.terminate() }
            lastError = error.localizedDescription
            return false
        }
    }

    /// Only the child with this launch's session and PID may be shut down by this app.
    func shutdown() async -> Bool {
        guard let process, process.isRunning else { return true }
        let status = await client.refreshStatus(timeout: 2)
        guard status.sessionId == sessionId, status.processId == Int(process.processIdentifier) else {
            lastError = "The local service could not be identified. It is still running; check backend.log."
            return false
        }
        do { try await client.control("system/shutdown") }
        catch { lastError = "The local service is still finishing. Try Quit again in a moment."; return false }
        for _ in 0..<80 {
            if !process.isRunning {
                try? logHandle?.close(); logHandle = nil; self.process = nil
                return true
            }
            try? await Task.sleep(nanoseconds: 250_000_000)
        }
        lastError = "The backend is still finishing its meeting. Try Quit again in a moment."
        return false
    }

    func openDataDirectory() {
        try? FileManager.default.createDirectory(at: dataDirectory, withIntermediateDirectories: true)
        NSWorkspace.shared.open(dataDirectory)
    }

    private static func sourceRoot() -> URL? {
        var candidates: [URL] = [URL(fileURLWithPath: FileManager.default.currentDirectoryPath), Bundle.main.bundleURL]
        if let root = ProcessInfo.processInfo.environment["DISWHISPER_SOURCE_ROOT"] { candidates.insert(URL(fileURLWithPath: root), at: 0) }
        for candidate in candidates {
            var url = candidate
            for _ in 0..<12 {
                if FileManager.default.fileExists(atPath: url.appendingPathComponent("diswhisper/main.py").path)
                    && FileManager.default.fileExists(atPath: url.appendingPathComponent("pyproject.toml").path) { return url }
                let parent = url.deletingLastPathComponent()
                if parent == url { break }
                url = parent
            }
        }
        return nil
    }
}
