// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "DisWhisperCompanion",
    platforms: [.macOS(.v13)],
    products: [.executable(name: "DisWhisperCompanion", targets: ["DisWhisperCompanion"])],
    targets: [
        .executableTarget(name: "DisWhisperCompanion", path: "Sources"),
        .testTarget(name: "DisWhisperCompanionTests", dependencies: ["DisWhisperCompanion"], path: "Tests")
    ]
)
