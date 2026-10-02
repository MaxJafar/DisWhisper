import AppKit

@MainActor
final class MainWindowController: NSWindowController, NSWindowDelegate {
    let split: MainSplitViewController
    init(client: DisWhisperClient, processManager: ProcessManager, preview: Bool) {
        split = MainSplitViewController(client: client, processManager: processManager)
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1220, height: 820),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                              backing: .buffered, defer: false)
        window.title = "DisWhisper"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.backgroundColor = Theme.background
        window.isReleasedWhenClosed = false
        window.minSize = NSSize(width: 840, height: 660)
        window.center()
        super.init(window: window)
        window.delegate = self
        let root = BackgroundView()
        let rootController = NSViewController()
        rootController.view = root
        rootController.addChild(split)
        window.contentViewController = rootController
        let header = UI.stack([
            LogoView(size: 23), UI.label("DisWhisper", size: 13, weight: .semibold, wrap: false),
            UI.label("/", size: 13, color: Theme.tertiary, wrap: false),
            UI.label("Your conversations, written.", size: 12, color: Theme.secondary, wrap: false), UI.spacer()
        ], vertical: false, spacing: 9)
        if client.isDemo { header.addArrangedSubview(UI.eyebrow("DEMO", color: Theme.brandText)) }
        root.addSubview(header); root.addSubview(split.view)
        split.view.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            header.leadingAnchor.constraint(equalTo: root.leadingAnchor, constant: 94),
            header.trailingAnchor.constraint(equalTo: root.trailingAnchor, constant: -22),
            header.topAnchor.constraint(equalTo: root.topAnchor),
            header.heightAnchor.constraint(equalToConstant: 44),
            split.view.topAnchor.constraint(equalTo: header.bottomAnchor),
            split.view.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            split.view.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            split.view.bottomAnchor.constraint(equalTo: root.bottomAnchor)
        ])
        root.layoutSubtreeIfNeeded()
        split.splitView.setPosition(228, ofDividerAt: 0)
        window.setFrameAutosaveName(client.isDemo ? "DemoWindow" : preview ? "PreviewWindow" : "MainWindow")
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    func show() {
        showWindow(nil)
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool { sender.orderOut(nil); return false }
}
