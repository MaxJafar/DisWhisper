import AppKit

@MainActor
final class SummariesViewController: PageViewController {
    var preselectedFilename: String?
    private let transcript = OptionPicker([("Choose a meeting", "")])
    private let provider = OptionPicker([("Local · Ollama", "local"), ("Cloud · Groq", "groq"), ("Cloud · OpenAI", "openai")])
    private let privacy = UI.label("Local notes require Ollama and a downloaded language model. Your transcript is processed on this Mac.", color: Theme.secondary)
    private let result = TextEditor(height: 300)
    private var summary = ""
    private lazy var generate = ActionButton("Generate meeting notes", style: .primary) { [weak self] in self?.generateNotes() }
    private lazy var copy = ActionButton("Copy") { [weak self] in if let self { UI.copy(self.summary); self.notice.show("Copied", "Meeting notes are on the clipboard.") } }

    override func buildContent() {
        heading("From conversation to clarity.", "Optional meeting notes, decisions, and action items from a saved transcript.")
        provider.onChange = { [weak self] in self?.updatePrivacy() }
        add(CardView([
            UI.formRow("Meeting transcript", control: transcript), UI.formRow("Generate notes with", control: provider), privacy,
            UI.stack([
                generate,
                ActionButton("Set up provider") { [weak self] in guard let self else { return }; self.navigate(self.provider.value == "local" ? "models" : "cloud", nil) },
                UI.spacer()
            ], vertical: false, spacing: 12)
        ]))
        copy.isEnabled = false
        result.show("Your meeting notes will appear here.")
        result.textView.setAccessibilityLabel("Meeting notes")
        add(CardView([
            UI.stack([UI.label("Meeting notes", size: 18, weight: .semibold), UI.spacer(), copy], vertical: false), result,
            UI.label("AI notes can miss context. Check names, decisions, and action items against the original transcript.", color: Theme.secondary)
        ]))
    }
    override func reload() async {
        do {
            let selected = preselectedFilename ?? transcript.value
            let library = try await client.transcripts()
            transcript.removeAllItems()
            if library.items.isEmpty { transcript.addItem(withTitle: "Choose a meeting"); transcript.lastItem?.representedObject = "" }
            for item in library.items { transcript.addItem(withTitle: item.title); transcript.lastItem?.representedObject = item.filename }
            transcript.value = selected
            preselectedFilename = nil
        } catch { notice.show("Couldn't load meetings", error.localizedDescription) }
    }
    private func updatePrivacy() {
        privacy.stringValue = provider.value == "local" ? "Local notes require Ollama and a downloaded language model. Your transcript is processed on this Mac." : "Generating notes sends this transcript to the selected cloud provider. Their usage charges and privacy terms apply."
    }
    private func generateNotes() {
        let filename = transcript.value
        guard !filename.isEmpty else { notice.show("Choose a meeting", "Select a saved transcript first."); return }
        let selected = provider.value
        perform(generate, success: ("Meeting notes ready", "Copy the notes to share or save them.")) { [self] in
            transcript.isEnabled = false; provider.isEnabled = false; copy.isEnabled = false
            defer { transcript.isEnabled = true; provider.isEnabled = true; copy.isEnabled = !summary.isEmpty }
            let text = try await client.transcript(filename)
            guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw APIError(message: "This meeting has no transcript text to summarize.") }
            let config = try await client.config()
            let model = selected == "local" ? config.string("LOCAL_SUMMARIZER_MODEL", default: "llama3.2:3b") : selected == "openai" ? "gpt-4o-mini" : "llama-3.3-70b-versatile"
            summary = try await client.summarize(text: text, provider: selected, model: model)
            result.show(summary, markdown: true)
        }
    }
}
