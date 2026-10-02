# DisWhisper brand assets

The mark is a violet speech bubble containing four white audio bars. It connects the voice input and the written conversation without borrowing Discord's corporate mark.

Original brand assets are under 0BSD:

- `logo.svg`: editable full-color mark.
- `logo-mono.svg`: single-color cutout for small UI surfaces.
- `wordmark.svg`: mark and a system-font wordmark.
- `logo.png`: raster mark.
- `readme-cover.png`: 1774 × 887 branded README cover for Windows and macOS.
- `app-screenshot-macos.png`: a separate, actual window capture of the native macOS AppKit companion, using its explicitly labelled demo conversation.
- `Assets.xcassets` in the macOS companion contains native app icons rendered from the original mark's vector geometry by `scripts/generate_macos_assets.swift`.
- The Windows Assets folder contains the SVG and a multi-resolution ICO used by the executable, tray, and shortcuts.

Palette: violet **#6C5CE7**, light violet **#8C7CFF**, warm charcoal **#14151B**, mint **#39BFA0**. Preserve generous clear space around the mark and use a high-contrast solid background at small sizes. UI typography uses each platform's system font. Both companions share colors, spacing, page structure, and rounded card geometry.

## Updating the app screenshot

The separate app preview is captured from a running release build of **DisWhisper.app**. `--demo` displays sample text in the real AppKit views without contacting Discord, processing audio, or exposing credentials. The demo badge and README caption identify the sample conversation. To reproduce, build the Mac companion, open it with `--demo`, and capture its Home window at the default 1220 × 820-point size. Keep this screenshot as a separate image below the branded cover.
