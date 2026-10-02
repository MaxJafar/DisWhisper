import AppKit
import Combine

@MainActor
final class MenuBarController: NSObject {
    private let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
    private let statusItem = NSMenuItem(title: "Starting local service", action: nil, keyEquivalent: "")
    private let finishItem = NSMenuItem(title: "Finish meeting", action: #selector(finish), keyEquivalent: "")
    private let client: DisWhisperClient
    private let window: MainWindowController
    private var subscriptions = Set<AnyCancellable>()
    init(client: DisWhisperClient, window: MainWindowController) {
        self.client = client; self.window = window
        super.init()
        item.button?.image = LogoView.menuBarImage()
        item.button?.imagePosition = .imageOnly
        item.button?.setAccessibilityLabel("DisWhisper")
        item.button?.toolTip = "DisWhisper"
        let menu = NSMenu()
        menu.addItem(statusItem); menu.addItem(.separator())
        let open = NSMenuItem(title: "Open DisWhisper", action: #selector(show), keyEquivalent: "")
        open.target = self; menu.addItem(open)
        finishItem.target = self; menu.addItem(finishItem)
        let notes = NSMenuItem(title: "Meeting notes", action: #selector(showNotes), keyEquivalent: "")
        notes.target = self; menu.addItem(notes); menu.addItem(.separator())
        let quit = NSMenuItem(title: "Quit DisWhisper", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        menu.addItem(quit)
        item.menu = menu
        client.$status.sink { [weak self] status in
            self?.statusItem.title = client.isDemo ? "Demo conversation" : status.sidebarText
            self?.finishItem.isEnabled = status.voiceConnected && !client.isDemo
            self?.item.button?.toolTip = "DisWhisper · \(status.sidebarText)"
        }.store(in: &subscriptions)
    }
    @objc private func show() { window.show() }
    @objc private func showNotes() { window.split.navigate("summaries"); window.show() }
    @objc private func finish() { Task { try? await client.control("meeting/finish") } }
}
