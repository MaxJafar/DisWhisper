#!/usr/bin/env swift
// Render the original SVG geometry as scalable macOS icon assets.
import AppKit
import Foundation

let root = URL(fileURLWithPath: CommandLine.arguments.dropFirst().first ?? FileManager.default.currentDirectoryPath)
let resources = root.appendingPathComponent("companion/macos/DisWhisperCompanion/Resources")
let assets = resources.appendingPathComponent("Assets.xcassets")
let icons = assets.appendingPathComponent("AppIcon.appiconset")
try FileManager.default.createDirectory(at: icons, withIntermediateDirectories: true)
try Data(#"{"info":{"author":"xcode","version":1}}"#.utf8).write(to: assets.appendingPathComponent("Contents.json"))

func render(_ pixels: Int) -> Data {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
                                  bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                  isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    let scale = CGFloat(pixels) / 256
    let transform = AffineTransform(scale: scale)
    let canvas = NSBezierPath(roundedRect: NSRect(x: 12 * scale, y: 12 * scale, width: 232 * scale, height: 232 * scale), xRadius: 50 * scale, yRadius: 50 * scale)
    NSColor(srgbRed: 0.13, green: 0.12, blue: 0.20, alpha: 1).setFill(); canvas.fill()
    let bubble = NSBezierPath()
    bubble.move(to: NSPoint(x: 76, y: 228)); bubble.line(to: NSPoint(x: 180, y: 228))
    bubble.curve(to: NSPoint(x: 228, y: 180), controlPoint1: NSPoint(x: 207, y: 228), controlPoint2: NSPoint(x: 228, y: 207))
    bubble.line(to: NSPoint(x: 228, y: 100))
    bubble.curve(to: NSPoint(x: 180, y: 52), controlPoint1: NSPoint(x: 228, y: 73), controlPoint2: NSPoint(x: 207, y: 52))
    bubble.line(to: NSPoint(x: 132, y: 52)); bubble.line(to: NSPoint(x: 84, y: 24))
    bubble.line(to: NSPoint(x: 84, y: 52)); bubble.line(to: NSPoint(x: 76, y: 52))
    bubble.curve(to: NSPoint(x: 28, y: 100), controlPoint1: NSPoint(x: 49, y: 52), controlPoint2: NSPoint(x: 28, y: 73))
    bubble.line(to: NSPoint(x: 28, y: 180))
    bubble.curve(to: NSPoint(x: 76, y: 228), controlPoint1: NSPoint(x: 28, y: 207), controlPoint2: NSPoint(x: 49, y: 228))
    bubble.close(); bubble.transform(using: transform)
    NSColor(srgbRed: 108.0 / 255, green: 92.0 / 255, blue: 231.0 / 255, alpha: 1).setFill(); bubble.fill()
    NSColor.white.setStroke()
    for (x, low, high) in [(74.0, 126.0, 154.0), (110, 100, 180), (146, 114, 166), (182, 130, 150)] {
        let bar = NSBezierPath(); bar.move(to: NSPoint(x: x * scale, y: low * scale)); bar.line(to: NSPoint(x: x * scale, y: high * scale))
        bar.lineWidth = 16 * scale; bar.lineCapStyle = .round; bar.stroke()
    }
    NSGraphicsContext.restoreGraphicsState()
    return bitmap.representation(using: .png, properties: [:])!
}
var images: [[String: String]] = []
for size in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let filename = "icon_\(size)x\(size)@\(scale)x.png"
        try render(size * scale).write(to: icons.appendingPathComponent(filename))
        images.append(["idiom": "mac", "size": "\(size)x\(size)", "scale": "\(scale)x", "filename": filename])
    }
}
let manifest: [String: Any] = ["images": images, "info": ["author": "xcode", "version": 1]]
try JSONSerialization.data(withJSONObject: manifest, options: [.prettyPrinted, .sortedKeys]).write(to: icons.appendingPathComponent("Contents.json"))
let logo = resources.appendingPathComponent("Logo.png")
if FileManager.default.fileExists(atPath: logo.path) { try FileManager.default.removeItem(at: logo) }
try FileManager.default.copyItem(at: root.appendingPathComponent("docs/brand/logo.png"), to: logo)
print("DisWhisper macOS icon assets rendered.")
