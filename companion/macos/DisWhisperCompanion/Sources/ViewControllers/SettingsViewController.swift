import AppKit

@MainActor
final class SettingsViewController: PageViewController {
    private let theme = OptionPicker([("Use macOS setting", "system"), ("Light", "light"), ("Dark", "dark")])
    private let motion = UI.check("Smooth transitions", on: true)
    private let device = OptionPicker([("Automatic · local CPU", "auto"), ("CPU", "cpu")])
    private let language = UI.field("auto, en, ru, de, tr…")
    private let precision = OptionPicker([("Int8 · smaller memory footprint", "int8"), ("Float32", "float32")])
    private let channel = UI.field("live-transcript")
    private let create = UI.check("Create this channel when the bot joins a server", on: true)
    private let post = UI.check("Share the complete transcript when a meeting finishes", on: true)
    private let autoSave = UI.check("Save transcripts on this Mac", on: true)
    private let autoConnect = UI.check("Connect my bot when DisWhisper opens")
    private let emptyDelay = NumberField(value: 60, range: 0...3600, step: 1)
    private let chunk = NumberField(value: 2.5, range: 0.5...10, step: 0.5)
    private let silence = NumberField(value: 0.01, range: 0...1, step: 0.002)
    private let debounce = NumberField(value: 5, range: 0.5...60, step: 0.5)
    private lazy var save = ActionButton("Save settings", style: .primary) { [weak self] in self?.saveSettings() }

    override func buildContent() {
        heading("Make it yours.", "A comfortable workspace and sensible defaults for every conversation.")
        theme.value = UserDefaults.standard.string(forKey: "theme") ?? "system"
        motion.isOn = UserDefaults.standard.object(forKey: "motionEnabled") as? Bool ?? true
        theme.onChange = { [weak self] in self?.saveAppearance() }
        motion.target = self; motion.action = #selector(motionChanged)
        add(CardView([
            UI.label("Appearance", size: 18, weight: .semibold), UI.formRow("App theme", control: theme), motion,
            UI.label("DisWhisper also respects the macOS Reduce Motion setting.", color: Theme.secondary)
        ]))
        add(CardView([
            UI.label("Speech processing", size: 18, weight: .semibold), UI.formRow("Run local speech models on", control: device),
            UI.formRow("Speech language", control: language),
            UI.label("Use auto for language detection, or an ISO language code for more predictable results. Vosk models use their own language.", color: Theme.secondary),
            UI.formRow("Whisper precision", control: precision)
        ]))
        add(CardView([
            UI.label("Meeting transcripts", size: 18, weight: .semibold), UI.formRow("Dedicated Discord channel", control: channel),
            create, post, autoSave, autoConnect, UI.formRow("Finish after everyone leaves · seconds", control: emptyDelay),
            UI.label("Set this delay to 0 to finish meetings manually. Closing the window keeps the app in the menu bar; Quit finishes the meeting and exits.", color: Theme.secondary),
            UI.stack([
                ActionButton("Open app data") { [weak self] in self?.processManager.openDataDirectory() },
                ActionButton("Discord setup") { [weak self] in self?.navigate("discord", nil) }, UI.spacer()
            ], vertical: false, spacing: 12)
        ]))
        add(DisclosureCard(title: "Advanced audio settings", views: [
            UI.formRow("Audio chunk duration · seconds", control: chunk),
            UI.label("Shorter chunks reduce delay; longer chunks give the model more context.", color: Theme.secondary),
            UI.formRow("Silence threshold · RMS", control: silence),
            UI.formRow("Combine consecutive speech in Discord · seconds", control: debounce)
        ]))
        add(UI.stack([save, UI.spacer()], vertical: false))
        add(UI.label("DisWhisper 0.2 · Free and open source. Original code and branding: 0BSD.", size: 12, color: Theme.secondary))
        add(UI.link("Dependency licenses and corresponding source ↗", address: "https://github.com/MaxJafar/DisWhisper/releases/latest"))
    }
    override func reload() async {
        do {
            let config = try await client.config()
            device.value = config.string("DEVICE", default: "cpu")
            if device.value != "auto" { device.value = "cpu" }
            precision.value = config.string("COMPUTE_TYPE", default: "int8")
            language.stringValue = config.string("LANGUAGE", default: "auto")
            channel.stringValue = config.string("TRANSCRIPT_CHANNEL_NAME", default: "live-transcript")
            create.isOn = config.flag("AUTO_CREATE_TRANSCRIPT_CHANNEL", default: true)
            post.isOn = config.flag("AUTO_POST_TRANSCRIPTS", default: true)
            autoSave.isOn = config.flag("AUTO_SAVE_TRANSCRIPTS", default: true)
            autoConnect.isOn = config.flag("AUTO_CONNECT_BOT")
            emptyDelay.value = config.number("AUTO_LEAVE_EMPTY_SEC", default: 60)
            chunk.value = config.number("CHUNKING_DURATION_SEC", default: 2.5)
            silence.value = config.number("SILENCE_THRESHOLD", default: 0.01)
            debounce.value = config.number("CONTINUOUS_SPEECH_TIMEOUT_SEC", default: 5)
        } catch { notice.show("Local service unavailable", error.localizedDescription) }
    }
    @objc private func motionChanged() { saveAppearance() }
    private func saveAppearance() {
        UserDefaults.standard.set(theme.value, forKey: "theme")
        UserDefaults.standard.set(motion.isOn, forKey: "motionEnabled")
        NSApp.appearance = theme.value == "system" ? nil : NSAppearance(named: theme.value == "dark" ? .darkAqua : .aqua)
    }
    private func saveSettings() {
        guard let emptyValue = emptyDelay.value, let chunkValue = chunk.value,
              let silenceValue = silence.value, let debounceValue = debounce.value else {
            notice.show("Check the numbers", "Fill in each audio setting with a number in its allowed range before saving."); return
        }
        perform(save, success: ("Settings saved", "Your next audio chunks use these settings.")) { [self] in
            try await client.updateConfig([
                "TRANSCRIPT_CHANNEL_NAME": channel.stringValue.trimmingCharacters(in: .whitespacesAndNewlines),
                "LANGUAGE": language.stringValue.trimmingCharacters(in: .whitespacesAndNewlines),
                "DEVICE": device.value, "COMPUTE_TYPE": precision.value,
                "AUTO_CREATE_TRANSCRIPT_CHANNEL": create.isOn, "AUTO_POST_TRANSCRIPTS": post.isOn,
                "AUTO_SAVE_TRANSCRIPTS": autoSave.isOn, "AUTO_CONNECT_BOT": autoConnect.isOn,
                "AUTO_LEAVE_EMPTY_SEC": emptyValue, "CHUNKING_DURATION_SEC": chunkValue,
                "SILENCE_THRESHOLD": silenceValue, "CONTINUOUS_SPEECH_TIMEOUT_SEC": debounceValue
            ])
        }
    }
}

