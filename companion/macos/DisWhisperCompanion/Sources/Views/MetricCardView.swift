import AppKit

class CardView: NSView {
    let content: NSStackView
    private let color: NSColor
    private let bordered: Bool
    init(_ views: [NSView], color: NSColor = Theme.card, padding: CGFloat = 22, radius: CGFloat = 16, bordered: Bool = true) {
        content = UI.stack(views)
        self.color = color
        self.bordered = bordered
        super.init(frame: .zero)
        translatesAutoresizingMaskIntoConstraints = false
        wantsLayer = true
        layer?.cornerRadius = radius
        layer?.borderWidth = bordered ? 1 : 0
        addSubview(content)
        UI.pin(content, to: self, inset: padding)
        for view in views { UI.fillWidth(view, in: content) }
        updateColors()
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    override func viewDidChangeEffectiveAppearance() { super.viewDidChangeEffectiveAppearance(); updateColors() }
    private func updateColors() {
        effectiveAppearance.performAsCurrentDrawingAppearance {
            layer?.backgroundColor = color.resolvedCGColor
            layer?.borderColor = Theme.stroke.resolvedCGColor
        }
    }
}

final class MetricCardView: CardView {
    let value: NSTextField
    let detail: NSTextField
    init(title: String, value: String, detail: String) {
        self.value = UI.label(value, size: 21, weight: .semibold, wrap: false)
        self.detail = UI.label(detail, size: 12, color: Theme.secondary)
        super.init([UI.eyebrow(title), self.value, self.detail])
        content.spacing = 10
        heightAnchor.constraint(greaterThanOrEqualToConstant: 128).isActive = true
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
}

final class NoticeView: CardView {
    private let heading = UI.label("", size: 13, weight: .semibold, color: Theme.brandText)
    private let message = UI.label("", size: 12, color: Theme.secondary)
    init() {
        super.init([heading, message], color: Theme.soft, padding: 16, radius: 12, bordered: false)
        content.spacing = 5
        isHidden = true
        setAccessibilityRole(.group)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
    func show(_ title: String, _ text: String) {
        heading.stringValue = title
        message.stringValue = text
        isHidden = false
        setAccessibilityLabel(title + ". " + text)
    }
}

final class LogoView: NSView {
    override func draw(_ dirtyRect: NSRect) {
        Self.drawMark(in: bounds, monochrome: false)
    }
    static func menuBarImage() -> NSImage {
        let image = NSImage(size: NSSize(width: 18, height: 18), flipped: false) { bounds in
            drawMark(in: bounds, monochrome: true)
            return true
        }
        image.isTemplate = true
        return image
    }
    private static func drawMark(in bounds: NSRect, monochrome: Bool) {
        let scale = min(bounds.width, bounds.height) / 256
        let transform = AffineTransform(scale: scale)
        let bubble = NSBezierPath()
        bubble.move(to: NSPoint(x: 76, y: 228))
        bubble.line(to: NSPoint(x: 180, y: 228))
        bubble.curve(to: NSPoint(x: 228, y: 180), controlPoint1: NSPoint(x: 207, y: 228), controlPoint2: NSPoint(x: 228, y: 207))
        bubble.line(to: NSPoint(x: 228, y: 100))
        bubble.curve(to: NSPoint(x: 180, y: 52), controlPoint1: NSPoint(x: 228, y: 73), controlPoint2: NSPoint(x: 207, y: 52))
        bubble.line(to: NSPoint(x: 132, y: 52)); bubble.line(to: NSPoint(x: 84, y: 24))
        bubble.line(to: NSPoint(x: 84, y: 52)); bubble.line(to: NSPoint(x: 76, y: 52))
        bubble.curve(to: NSPoint(x: 28, y: 100), controlPoint1: NSPoint(x: 49, y: 52), controlPoint2: NSPoint(x: 28, y: 73))
        bubble.line(to: NSPoint(x: 28, y: 180))
        bubble.curve(to: NSPoint(x: 76, y: 228), controlPoint1: NSPoint(x: 28, y: 207), controlPoint2: NSPoint(x: 49, y: 228))
        bubble.close()
        let bars = [(74.0, 126.0, 154.0), (110.0, 100.0, 180.0), (146.0, 114.0, 166.0), (182.0, 130.0, 150.0)]
        if monochrome {
            // Template images use alpha: cut the waveform out of the speech bubble.
            bubble.windingRule = .evenOdd
            for (x, bottom, top) in bars {
                bubble.append(NSBezierPath(roundedRect: NSRect(x: x - 8, y: bottom - 8, width: 16, height: top - bottom + 16), xRadius: 8, yRadius: 8))
            }
        }
        bubble.transform(using: transform)
        (monochrome ? NSColor.black : Theme.brand).setFill(); bubble.fill()
        guard !monochrome else { return }
        NSColor.white.setStroke()
        for (x, bottom, top) in bars {
            let path = NSBezierPath()
            path.move(to: NSPoint(x: x * scale, y: bottom * scale))
            path.line(to: NSPoint(x: x * scale, y: top * scale))
            path.lineWidth = 16 * scale
            path.lineCapStyle = .round
            path.stroke()
        }
    }
    init(size: CGFloat) {
        super.init(frame: .zero)
        translatesAutoresizingMaskIntoConstraints = false
        widthAnchor.constraint(equalToConstant: size).isActive = true
        heightAnchor.constraint(equalToConstant: size).isActive = true
        setAccessibilityLabel("DisWhisper")
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }
}
