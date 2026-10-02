import AppKit
import Combine

@MainActor
final class DashboardViewController: PageViewController {
    private let heroTitle = UI.label("A home for every conversation.", size: 27, weight: .semibold, color: Theme.heroText)
    private let heroDescription = UI.label("Connect your own Discord bot, choose a speech model, and let the conversation flow.", color: Theme.heroText)
    private let heroLogo = LogoView(size: 90)
    private lazy var connectButton = ActionButton("Set up Discord", style: .primary) { [weak self] in self?.connect() }
    private let discordCard = MetricCardView(title: "DISCORD", value: "Not connected", detail: "Your bot, your server")
    private let modelCard = MetricCardView(title: "SPEECH MODEL", value: "Whisper", detail: "Choose a model to begin")
    private let computeCard = MetricCardView(title: "PROCESSING", value: "On this Mac", detail: "Local speech, without a subscription")
    private lazy var metrics = UI.stack([discordCard, modelCard, computeCard], vertical: false, spacing: 14)
    private var narrowConstraints: [NSLayoutConstraint] = []
    private let feed = UI.stack(spacing: 16)
    private let privacy = UI.label("Speech stays on your Mac with local models. Discord carries the call and the transcripts you choose to share.", size: 12, color: Theme.secondary)

    override func buildContent() {
        heading("Home", "Less note-taking. More conversation.")
        let actions = UI.stack([
            connectButton,
            ActionButton("Explore models") { [weak self] in self?.navigate("models", nil) }, UI.spacer()
        ], vertical: false, spacing: 10)
        let text = UI.stack([
            UI.eyebrow("YOUR CONVERSATIONS, WRITTEN.", color: Theme.brandText), heroTitle, heroDescription, actions
        ], spacing: 12)
        for child in [heroTitle, heroDescription, actions] { UI.fillWidth(child, in: text) }
        heroDescription.alphaValue = 0.8
        let heroRow = UI.stack([text, heroLogo], vertical: false, spacing: 24)
        add(CardView([heroRow], color: Theme.hero, padding: 28, radius: 20, bordered: false))
        metrics.distribution = .fillEqually
        metrics.alignment = .top
        add(metrics)
        narrowConstraints = [discordCard, modelCard, computeCard].map { $0.widthAnchor.constraint(equalTo: metrics.widthAnchor) }
        let feedHeader = UI.stack([
            UI.label("Recent conversation", size: 18, weight: .semibold), UI.spacer(),
            ActionButton("Transcript library →") { [weak self] in self?.navigate("transcripts", nil) }
        ], vertical: false)
        add(CardView([feedHeader, feed]))
        add(CardView([privacy], color: Theme.soft, padding: 16, radius: 12, bordered: false))
        client.$status.sink { [weak self] in self?.render($0) }.store(in: &subscriptions)
        client.$liveTranscripts.sink { [weak self] in self?.renderFeed($0) }.store(in: &subscriptions)
        processManager.$lastError.sink { [weak self] error in
            if !error.isEmpty { self?.notice.show("Local service", error) }
        }.store(in: &subscriptions)
    }

