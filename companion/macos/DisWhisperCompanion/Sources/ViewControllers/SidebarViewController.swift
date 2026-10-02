import AppKit
import Combine

final class NavigationItem: NSObject {
    let title: String
    let route: String
    let symbol: String
    let children: [NavigationItem]
    init(_ title: String, route: String, symbol: String, children: [NavigationItem] = []) {
        self.title = title; self.route = route; self.symbol = symbol; self.children = children
    }
}

@MainActor
final class SidebarViewController: NSViewController, NSOutlineViewDataSource, NSOutlineViewDelegate {
    private let client: DisWhisperClient
    var onNavigate: ((String) -> Void)?
    private let outline = NSOutlineView()
    private let statusText = UI.label("Starting local service", size: 12, weight: .semibold)
    private let statusDot = UI.symbol("circle.fill", size: 7, color: Theme.orange)
    private var subscriptions = Set<AnyCancellable>()
    private var selecting = false
    private let items = [
        NavigationItem("Home", route: "home", symbol: "house"),
        NavigationItem("Models", route: "models", symbol: "cpu"),
        NavigationItem("Transcripts", route: "transcripts", symbol: "doc.text"),
        NavigationItem("", route: "separator", symbol: ""),
        NavigationItem("Connect Discord", route: "discord", symbol: "link"),
        NavigationItem("Extras", route: "extras", symbol: "sparkles", children: [
            NavigationItem("Meeting notes", route: "summaries", symbol: ""),
            NavigationItem("Cloud providers", route: "cloud", symbol: "")
        ])
    ]
    init(client: DisWhisperClient) { self.client = client; super.init(nibName: nil, bundle: nil) }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func loadView() {
        let material = NSVisualEffectView()
        material.blendingMode = .behindWindow
        material.material = .underWindowBackground
        material.state = .active
        view = material
        let tint = BackgroundView()
        tint.alphaValue = 0.92
        view.addSubview(tint); UI.pin(tint, to: view)
        let header = UI.stack([
            UI.eyebrow("YOUR WORKSPACE", color: Theme.tertiary),
            UI.label("Make room for the conversation.", size: 13, color: Theme.secondary)
        ], spacing: 7)
        view.addSubview(header)
        let column = NSTableColumn(identifier: .init("navigation"))
        outline.addTableColumn(column); outline.outlineTableColumn = column
        outline.headerView = nil; outline.backgroundColor = .clear
        outline.focusRingType = .none
        outline.rowHeight = 44; outline.intercellSpacing = NSSize(width: 0, height: 3)
        outline.indentationPerLevel = 18
        outline.dataSource = self; outline.delegate = self
        outline.setAccessibilityLabel("Workspace navigation")
        let scroll = NSScrollView()
        scroll.drawsBackground = false; scroll.documentView = outline
        scroll.hasVerticalScroller = true; scroll.scrollerStyle = .overlay
        scroll.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(scroll)
        let settings = ActionButton("Settings", style: .link) { [weak self] in self?.onNavigate?("settings") }
        let settingsRow = UI.stack([UI.symbol("gearshape", size: 18, color: Theme.secondary), settings, UI.spacer()], vertical: false, spacing: 12)
        let footer = CardView([
            UI.stack([statusDot, statusText], vertical: false, spacing: 7),
            UI.label("Free. Local. Yours.", size: 11, color: Theme.secondary),
            UI.link("View source ↗", address: "https://github.com/MaxJafar/DisWhisper")
        ], padding: 14, radius: 12)
        footer.content.spacing = 7
        view.addSubview(settingsRow); view.addSubview(footer)
        NSLayoutConstraint.activate([
            header.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 20),
            header.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -20),
            header.topAnchor.constraint(equalTo: view.topAnchor, constant: 26),
            scroll.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 22),
            scroll.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 8),
            scroll.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -8),
            scroll.bottomAnchor.constraint(equalTo: settingsRow.topAnchor, constant: -12),
            settingsRow.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 22),
            settingsRow.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -18),
            settingsRow.bottomAnchor.constraint(equalTo: footer.topAnchor, constant: -12),
            footer.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 12),
            footer.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -12),
            footer.bottomAnchor.constraint(equalTo: view.bottomAnchor, constant: -18)
        ])
        outline.reloadData()
        select("home")
        client.$status.sink { [weak self] status in
            self?.statusText.stringValue = self?.client.isDemo == true ? "Demo conversation" : status.sidebarText
            self?.statusDot.contentTintColor = ["online", "idle"].contains(status.status) ? Theme.green : Theme.orange
        }.store(in: &subscriptions)
    }
    func select(_ route: String) {
        guard isViewLoaded else { return }
        selecting = true
        defer { selecting = false }
        let item = items.flatMap { [$0] + $0.children }.first { $0.route == route }
        if ["summaries", "cloud"].contains(route), let extras = items.last { outline.expandItem(extras) }
        if let item, outline.row(forItem: item) >= 0 { outline.selectRowIndexes(IndexSet(integer: outline.row(forItem: item)), byExtendingSelection: false) }
        else { outline.deselectAll(nil) }
    }
    func outlineView(_ outlineView: NSOutlineView, numberOfChildrenOfItem item: Any?) -> Int { (item as? NavigationItem)?.children.count ?? items.count }
    func outlineView(_ outlineView: NSOutlineView, child index: Int, ofItem item: Any?) -> Any { (item as? NavigationItem)?.children[index] ?? items[index] }
    func outlineView(_ outlineView: NSOutlineView, isItemExpandable item: Any) -> Bool { !(item as! NavigationItem).children.isEmpty }
    func outlineView(_ outlineView: NSOutlineView, shouldSelectItem item: Any) -> Bool { (item as! NavigationItem).route != "separator" }
    func outlineView(_ outlineView: NSOutlineView, heightOfRowByItem item: Any) -> CGFloat { (item as! NavigationItem).route == "separator" ? 16 : 42 }
    func outlineView(_ outlineView: NSOutlineView, viewFor tableColumn: NSTableColumn?, item: Any) -> NSView? {
        let item = item as! NavigationItem
        if item.route == "separator" {
            let line = NSBox(); line.boxType = .separator; return line
        }
        var parts: [NSView] = []
        if !item.symbol.isEmpty { parts.append(UI.symbol(item.symbol, size: 18, color: Theme.secondary)) }
        parts += [UI.label(item.title, size: 13, wrap: false), UI.spacer()]
        let row = UI.stack(parts, vertical: false, spacing: 12)
        row.setAccessibilityLabel(item.title)
        return row
    }
    func outlineView(_ outlineView: NSOutlineView, rowViewForItem item: Any) -> NSTableRowView? { NavigationRowView() }
    func outlineViewSelectionDidChange(_ notification: Notification) {
        guard !selecting, let item = outline.item(atRow: outline.selectedRow) as? NavigationItem else { return }
        if item.route == "extras" { outline.expandItem(item) }
        onNavigate?(item.route == "extras" ? "summaries" : item.route)
    }
}

final class NavigationRowView: NSTableRowView {
    override func drawSelection(in dirtyRect: NSRect) {
        guard isSelected else { return }
        Theme.soft.setFill()
        NSBezierPath(roundedRect: bounds.insetBy(dx: 2, dy: 2), xRadius: 8, yRadius: 8).fill()
        Theme.brand.setFill()
        NSBezierPath(roundedRect: NSRect(x: 2, y: bounds.midY - 9, width: 3, height: 18), xRadius: 1.5, yRadius: 1.5).fill()
    }
    override var isEmphasized: Bool { get { false } set {} }
}
