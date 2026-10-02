import AppKit

@MainActor
final class DiscordSetupViewController: PageViewController, NSTextFieldDelegate {
    private let token = UI.field("Paste your bot token", secure: true)
    private let botName = UI.label("", weight: .semibold, color: Theme.brandText)
    private let server = OptionPicker([("Check your token to list servers", "")])
    private let language = OptionPicker([
        ("Detect automatically", "auto"), ("English", "en"), ("Русский · Russian", "ru"),
        ("Türkçe · Turkish", "tr"), ("Deutsch · German", "de"), ("Français · French", "fr"),
        ("Español · Spanish", "es"), ("中文 · Chinese", "zh")
    ])
    private let autoConnect = UI.check("Connect this bot when DisWhisper opens", on: true)
    private var connection: DiscordConnectionInfo?
    private var selectedServerId = ""
    private lazy var check = ActionButton("Check connection") { [weak self] in self?.checkConnection() }
    private lazy var invite = ActionButton("Invite bot to a server ↗") { [weak self] in self?.inviteBot() }
    private lazy var save = ActionButton("Save and choose a speech model →", style: .primary) { [weak self] in self?.saveConnection() }

    override func buildContent() {
        heading("Connect Discord", "Your own bot. Your own server. A few steps, once.")
        token.delegate = self
        invite.isEnabled = false
        add(CardView([
            step("01", "Create your bot"),
            UI.label("Open the Discord Developer Portal, create an application, then open its Bot page. Generate a bot token and copy it.", color: Theme.secondary),
            UI.link("Open Discord Developer Portal ↗", address: "https://discord.com/developers/applications")
        ]))
        add(CardView([
            step("02", "Connect your bot account"), UI.formRow("Bot token", control: token),
            UI.label("Saved on this Mac. Your login Keychain protects saved tokens.", size: 12, color: Theme.secondary),
            UI.stack([check, botName, UI.spacer()], vertical: false, spacing: 12)
        ]))
        add(CardView([
            step("03", "Choose your server"),
            UI.label("Invite the bot with the required permissions. DisWhisper creates #live-transcript for recognized speech and completed meeting files.", color: Theme.secondary),
            UI.stack([invite, UI.spacer()], vertical: false), UI.formRow("Server", control: server),
            UI.label("After inviting the bot, check the connection again to refresh this list.", size: 12, color: Theme.secondary),
            UI.formRow("Main speech language", control: language), autoConnect
        ]))
        add(UI.stack([save, UI.spacer()], vertical: false))
        add(UI.label("Use /join in a Discord voice channel to begin. Use /leave to finish. DisWhisper never starts recording just because you open the app.", size: 12, color: Theme.secondary))
    }
    private func step(_ number: String, _ title: String) -> NSStackView {
        UI.stack([UI.label(number, weight: .semibold, color: Theme.brandText), UI.label(title, size: 18, weight: .semibold), UI.spacer()], vertical: false, spacing: 12)
    }
    override func reload() async {
        do {
            let config = try await client.config()
            selectedServerId = (config["GUILD_ID"] as? NSNumber)?.stringValue ?? ""
            token.placeholderString = config.flag("DISCORD_TOKEN_CONFIGURED") ? "Token saved · leave blank to keep it" : "Paste your bot token"
            language.value = config.string("LANGUAGE", default: "auto")
            autoConnect.isOn = config.flag("AUTO_CONNECT_BOT")
            if client.status.status == "online" && !client.isDemo { notice.show("Your bot is connected", "Disconnect it from Home before switching bot accounts or servers.") }
        } catch { notice.show("Local service is starting", "Try again in a moment, or retry the service from Home.") }
    }
    func controlTextDidChange(_ obj: Notification) {
        connection = nil; invite.isEnabled = false
        botName.stringValue = "Check your bot account"
    }
    private func checkConnection() {
        perform(check) { [self] in
            token.isEnabled = false
            defer { token.isEnabled = true }
            let result = try await client.validateDiscord(token.stringValue.trimmingCharacters(in: .whitespacesAndNewlines))
            connection = result
            botName.stringValue = "Connected as \(result.botName)"
            invite.isEnabled = true
            server.removeAllItems()
            for guild in result.servers { server.addItem(withTitle: guild.name); server.lastItem?.representedObject = guild.id }
            server.value = selectedServerId
            notice.show(result.servers.isEmpty ? "Invite your bot next" : "Bot account verified",
                        result.servers.isEmpty ? "Use the invite button, then check the connection again." : "Choose the server you want to transcribe.")
        }
    }
    private func inviteBot() {
        guard let connection, let url = URL(string: connection.inviteURL), url.scheme == "https", url.host == "discord.com" else { return }
        NSWorkspace.shared.open(url)
    }
    private func saveConnection() {
        guard connection != nil else { notice.show("Check your bot first", "Use Check connection to verify this bot token."); return }
        guard let guildId = UInt64(server.value), guildId > 0 else {
            notice.show("Choose a server", "Invite your bot, then check the connection again to refresh the server list."); return
        }
        perform(save) { [self] in
            var updates: [String: Any] = ["GUILD_ID": guildId, "LANGUAGE": language.value, "AUTO_CONNECT_BOT": autoConnect.isOn]
            let value = token.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
            if !value.isEmpty { updates["DISCORD_TOKEN"] = value }
            try await client.updateConfig(updates)
            token.stringValue = ""
            selectedServerId = String(guildId)
            navigate("models", nil)
        }
    }
}
