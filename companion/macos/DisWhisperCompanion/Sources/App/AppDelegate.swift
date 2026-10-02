import AppKit

@main
enum DisWhisperCompanion {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.regular)
        withExtendedLifetime(delegate) { app.run() }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var client: DisWhisperClient!
    private var processManager: ProcessManager!
    private var windowController: MainWindowController!
    private var menuBar: MenuBarController!
    private var terminating = false
    func applicationDidFinishLaunching(_ notification: Notification) {
        let arguments = ProcessInfo.processInfo.arguments
        let preview = arguments.contains("--preview")
        let demo = arguments.contains("--demo")
        let theme = demo ? "dark" : UserDefaults.standard.string(forKey: "theme") ?? "system"
        NSApp.appearance = theme == "system" ? nil : NSAppearance(named: theme == "dark" ? .darkAqua : .aqua)
        client = DisWhisperClient(port: preview ? 8767 : 8765, demo: demo)
        processManager = ProcessManager(client: client, preview: preview)
        windowController = MainWindowController(client: client, processManager: processManager, preview: preview)
        menuBar = MenuBarController(client: client, window: windowController)
        installMenu()
        windowController.show()
        if let routeIndex = arguments.firstIndex(of: "--page"), arguments.indices.contains(routeIndex + 1) {
            windowController.split.navigate(arguments[routeIndex + 1])
        }
        client.start()
        Task { await processManager.ensureRunning() }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { windowController.show(); return true }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard !terminating else { return .terminateCancel }
        terminating = true
        Task {
            let stopped = await processManager.shutdown()
            if stopped { client.stop() }
            else {
                let alert = NSAlert()
                alert.messageText = "DisWhisper is still finishing"
                alert.informativeText = processManager.lastError
                alert.addButton(withTitle: "OK")
                windowController.show()
                alert.runModal()
            }
            terminating = false
            sender.reply(toApplicationShouldTerminate: stopped)
        }
        return .terminateLater
    }
    private func installMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem(); main.addItem(appItem)
        let appMenu = NSMenu(title: "DisWhisper")
        appMenu.addItem(withTitle: "About DisWhisper", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Hide DisWhisper", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit DisWhisper", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        let editItem = NSMenuItem(); main.addItem(editItem)
        let edit = NSMenu(title: "Edit")
        for (title, action, key) in [("Undo", Selector(("undo:")), "z"), ("Cut", #selector(NSText.cut(_:)), "x"), ("Copy", #selector(NSText.copy(_:)), "c"), ("Paste", #selector(NSText.paste(_:)), "v"), ("Select All", #selector(NSText.selectAll(_:)), "a")] {
            edit.addItem(withTitle: title, action: action, keyEquivalent: key)
        }
        editItem.submenu = edit
        let viewItem = NSMenuItem(); main.addItem(viewItem)
        let viewMenu = NSMenu(title: "View")
        for (index, title) in ["Home", "Models", "Transcripts", "Settings"].enumerated() {
            let item = NSMenuItem(title: title, action: #selector(shortcut(_:)), keyEquivalent: String(index + 1))
            item.tag = index; item.target = self; viewMenu.addItem(item)
        }
        viewMenu.addItem(.separator())
        let toggle = NSMenuItem(title: "Toggle Sidebar", action: #selector(NSSplitViewController.toggleSidebar(_:)), keyEquivalent: "s")
        toggle.keyEquivalentModifierMask = [.command, .control]
        toggle.target = windowController.split
        viewMenu.addItem(toggle); viewItem.submenu = viewMenu
        let windowItem = NSMenuItem(); main.addItem(windowItem)
        let windows = NSMenu(title: "Window")
        windows.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windows.addItem(withTitle: "Zoom", action: #selector(NSWindow.performZoom(_:)), keyEquivalent: "")
        windowItem.submenu = windows; NSApp.windowsMenu = windows
        NSApp.mainMenu = main
    }
    @objc private func shortcut(_ sender: NSMenuItem) {
        windowController.split.navigate(["home", "models", "transcripts", "settings"][sender.tag])
        windowController.show()
    }
}