final class NumberField: NSView {
    private let field = UI.field()
    private let stepper = NSStepper()
    private let range: ClosedRange<Double>
    var value: Double? {
        get {
            guard let number = Double(field.stringValue), number.isFinite, range.contains(number) else { return nil }
            return number
        }
        set { field.stringValue = newValue.map { String(format: "%g", $0) } ?? ""; stepper.doubleValue = newValue ?? range.lowerBound }
    }
    init(value: Double, range: ClosedRange<Double>, step: Double) {
        self.range = range
        super.init(frame: .zero)
        translatesAutoresizingMaskIntoConstraints = false
        stepper.minValue = range.lowerBound; stepper.maxValue = range.upperBound
        stepper.increment = step; stepper.doubleValue = value
        stepper.target = self; stepper.action = #selector(stepped)
        stepper.translatesAutoresizingMaskIntoConstraints = false
        addSubview(field); addSubview(stepper)
        NSLayoutConstraint.activate([
            field.leadingAnchor.constraint(equalTo: leadingAnchor), field.topAnchor.constraint(equalTo: topAnchor),
            field.bottomAnchor.constraint(equalTo: bottomAnchor), field.trailingAnchor.constraint(equalTo: stepper.leadingAnchor, constant: -8),
            stepper.trailingAnchor.constraint(equalTo: trailingAnchor), stepper.centerYAnchor.constraint(equalTo: centerYAnchor)
        ])
        self.value = value
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    @objc private func stepped() { value = stepper.doubleValue }
}
