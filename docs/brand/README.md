# DisWhisper brand

The mark is a violet speech bubble containing four white audio bars. It connects the voice input and the written conversation without borrowing Discord's corporate mark.

Original brand assets are under 0BSD:

- `logo.svg`: editable full-color mark.
- `logo-mono.svg`: single-color cutout for small UI surfaces.
- `wordmark.svg`: mark and a system-font wordmark.
- `logo.png`: raster mark.
- `readme-cover.png`: the original 1774 × 887 branded README artwork, updated to say “Windows + macOS”.
- `app-screenshot-macos.png`: a separate, actual window capture of the native macOS AppKit companion, using its explicitly labelled demo conversation.
- `Assets.xcassets` in the macOS companion contains native app icons rendered from the original mark's vector geometry by `scripts/generate_macos_assets.swift`.
- The Windows Assets folder contains the SVG and a multi-resolution ICO used by the executable, tray, and shortcuts.

Palette: violet **#6C5CE7**, light violet **#8C7CFF**, warm charcoal **#14151B**, mint **#39BFA0**. Preserve generous clear space around the mark and use a high-contrast solid background at small sizes. UI typography uses each platform's system font. Both companions share colors, spacing, page structure, and rounded card geometry.

## Artwork provenance

The original cover was generated using the built-in image generation tool with the original mark as its shape/palette reference. It retains the speech-bubble mark, wordmark, charcoal/violet background, and sculptural waveform turning into transcript lines. The SVG marks are editable source assets.

The platform-line edit also used the built-in tool. Its final prompt was:

> Use case: text-localization. Asset type: existing GitHub README cover, a very small text edit. Input image 1 is the EDIT TARGET, the original DisWhisper cover. Make exactly one change: replace the small bottom-left line 'Windows now. macOS next.' with the exact text 'Windows + macOS'. Match its original small font, muted violet-gray color, baseline, position, and spacing below 'Free · Local · Open source'. Preserve the entire rest of the original cover as faithfully and pixel-identically as possible: the speech-bubble audio mark, large DisWhisper wordmark, 'Your conversations, written.' tagline, mint benefit text, violet sculptural waveform flowing into transcript lines, charcoal background, curved glowing surfaces, composition, gradients, and the wide 2:1 aspect ratio. Do not redesign, recolor, move, crop, or add any elements. No app screenshot is to be added to this image: a real screenshot will be placed separately in the README. Exact platform text: 'Windows + macOS'.

## Screenshot provenance

The separate app preview is captured from a running release build of **DisWhisper.app**. `--demo` displays sample text in the real AppKit views without contacting Discord, processing audio, or exposing credentials. The demo badge and README caption identify the sample conversation. To reproduce, build the Mac companion, open it with `--demo`, and capture its Home window at the default 1220 × 820-point size. Keep this screenshot as a separate image below the branded cover.