    override func viewDidLayout() {
        super.viewDidLayout()
        let narrow = view.bounds.width < 740
        if (metrics.orientation == .vertical) != narrow {
            NSLayoutConstraint.deactivate(narrowConstraints)
            metrics.orientation = narrow ? .vertical : .horizontal
            metrics.alignment = narrow ? .leading : .top
            if narrow { NSLayoutConstraint.activate(narrowConstraints) }
        }
        heroLogo.isHidden = narrow
    }
    private func render(_ status: DisWhisperStatus) {
        switch status.status {
        case "online": discordCard.value.stringValue = status.botUser
        case "starting": discordCard.value.stringValue = "Loading model…"
        case "connecting": discordCard.value.stringValue = "Connecting…"
        case "idle": discordCard.value.stringValue = "Ready to connect"
        case "error": discordCard.value.stringValue = "Needs attention"
        default: discordCard.value.stringValue = "Starting service…"
        }
        discordCard.detail.stringValue = status.voiceConnected ? "Listening in \(status.voiceChannel)" : "Join a voice channel, then use /join"
        modelCard.value.stringValue = status.engineName.replacingOccurrences(of: " (faster-whisper)", with: "")
        modelCard.detail.stringValue = "\(status.modelName.replacingOccurrences(of: "whisper-", with: "")) · \(status.language == "auto" ? "Automatic language" : status.language.uppercased())"
        computeCard.value.stringValue = !status.engineLoaded ? "Ready when you are" : status.device == "cloud" ? "Cloud provider" : "Local CPU"
        computeCard.detail.stringValue = status.voiceConnected ? "\(status.activeSpeakerBuffers) speaker buffers · \(status.queueDepth) chunks waiting" : status.engineLoaded ? "\(status.computeType) · Model loaded" : "Model loads when the bot connects"
        heroTitle.stringValue = status.voiceConnected ? "You're free to focus." : status.status == "online" ? "Ready for your next conversation." : "A home for every conversation."
        heroDescription.stringValue = status.voiceConnected ? "The meeting is being transcribed. Finish it here or use /leave in Discord to save and share the transcript." : status.status == "online" ? "Join your Discord voice channel and use /join. DisWhisper takes care of the transcript." : "Connect your own Discord bot, choose a speech model, and let the conversation flow."
        connectButton.title = status.voiceConnected ? "Finish meeting" : status.status == "offline" ? "Retry local service" : !status.tokenConfigured ? "Set up Discord" : status.status == "online" ? status.managed ? "Disconnect bot" : "Bot is connected" : "Connect bot"
        connectButton.isEnabled = !busy && !["starting", "connecting"].contains(status.status) && !(status.status == "online" && !status.managed && !status.voiceConnected)
        privacy.stringValue = status.device == "cloud" ? "This speech provider sends audio to its cloud service. Select Whisper, Vosk, or SenseVoice for speech processing on this Mac." : "Speech stays on your Mac with local models. Discord carries the call and the transcripts you choose to share."
        if status.status == "error", !status.error.isEmpty { notice.show("Couldn't connect", status.error) }
    }
    private func renderFeed(_ snippets: [LiveTranscript]) {
        for child in feed.arrangedSubviews { feed.removeArrangedSubview(child); child.removeFromSuperview() }
        if snippets.isEmpty {
            let title = UI.label("The next conversation starts here.", size: 16, weight: .semibold)
            let description = UI.label("Join a Discord voice channel and use /join. Recognized speech will appear here and in your dedicated Discord channel.", color: Theme.secondary)
            title.alignment = .center; description.alignment = .center
            description.widthAnchor.constraint(lessThanOrEqualToConstant: 430).isActive = true
            let empty = UI.stack([UI.symbol("text.bubble", size: 32), title, description], spacing: 10)
            empty.alignment = .centerX
            empty.edgeInsets = NSEdgeInsets(top: 28, left: 0, bottom: 28, right: 0)
            feed.addArrangedSubview(empty); UI.fillWidth(empty, in: feed)
        } else {
            for snippet in snippets.suffix(6) {
                let time = UI.label(snippet.time, size: 11, color: Theme.tertiary, wrap: false)
                time.widthAnchor.constraint(equalToConstant: 60).isActive = true
                let text = UI.label(snippet.text)
                text.isSelectable = true
                let body = UI.stack([UI.label(snippet.speaker, weight: .semibold, color: Theme.brandText), text], spacing: 5)
                UI.fillWidth(text, in: body)
                let row = UI.stack([time, body], vertical: false, spacing: 16)
                row.alignment = .top
                row.edgeInsets = NSEdgeInsets(top: 6, left: 2, bottom: 6, right: 2)
                feed.addArrangedSubview(row); UI.fillWidth(row, in: feed)
            }
        }
    }
    private func connect() {
        let status = client.status
        if !status.tokenConfigured && status.status != "offline" { navigate("discord", nil); return }
        perform(connectButton) { [self] in
            if status.status == "offline" {
                guard await processManager.ensureRunning() else { throw APIError(message: processManager.lastError) }
            } else {
                try await client.control(status.voiceConnected ? "meeting/finish" : status.status == "online" ? "bot/stop" : "bot/start")
            }
            render(await client.refreshStatus())
        }
    }
}
