import AppKit

enum Theme {
    static let brand = NSColor(hex: 0x6C5CE7)
    static let green = NSColor(hex: 0x39BFA0)
    static let orange = NSColor(hex: 0xD98641)
    static let background = adaptive("background", dark: 0x14151B, light: 0xF6F5FA)
    static let card = adaptive("card", dark: 0x21222B, light: 0xFFFFFF)
    static let stroke = adaptive("stroke", dark: 0x34353F, light: 0xE6E3EE)
    static let soft = adaptive("soft", dark: 0x29243E, light: 0xF0EDFC)
    static let hero = adaptive("hero", dark: 0x2D264B, light: 0xECE7FF)
    static let heroText = adaptive("heroText", dark: 0xF3F0FF, light: 0x30244D)
    static let brandText = adaptive("brandText", dark: 0xBDB2FF, light: 0x5947C6)
    static let text = adaptive("text", dark: 0xF3F1F7, light: 0x24232C)
    static let secondary = adaptive("secondary", dark: 0xB1AFBD, light: 0x696576)
    static let tertiary = adaptive("tertiary", dark: 0x85818F, light: 0x7D778B)
    static let quiet = adaptive("quiet", dark: 0x2C2D37, light: 0xF8F7FB)

    private static func adaptive(_ name: String, dark: UInt32, light: UInt32) -> NSColor {
        NSColor(name: NSColor.Name("DisWhisper.\(name)")) { appearance in
            NSColor(hex: appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua ? dark : light)
        }
    }
}

extension NSColor {
    convenience init(hex: UInt32) {
        self.init(srgbRed: Double((hex >> 16) & 255) / 255,
                  green: Double((hex >> 8) & 255) / 255,
                  blue: Double(hex & 255) / 255, alpha: 1)
    }
    var resolvedCGColor: CGColor { usingColorSpace(.deviceRGB)?.cgColor ?? cgColor }
}

final class BackgroundView: NSView {
    override var isFlipped: Bool { true }
    override func draw(_ dirtyRect: NSRect) { Theme.background.setFill(); bounds.fill() }
    override func viewDidChangeEffectiveAppearance() { super.viewDidChangeEffectiveAppearance(); needsDisplay = true }
}

