import AppKit
import Combine

@MainActor
class PageViewController: NSViewController {
    let client: DisWhisperClient
    let processManager: ProcessManager
    let navigate: (String, String?) -> Void
    let content = UI.stack(spacing: 22)
    let notice = NoticeView()
    var subscriptions = Set<AnyCancellable>()
    private(set) var busy = false
    private let activity = NSProgressIndicator()

    init(client: DisWhisperClient, processManager: ProcessManager, navigate: @escaping (String, String?) -> Void) {
        self.client = client; self.processManager = processManager; self.navigate = navigate
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func loadView() {
        view = BackgroundView()
        let scroll = NSScrollView()
        scroll.drawsBackground = false
        scroll.hasVerticalScroller = true
        scroll.scrollerStyle = .overlay
        let document = FlippedDocumentView()
        document.translatesAutoresizingMaskIntoConstraints = false
        scroll.documentView = document
        view.addSubview(scroll); UI.pin(scroll, to: view)
        document.addSubview(content)
        NSLayoutConstraint.activate([
            document.widthAnchor.constraint(equalTo: scroll.contentView.widthAnchor),
            content.leadingAnchor.constraint(equalTo: document.leadingAnchor, constant: 28),
            content.trailingAnchor.constraint(equalTo: document.trailingAnchor, constant: -28),
            content.topAnchor.constraint(equalTo: document.topAnchor, constant: 20),
            content.bottomAnchor.constraint(equalTo: document.bottomAnchor, constant: -28)
        ])
        buildContent()
    }
    override func viewDidAppear() { super.viewDidAppear(); Task { await reload() } }
    func buildContent() {}
    func reload() async {}
    func add(_ child: NSView) { content.addArrangedSubview(child); UI.fillWidth(child, in: content) }
    func heading(_ title: String, _ description: String, action: NSView? = nil) {
        let text = UI.stack([UI.label(title, size: 30, weight: .semibold), UI.label(description, color: Theme.secondary)], spacing: 5)
        activity.style = .spinning
        activity.controlSize = .small
        activity.isDisplayedWhenStopped = false
        activity.translatesAutoresizingMaskIntoConstraints = false
        activity.widthAnchor.constraint(equalToConstant: 20).isActive = true
        activity.heightAnchor.constraint(equalToConstant: 20).isActive = true
        activity.setAccessibilityLabel("Working")
        var children = [text, UI.spacer(), activity]
        if let action { children.append(action) }
        add(UI.stack(children, vertical: false, spacing: 18))
        add(notice)
    }
    func perform(_ button: NSButton? = nil, success: (String, String)? = nil, operation: @escaping () async throws -> Void) {
        guard !busy else { return }
        busy = true; button?.isEnabled = false; notice.isHidden = true
        activity.startAnimation(nil)
        Task {
            defer { busy = false; button?.isEnabled = true; activity.stopAnimation(nil) }
            do {
                try await operation()
                if let success { notice.show(success.0, success.1) }
            } catch { notice.show("One more step", error.localizedDescription) }
        }
    }
}

final class FlippedDocumentView: NSView { override var isFlipped: Bool { true } }
