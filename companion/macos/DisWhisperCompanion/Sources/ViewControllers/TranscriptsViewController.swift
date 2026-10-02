import AppKit

@MainActor
final class TranscriptsViewController: PageViewController, NSTableViewDataSource, NSTableViewDelegate, NSSearchFieldDelegate {
    private let search = NSSearchField()
    private let table = NSTableView()
    private let previewTitle = UI.label("Your transcript library", size: 18, weight: .semibold)
    private let editor = TextEditor(height: 360)
    private var items: [TranscriptItem] = []
    private var filtered: [TranscriptItem] = []
    private var selected: TranscriptItem?
    private var directory = ""
    private var text = ""
    private var selectionVersion = 0
    private lazy var copy = ActionButton("Copy") { [weak self] in if let self { UI.copy(self.text) } }
    private lazy var open = ActionButton("Open file ↗") { [weak self] in self?.openFile() }
    private lazy var notes = ActionButton("Make meeting notes") { [weak self] in guard let self, let item = self.selected else { return }; self.navigate("summaries", item.filename) }
    private var panels: NSStackView!
    private var libraryPanel: CardView!
    private var previewPanel: CardView!
    private var fixedWidth: NSLayoutConstraint!
    private var narrowWidths: [NSLayoutConstraint] = []

    override func buildContent() {
        heading("Transcripts", "Every conversation, saved where you can find it.",
                action: ActionButton("Refresh") { [weak self] in Task { await self?.reload() } })
        search.placeholderString = "Find a meeting…"; search.delegate = self
        search.sendsSearchStringImmediately = true
        search.translatesAutoresizingMaskIntoConstraints = false
        search.heightAnchor.constraint(equalToConstant: 34).isActive = true
        let column = NSTableColumn(identifier: .init("meeting"))
        table.addTableColumn(column); table.headerView = nil
        table.backgroundColor = .clear; table.rowHeight = 62
        table.dataSource = self; table.delegate = self
        table.setAccessibilityLabel("Saved meetings")
        let list = NSScrollView()
        list.documentView = table; list.drawsBackground = false; list.hasVerticalScroller = true
        list.scrollerStyle = .overlay; list.translatesAutoresizingMaskIntoConstraints = false
        list.heightAnchor.constraint(equalToConstant: 390).isActive = true
        libraryPanel = CardView([
            search, list, ActionButton("Open transcript folder ↗") { [weak self] in self?.openFolder() }
        ], padding: 14)
        fixedWidth = libraryPanel.widthAnchor.constraint(equalToConstant: 280); fixedWidth.isActive = true
        copy.isEnabled = false; open.isEnabled = false; notes.isEnabled = false
        editor.show("A conversation worth keeping.\n\nStart a meeting with /join in Discord. Your transcript is saved automatically and will appear here.")
        editor.textView.setAccessibilityLabel("Transcript preview")
        previewPanel = CardView([previewTitle, UI.stack([copy, open, notes, UI.spacer()], vertical: false, spacing: 8), editor])
        panels = UI.stack([libraryPanel, previewPanel], vertical: false, spacing: 18)
        panels.alignment = .top
        add(panels)
        narrowWidths = [libraryPanel.widthAnchor.constraint(equalTo: panels.widthAnchor), previewPanel.widthAnchor.constraint(equalTo: panels.widthAnchor)]
    }
    override func viewDidLayout() {
        super.viewDidLayout()
        guard panels != nil else { return }
        let narrow = view.bounds.width < 820
        if (panels.orientation == .vertical) != narrow {
            NSLayoutConstraint.deactivate(narrowWidths); fixedWidth.isActive = !narrow
            panels.orientation = narrow ? .vertical : .horizontal
            panels.alignment = narrow ? .leading : .top
            if narrow { NSLayoutConstraint.activate(narrowWidths) }
        }
    }
    override func reload() async {
        do {
            let library = try await client.transcripts()
            items = library.items; directory = library.directory
            filter()
        } catch { notice.show("Couldn't load meetings", error.localizedDescription) }
    }
    func controlTextDidChange(_ obj: Notification) { filter() }
    private func filter() {
        let filename = selected?.filename
        filtered = items.filter { search.stringValue.isEmpty || ($0.filename + " " + $0.title).localizedCaseInsensitiveContains(search.stringValue) }
        table.reloadData()
        if let index = filtered.firstIndex(where: { $0.filename == filename }) { table.selectRowIndexes(IndexSet(integer: index), byExtendingSelection: false) }
        else { table.deselectAll(nil); clearSelection() }
    }
    func numberOfRows(in tableView: NSTableView) -> Int { filtered.count }
    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let item = filtered[row]
        return UI.stack([UI.label(item.title, size: 13, weight: .semibold), UI.label(item.caption, size: 11, color: Theme.secondary)], spacing: 5)
    }
    func tableView(_ tableView: NSTableView, rowViewForRow row: Int) -> NSTableRowView? { NavigationRowView() }
    func tableViewSelectionDidChange(_ notification: Notification) {
        guard filtered.indices.contains(table.selectedRow) else { clearSelection(); return }
        let item = filtered[table.selectedRow]
        selected = item; text = ""
        selectionVersion += 1
        let version = selectionVersion
        copy.isEnabled = false; open.isEnabled = false; notes.isEnabled = false
        previewTitle.stringValue = item.title
        editor.show("Loading transcript…")
        Task {
            do {
                let content = try await client.transcript(item.filename)
                guard version == selectionVersion else { return }
                text = content; editor.show(content, markdown: true)
                copy.isEnabled = true; notes.isEnabled = true
                open.isEnabled = FileManager.default.fileExists(atPath: item.path)
            } catch { if version == selectionVersion { notice.show("Couldn't open transcript", error.localizedDescription) } }
        }
    }
    private func clearSelection() {
        selectionVersion += 1; selected = nil; text = ""
        previewTitle.stringValue = "Your transcript library"
        copy.isEnabled = false; open.isEnabled = false; notes.isEnabled = false
        editor.show("A conversation worth keeping.\n\nStart a meeting with /join in Discord. Your transcript is saved automatically and will appear here.")
    }
    private func openFile() {
        guard let selected, selected.path.hasSuffix(".md"), FileManager.default.fileExists(atPath: selected.path) else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: selected.path))
    }
    private func openFolder() {
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: directory, isDirectory: &isDirectory), isDirectory.boolValue else {
            notice.show("Folder unavailable", client.isDemo ? "This is an in-memory demo transcript." : "Connect the local service and refresh the library."); return
        }
        NSWorkspace.shared.open(URL(fileURLWithPath: directory))
    }
}
