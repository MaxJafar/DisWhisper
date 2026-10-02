# macOS build verification

The Apple Silicon package was built and checked on macOS 26.6.2 with Xcode 26.5, using the portable Python 3.12 runtime and the pinned `requirements-macos.lock` dependencies.

| Check | Result |
| --- | --- |
| Python core and API tests | 93 passed |
| Swift IPC client tests | 7 passed |
| Python lint and AppKit release compilation | Passed |
| Deployment targets and native library paths | 122 Mach-O files audited; macOS 13.0 or earlier; no external library dependencies |
| Packaged service | Native speech/Opus imports, first-run status, model inventory, redacted settings, transcript listing, settings persistence, and orderly shutdown passed |
| Companion process manager | The real AppKit app started its bundled backend in the isolated preview profile; launch session and child process ID matched |
| Extracted ZIP | Ad-hoc signature verified; backend ran without Homebrew or Python on `PATH` |
| Local inference | Packaged Whisper tiny transcribed the synthetic English sample correctly with network access disabled |
| README app preview | Actual AppKit Home window capture with the clearly labelled demo conversation, below the branded cover |

The speech sample said: “This is a local transcription test. The Mac application saves clear meeting notes and keeps every conversation organized.” The packaged engine returned that text, language `en`, and device `cpu`. Test audio, model weights, and validation profiles are outside the release bundle.

These local checks cover Apple Silicon. The shared release workflow additionally builds on separate arm64 and Intel Mac runners, copies each app from its DMG, detaches the disk image, and checks the copied app's signature and backend startup/shutdown. Publication waits for both Mac builds and the Windows installer checks to pass.

The deployment audit checks binary compatibility requirements. Runtime testing on macOS 13, live Discord voice reception, and authenticated cloud-provider calls remain unverified. The packages have ad-hoc signatures and are not notarized. See [the quickstart](macos-quickstart.md) for installation, builds, and data storage.
