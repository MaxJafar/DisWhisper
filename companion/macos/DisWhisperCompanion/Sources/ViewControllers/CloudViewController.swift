import AppKit

@MainActor
final class CloudViewController: PageViewController {
    private let groq = UI.field("Paste a Groq API key", secure: true)
    private let openai = UI.field("Paste an OpenAI API key", secure: true)
    private lazy var save = ActionButton("Save keys", style: .primary) { [weak self] in self?.saveKeys() }
    override func buildContent() {
        heading("More options, when you need them.", "Local speech models work without API keys. Cloud transcription and notes are optional.")
        add(providerCard("Groq", provider: "groq", field: groq, link: "https://console.groq.com/keys"))
        add(providerCard("OpenAI", provider: "openai", field: openai, link: "https://platform.openai.com/api-keys"))
        add(UI.label("Blank fields keep saved keys. Your login Keychain protects newly saved credentials. Cloud providers receive the audio or transcript sent to them and may charge for usage.", color: Theme.secondary))
        add(UI.stack([save, UI.spacer()], vertical: false))
    }
    private func providerCard(_ title: String, provider: String, field: NSTextField, link: String) -> CardView {
        let check = ActionButton("Check new key") { [weak self] in self?.test(field, provider: provider) }
        return CardView([
            UI.label(title, size: 18, weight: .semibold),
            UI.label("Cloud Whisper transcription and meeting notes.", color: Theme.secondary),
            UI.formRow("API key", control: field),
            UI.stack([check, UI.link("Get an API key ↗", address: link), UI.spacer()], vertical: false, spacing: 12)
        ])
    }
    override func reload() async {
        do {
            let config = try await client.config()
            for (key, field) in [("GROQ_API_KEY", groq), ("OPENAI_API_KEY", openai)] {
                field.placeholderString = config.flag(key + "_CONFIGURED") ? "Key saved · leave blank to keep it" : "Paste an API key"
            }
        } catch { notice.show("Local service unavailable", error.localizedDescription) }
    }
    private func saveKeys() {
        var updates: [String: Any] = [:]
        for (key, field) in [("GROQ_API_KEY", groq), ("OPENAI_API_KEY", openai)] {
            let value = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
            if !value.isEmpty { updates[key] = value }
        }
        guard !updates.isEmpty else { notice.show("Keys unchanged", "Paste a new key to replace a saved one."); return }
        perform(save, success: ("Keys saved", "Choose a cloud provider in Models or Meeting notes when you want to use it.")) { [self] in
            try await client.updateConfig(updates)
            groq.stringValue = ""; openai.stringValue = ""
            await reload()
        }
    }
    private func test(_ field: NSTextField, provider: String) {
        let key = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !key.isEmpty else { notice.show("Paste a new key", "Checks use the key in this field. Saved keys stay private."); return }
        perform(nil, success: ("Key verified", "This key can access the provider. Save it to use it in DisWhisper.")) { [self] in
            try await client.checkCloudKey(key, provider: provider)
        }
    }
}
