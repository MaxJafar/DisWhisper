import AppKit

@MainActor
final class MainSplitViewController: NSSplitViewController {
    private let client: DisWhisperClient
    private let processManager: ProcessManager
    private let sidebar: SidebarViewController
    private let container = NSViewController()
    private var pages: [String: PageViewController] = [:]
    private var current: PageViewController?

    init(client: DisWhisperClient, processManager: ProcessManager) {
        self.client = client; self.processManager = processManager
        sidebar = SidebarViewController(client: client)
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func viewDidLoad() {
        super.viewDidLoad()
        splitView.isVertical = true
        splitView.dividerStyle = .thin
        let sidebarItem = NSSplitViewItem(sidebarWithViewController: sidebar)
        sidebarItem.minimumThickness = 210
        sidebarItem.maximumThickness = 260
        sidebarItem.canCollapse = true
        addSplitViewItem(sidebarItem)
        container.view = BackgroundView()
        let contentItem = NSSplitViewItem(viewController: container)
        contentItem.minimumThickness = 560
        addSplitViewItem(contentItem)
        sidebar.onNavigate = { [weak self] route in self?.navigate(route) }
        splitView.setPosition(228, ofDividerAt: 0)
        navigate("home")
    }
    func navigate(_ route: String, filename: String? = nil) {
        guard isViewLoaded else { _ = view; navigate(route, filename: filename); return }
        let key = route == "extras" ? "summaries" : route
        sidebar.select(key)
        let callback: (String, String?) -> Void = { [weak self] route, filename in self?.navigate(route, filename: filename) }
        let page: PageViewController
        if let cached = pages[key] { page = cached }
        else {
            switch key {
            case "models": page = ModelsViewController(client: client, processManager: processManager, navigate: callback)
            case "transcripts": page = TranscriptsViewController(client: client, processManager: processManager, navigate: callback)
            case "discord": page = DiscordSetupViewController(client: client, processManager: processManager, navigate: callback)
            case "cloud": page = CloudViewController(client: client, processManager: processManager, navigate: callback)
            case "summaries": page = SummariesViewController(client: client, processManager: processManager, navigate: callback)
            case "settings": page = SettingsViewController(client: client, processManager: processManager, navigate: callback)
            default: page = DashboardViewController(client: client, processManager: processManager, navigate: callback)
            }
            pages[key] = page
        }
        if let notes = page as? SummariesViewController, let filename { notes.preselectedFilename = filename }
        if current === page { if filename != nil { Task { await page.reload() } }; return }
        current?.view.removeFromSuperview(); current?.removeFromParent()
        container.addChild(page)
        container.view.addSubview(page.view); UI.pin(page.view, to: container.view)
        current = page
        if UI.motionEnabled && !client.isDemo {
            page.view.alphaValue = 0
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.16
                page.view.animator().alphaValue = 1
            }
        }
    }
}
