import Foundation
import XCTest
@testable import DisWhisperCompanion

final class MockURLProtocol: URLProtocol {
    static var handler: ((URLRequest) throws -> (Int, Data))?
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        do {
            let (status, data) = try Self.handler!(request)
            let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch { client?.urlProtocol(self, didFailWithError: error) }
    }
    override func stopLoading() {}
    static func body(_ request: URLRequest) -> Data {
        if let data = request.httpBody { return data }
        guard let stream = request.httpBodyStream else { return Data() }
        stream.open(); defer { stream.close() }
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: 4096)
        while stream.hasBytesAvailable {
            let count = stream.read(&buffer, maxLength: buffer.count)
            if count <= 0 { break }
            data.append(buffer, count: count)
        }
        return data
    }
}

final class ClientTests: XCTestCase {
    @MainActor private func client(_ handler: @escaping (URLRequest) throws -> (Int, Data)) -> DisWhisperClient {
        MockURLProtocol.handler = handler
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [MockURLProtocol.self]
        return DisWhisperClient(session: URLSession(configuration: configuration))
    }
    @MainActor func testStatusHandlesNullsAndKeepsBackendOwnership() async {
        let client = client { request in
            XCTAssertEqual(request.url?.path, "/api/status")
            return (200, Data(#"{"status":"idle","voice_channel":null,"language":null,"managed":true,"session_id":"owned","process_id":123,"queue_depth":4}"#.utf8))
        }
        let status = await client.refreshStatus()
        XCTAssertEqual(status.status, "idle")
        XCTAssertEqual(status.voiceChannel, "")
        XCTAssertEqual(status.language, "auto")
        XCTAssertEqual(status.sessionId, "owned")
        XCTAssertEqual(status.processId, 123)
        XCTAssertEqual(status.queueDepth, 4)
    }
    @MainActor func testConnectionLossReplacesStaleOnlineState() async {
        var online = true
        let client = client { _ in
            if online { return (200, Data(#"{"status":"online","voice_connected":true}"#.utf8)) }
            throw URLError(.cannotConnectToHost)
        }
        let initial = await client.refreshStatus()
        XCTAssertTrue(initial.voiceConnected)
        online = false
        let status = await client.refreshStatus()
        XCTAssertEqual(status.status, "offline")
        XCTAssertFalse(status.voiceConnected)
    }
    @MainActor func testConfigErrorsExposeFieldMessagesWithoutEchoingInput() async {
        let client = client { request in
            XCTAssertEqual(request.httpMethod, "POST")
            return (400, Data(#"{"error":"Invalid configuration","fields":[{"field":"SILENCE_THRESHOLD","message":"Must be at most 1"}]}"#.utf8))
        }
        do { try await client.updateConfig(["SILENCE_THRESHOLD": 2]); XCTFail("Expected validation failure") }
        catch { XCTAssertTrue(error.localizedDescription.contains("SILENCE_THRESHOLD: Must be at most 1")) }
    }
    @MainActor func testTranscriptFilenameIsEncodedAndTraversalRejected() async throws {
        let client = client { request in
            XCTAssertEqual(request.url?.path, "/api/transcripts/meeting #1.md")
            XCTAssertNil(request.url?.fragment)
            return (200, Data(#"{"content":"Alice: Hello"}"#.utf8))
        }
        let content = try await client.transcript("meeting #1.md")
        XCTAssertEqual(content, "Alice: Hello")
        for name in ["../config.json", "..\\secret.md", "config.json"] {
            do { _ = try await client.transcript(name); XCTFail("Expected filename rejection") } catch {}
        }
    }
    @MainActor func testCloudSummaryCarriesExplicitSelectedProvider() async throws {
        let client = client { request in
            let input = try JSONSerialization.jsonObject(with: MockURLProtocol.body(request)) as! [String: Any]
            XCTAssertEqual(input["provider"] as? String, "cloud")
            XCTAssertEqual(input["cloud_platform"] as? String, "openai")
            XCTAssertEqual(input["model"] as? String, "gpt-4o-mini")
            return (200, Data(#"{"summary":"Meeting notes"}"#.utf8))
        }
        let notes = try await client.summarize(text: "Alice: Hello", provider: "openai", model: "gpt-4o-mini")
        XCTAssertEqual(notes, "Meeting notes")
    }
    @MainActor func testDemoCannotWriteConfigurationOrCallProviders() async throws {
        let client = DisWhisperClient(demo: true)
        do { try await client.updateConfig(["DISCORD_TOKEN": "test-only"]); XCTFail("Demo must reject mutations") } catch {}
        do { try await client.checkCloudKey("test-only", provider: "groq"); XCTFail("Demo must reject real providers") } catch {}
        let config = try await client.config()
        XCTAssertFalse(config.flag("DISCORD_TOKEN_CONFIGURED"))
        XCTAssertEqual(client.liveTranscripts.count, 3)
    }
    func testModelDownloadCompletionAllowsActivation() {
        let model = ModelInfo(json: ["id": "whisper-base", "downloaded": false, "available": true, "downloadable": true])
        XCTAssertEqual(model.statusText(progress: DownloadProgress(json: ["status": "cancelled"])), "Download interrupted. Retry to resume.")
        XCTAssertEqual(model.activationLabel, "Use model")
    }
}