@MainActor
enum UI {
    static func label(_ text: String, size: CGFloat = 14, weight: NSFont.Weight = .regular,
                      color: NSColor = Theme.text, wrap: Bool = true) -> NSTextField {
        let field = NSTextField(labelWithString: text)
        field.font = .systemFont(ofSize: size, weight: weight)
        field.textColor = color
        field.maximumNumberOfLines = wrap ? 0 : 1
        field.lineBreakMode = wrap ? .byWordWrapping : .byTruncatingTail
        field.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        field.translatesAutoresizingMaskIntoConstraints = false
        return field
    }
    static func eyebrow(_ text: String, color: NSColor = Theme.secondary) -> NSTextField {
        let field = label(text, size: 10, weight: .semibold, color: color, wrap: false)
        field.attributedStringValue = NSAttributedString(string: text, attributes: [
            .font: NSFont.systemFont(ofSize: 10, weight: .semibold), .foregroundColor: color, .kern: 1
        ])
        return field
    }
    static func stack(_ views: [NSView] = [], vertical: Bool = true, spacing: CGFloat = 14) -> NSStackView {
        let stack = NSStackView(views: views)
        stack.orientation = vertical ? .vertical : .horizontal
        stack.alignment = vertical ? .leading : .centerY
        stack.spacing = spacing
        stack.distribution = vertical ? .gravityAreas : .fill
        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.detachesHiddenViews = true
        return stack
    }
    static func fillWidth(_ child: NSView, in stack: NSStackView) {
        child.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
    }
    static func spacer() -> NSView {
        let view = NSView()
        view.translatesAutoresizingMaskIntoConstraints = false
        view.setContentHuggingPriority(.defaultLow, for: .horizontal)
        view.setContentHuggingPriority(.defaultLow, for: .vertical)
        return view
    }
    static func pin(_ child: NSView, to parent: NSView, inset: CGFloat = 0) {
        child.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            child.leadingAnchor.constraint(equalTo: parent.leadingAnchor, constant: inset),
            child.trailingAnchor.constraint(equalTo: parent.trailingAnchor, constant: -inset),
            child.topAnchor.constraint(equalTo: parent.topAnchor, constant: inset),
            child.bottomAnchor.constraint(equalTo: parent.bottomAnchor, constant: -inset)
        ])
    }
    static func symbol(_ name: String, size: CGFloat = 20, color: NSColor = Theme.brandText) -> NSImageView {
        let image = NSImageView()
        image.image = NSImage(systemSymbolName: name, accessibilityDescription: nil)?
            .withSymbolConfiguration(.init(pointSize: size, weight: .regular))
        image.contentTintColor = color
        image.translatesAutoresizingMaskIntoConstraints = false
        image.widthAnchor.constraint(equalToConstant: size + 4).isActive = true
        image.heightAnchor.constraint(equalToConstant: size + 4).isActive = true
        return image
    }
    static func field(_ placeholder: String = "", secure: Bool = false) -> NSTextField {
        let field: NSTextField = secure ? NSSecureTextField() : NSTextField()
        field.placeholderString = placeholder
        field.font = .systemFont(ofSize: 14)
        field.bezelStyle = .roundedBezel
        field.textColor = Theme.text
        field.translatesAutoresizingMaskIntoConstraints = false
        field.heightAnchor.constraint(equalToConstant: 36).isActive = true
        return field
    }
    static func formRow(_ title: String, control: NSView) -> NSStackView {
        let row = stack([label(title, size: 13), control], spacing: 7)
        fillWidth(control, in: row)
        return row
    }
    static func check(_ title: String, on: Bool = false, action: (() -> Void)? = nil) -> ClosureCheckBox {
        ClosureCheckBox(title, on: on, action: action)
    }
    static func link(_ title: String, address: String) -> ActionButton {
        ActionButton(title, style: .link) { open(address) }
    }
    static func open(_ address: String) {
        guard let url = URL(string: address), url.scheme == "https" else { return }
        NSWorkspace.shared.open(url)
    }
    static func copy(_ text: String) {
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }
    static var motionEnabled: Bool {
        (UserDefaults.standard.object(forKey: "motionEnabled") as? Bool ?? true)
            && !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }
}

enum ActionStyle { case primary, quiet, link }

