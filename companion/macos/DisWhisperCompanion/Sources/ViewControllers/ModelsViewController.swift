import AppKit
import Combine

@MainActor
final class ModelsViewController: PageViewController, NSSearchFieldDelegate {
    private let search = NSSearchField()
    private let speech = UI.stack(spacing: 12)
    private let summaries = UI.stack(spacing: 12)
    private let cloud = UI.stack(spacing: 12)
    private var models: [ModelInfo] = []
    private var progress: [String: DownloadProgress] = [:]
    private var cards: [String: ModelCardView] = [:]
    private var refreshTask: Task<Void, Never>?
    private var refreshing = false

    override func buildContent() {
        heading("Models", "Download once. Transcribe locally, whenever you need.",
                action: ActionButton("Refresh") { [weak self] in Task { await self?.reload() } })
        add(CardView([
            UI.label("New here? Start with Whisper base.", weight: .semibold, color: Theme.brandText),
            UI.label("A lightweight multilingual model that runs on your CPU. Try small for more accuracy, or a larger model when your Mac has enough memory.", size: 12, color: Theme.secondary)
        ], color: Theme.soft, padding: 18, radius: 12, bordered: false))
        search.placeholderString = "Find a model or language…"
        search.delegate = self; search.sendsSearchStringImmediately = true
        search.translatesAutoresizingMaskIntoConstraints = false
        search.heightAnchor.constraint(equalToConstant: 34).isActive = true
        add(search); add(UI.label("Speech recognition", size: 18, weight: .semibold)); add(speech)
        add(DisclosureCard(title: "Local meeting notes · optional", views: [
            UI.label("Ollama runs the summary model on your Mac. Install and start Ollama once, then download a model here.", color: Theme.secondary),
            UI.link("Get Ollama ↗", address: "https://ollama.com/download/mac"), summaries
        ]))
        add(DisclosureCard(title: "Cloud speech providers · optional", views: [
            UI.label("Cloud providers require your own API key and send speech to that provider. Local models work without these services.", color: Theme.secondary),
            ActionButton("Set up optional cloud keys →") { [weak self] in self?.navigate("cloud", nil) }, cloud
        ]))
        add(UI.label("Model download sizes are approximate. Individual model licenses are available through Model details.", size: 11, color: Theme.tertiary))
        client.events.sink { [weak self] event in
            guard let self else { return }
            if event.name == "download_progress" {
                let id = event.data.string("model_id")
                let state = DownloadProgress(json: event.data)
                self.progress[id] = state
                self.cards[id]?.update(state)
                if state.status == "completed" { Task { await self.reload() } }
            } else if ["engine_switched", "config_updated", "connected"].contains(event.name), self.view.window != nil {
                Task { await self.reload() }
            }
        }.store(in: &subscriptions)
    }
    override func viewDidAppear() {
        super.viewDidAppear()
        refreshTask?.cancel()
        refreshTask = Task { [weak self] in
            while !Task.isCancelled {
                do { try await Task.sleep(nanoseconds: 3_000_000_000) } catch { return }
                guard let self else { return }
                if let states = try? await self.client.progress() {
                    self.progress = states
                    for (id, state) in states { self.cards[id]?.update(state) }
                }
            }
        }
    }
    override func viewDidDisappear() { super.viewDidDisappear(); refreshTask?.cancel(); refreshTask = nil }
    override func reload() async {
        guard !refreshing else { return }
        refreshing = true; defer { refreshing = false }
        do {
            models = try await client.models()
            progress = (try? await client.progress()) ?? [:]
            filter()
        } catch { notice.show("Couldn't load models", error.localizedDescription) }
    }
    func controlTextDidChange(_ obj: Notification) { filter() }
    private func filter() {
        for stack in [speech, summaries, cloud] {
            for child in stack.arrangedSubviews { stack.removeArrangedSubview(child); child.removeFromSuperview() }
        }
        cards.removeAll()
        let query = search.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let filtered = models.filter { query.isEmpty || ($0.name + " " + $0.description + " " + $0.languages.joined(separator: " ")).localizedCaseInsensitiveContains(query) }
        let sorted = filtered.sorted { lhs, rhs in lhs.id == "whisper-base" && rhs.id != "whisper-base" }
        for model in sorted {
            let card = ModelCardView(model: model) { [weak self] action in self?.act(action, model: model) }
            if let state = progress[model.id] { card.update(state) }
            let target = model.category == "local_llm" ? summaries : model.category == "cloud_stt" ? cloud : speech
            target.addArrangedSubview(card); UI.fillWidth(card, in: target)
            cards[model.id] = card
        }
        if speech.arrangedSubviews.isEmpty { speech.addArrangedSubview(UI.label(models.isEmpty ? "The local service will load your model catalog here." : "No speech models match your search.", color: Theme.secondary)) }
    }
    private func act(_ action: String, model: ModelInfo) {
        perform(nil, success: action == "activate" ? ("Model selected", "This model will be used when the bot connects. An already connected bot switches now.") : nil) { [self] in
            try await client.control("models/\(action)", body: ["model_id": model.id])
            await reload()
        }
    }
}