final class ActionButton: NSButton {
    private let handler: () -> Void
    private let actionStyle: ActionStyle
    init(_ title: String, style: ActionStyle = .quiet, action: @escaping () -> Void) {
        handler = action
        actionStyle = style
        super.init(frame: .zero)
        self.title = title
        alignment = style == .link ? .left : .center
        font = .systemFont(ofSize: style == .link ? 12 : 13, weight: style == .primary ? .semibold : .regular)
        bezelStyle = .rounded
        isBordered = false
        wantsLayer = true
        layer?.cornerRadius = style == .link ? 0 : 9
        layer?.borderWidth = style == .quiet ? 1 : 0
        translatesAutoresizingMaskIntoConstraints = false
        heightAnchor.constraint(equalToConstant: style == .link ? 24 : 40).isActive = true
        let minimum = widthAnchor.constraint(greaterThanOrEqualToConstant: intrinsicContentSize.width + (style == .link ? 0 : 26))
        minimum.priority = .defaultHigh
        minimum.isActive = true
        target = self; self.action = #selector(performAction)
        setAccessibilityLabel(title)
        updateColors()
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    @objc private func performAction() { handler() }
    override var title: String { didSet { if layer != nil { updateColors(); setAccessibilityLabel(title) } } }
    override var isEnabled: Bool { didSet { alphaValue = isEnabled ? 1 : 0.45 } }
    override func viewDidChangeEffectiveAppearance() { super.viewDidChangeEffectiveAppearance(); updateColors() }
    private func updateColors() {
        effectiveAppearance.performAsCurrentDrawingAppearance {
            layer?.backgroundColor = (actionStyle == .primary ? Theme.brand : actionStyle == .quiet ? Theme.quiet : .clear).resolvedCGColor
            layer?.borderColor = Theme.stroke.resolvedCGColor
            attributedTitle = NSAttributedString(string: title, attributes: [
                .font: font ?? NSFont.systemFont(ofSize: 13),
                .foregroundColor: actionStyle == .primary ? NSColor.white : actionStyle == .link ? Theme.brandText : Theme.text
            ])
        }
    }
}

final class ClosureCheckBox: NSButton {
    private let handler: (() -> Void)?
    init(_ title: String, on: Bool, action: (() -> Void)?) {
        handler = action
        super.init(frame: .zero)
        setButtonType(.switch)
        self.title = title
        font = .systemFont(ofSize: 13)
        state = on ? .on : .off
        target = self; self.action = #selector(changed)
        translatesAutoresizingMaskIntoConstraints = false
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    @objc private func changed() { handler?() }
    var isOn: Bool { get { state == .on } set { state = newValue ? .on : .off } }
}

final class OptionPicker: NSPopUpButton {
    var onChange: (() -> Void)?
    init(_ options: [(String, String)]) {
        super.init(frame: .zero, pullsDown: false)
        font = .systemFont(ofSize: 13)
        for (title, value) in options { addItem(withTitle: title); lastItem?.representedObject = value }
        target = self; action = #selector(changed)
        translatesAutoresizingMaskIntoConstraints = false
        heightAnchor.constraint(equalToConstant: 34).isActive = true
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    @objc private func changed() { onChange?() }
    var value: String {
        get { selectedItem?.representedObject as? String ?? "" }
        set { if let item = itemArray.first(where: { $0.representedObject as? String == newValue }) { select(item) } }
    }
}

final class TextEditor: NSScrollView {
    let textView = NSTextView()
    init(height: CGFloat = 300) {
        super.init(frame: .zero)
        drawsBackground = false
        hasVerticalScroller = true
        scrollerStyle = .overlay
        textView.isEditable = false
        textView.isSelectable = true
        textView.isRichText = true
        textView.drawsBackground = false
        textView.font = .systemFont(ofSize: 14)
        textView.textColor = Theme.text
        textView.textContainerInset = NSSize(width: 2, height: 10)
        textView.isHorizontallyResizable = false
        textView.isVerticallyResizable = true
        textView.autoresizingMask = [.width]
        textView.textContainer?.widthTracksTextView = true
        documentView = textView
        translatesAutoresizingMaskIntoConstraints = false
        heightAnchor.constraint(equalToConstant: height).isActive = true
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    func show(_ text: String, markdown: Bool = false) {
        let result = NSMutableAttributedString(string: "")
        for line in text.components(separatedBy: "\n") {
            let heading = line.hasPrefix("#")
            let clean = heading ? line.drop(while: { $0 == "#" || $0 == " " }).description : line.replacingOccurrences(of: "**", with: "")
            let paragraph = NSMutableParagraphStyle()
            paragraph.paragraphSpacing = 9
            paragraph.lineSpacing = 3
            let attributes: [NSAttributedString.Key: Any] = [
                .font: NSFont.systemFont(ofSize: heading && markdown ? (line.hasPrefix("# ") ? 21 : 16) : 14,
                                         weight: heading && markdown ? .semibold : .regular),
                .foregroundColor: Theme.text, .paragraphStyle: paragraph
            ]
            let part = NSMutableAttributedString(string: (markdown ? clean : line) + "\n", attributes: attributes)
            if markdown, line.hasPrefix("**"), let colon = clean.firstIndex(of: ":") {
                let count = clean.distance(from: clean.startIndex, to: colon) + 1
                part.addAttributes([.font: NSFont.systemFont(ofSize: 14, weight: .semibold), .foregroundColor: Theme.brandText],
                                   range: NSRange(location: 0, length: (clean.prefix(count) as NSString).length))
            }
            result.append(part)
        }
        textView.textStorage?.setAttributedString(result)
        textView.scrollToBeginningOfDocument(nil)
    }
}