final class ModelCardView: CardView {
    private var model: ModelInfo
    private let statusLabel = UI.label("", size: 12, color: Theme.brandText)
    private let progressBar = NSProgressIndicator()
    private let download: ActionButton
    private let activate: ActionButton
    private let cancel: ActionButton
    init(model: ModelInfo, action: @escaping (String) -> Void) {
        self.model = model
        download = ActionButton(model.downloaded ? "Installed" : "Download", style: .primary) { action("download") }
        activate = ActionButton(model.activationLabel) { action("activate") }
        cancel = ActionButton("Cancel") { action("cancel") }
        let title = UI.label(model.name, size: 18, weight: .semibold)
        let titleRow = UI.stack([title, UI.spacer()], vertical: false, spacing: 9)
        if model.id == "whisper-base" { titleRow.insertArrangedSubview(UI.eyebrow("START HERE", color: Theme.brandText), at: 1) }
        progressBar.style = .bar; progressBar.maxValue = 100
        progressBar.translatesAutoresizingMaskIntoConstraints = false
        let details = UI.stack([
            titleRow, UI.label(model.description, color: Theme.secondary),
            UI.label(model.details, size: 11, color: Theme.tertiary), statusLabel, progressBar,
            UI.link("Model details ↗", address: model.sourceURL)
        ], spacing: 9)
        for child in details.arrangedSubviews { UI.fillWidth(child, in: details) }
        let buttons = UI.stack([download, activate, cancel], spacing: 9)
        buttons.widthAnchor.constraint(equalToConstant: 136).isActive = true
        for button in buttons.arrangedSubviews { UI.fillWidth(button, in: buttons) }
        let row = UI.stack([details, buttons], vertical: false, spacing: 20)
        super.init([row])
        update(nil)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    func update(_ progress: DownloadProgress?) {
        let downloading = progress?.status == "downloading"
        if progress?.status == "completed" { model.downloaded = true }
        statusLabel.stringValue = model.statusText(progress: progress)
        download.isHidden = !model.downloadable
        download.title = model.downloaded ? "Installed" : "Download"
        download.isEnabled = model.available && !model.downloaded && !downloading
        activate.isEnabled = model.available && model.downloaded && !model.active && !downloading
        progressBar.isHidden = !downloading
        cancel.isHidden = !downloading
        progressBar.isIndeterminate = progress?.percent == nil
        progressBar.doubleValue = Double(progress?.percent ?? 0)
        if downloading { progressBar.startAnimation(nil) } else { progressBar.stopAnimation(nil) }
    }
}

final class DisclosureCard: CardView {
    private let body: NSStackView
    private var expanded = false
    init(title: String, views: [NSView]) {
        body = UI.stack(views, spacing: 16)
        for child in views { UI.fillWidth(child, in: body) }
        super.init([])
        let toggle = ActionButton("›  " + title) { [weak self] in
            guard let self else { return }
            self.expanded.toggle()
            self.body.isHidden = !self.expanded
            (self.content.arrangedSubviews.first as? NSButton)?.title = (self.expanded ? "⌄  " : "›  ") + title
        }
        content.addArrangedSubview(toggle); UI.fillWidth(toggle, in: content)
        content.addArrangedSubview(body); UI.fillWidth(body, in: content)
        body.isHidden = true
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
}
