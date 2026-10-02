# Matching native audio sources for DisWhisper 0.2.0 macOS

The macOS portable app uses the upstream PyAV 15.1.0 CPython 3.12 wheel for
the build architecture. Its `scripts/ffmpeg-7.1.json` pins the PyAV-Org/
pyav-ffmpeg **7.1.1-6** vendor release. That recipe uses FFmpeg 7.1.1 and
the codec source hashes recorded in vendor-sources.json. DisWhisper makes
no changes to those native sources. The upstream recipe includes patches
and its macOS workflow. The combined portable app is distributed under
GPL-3.0-or-later because the wheel includes x264/x265 and GPL audio codecs;
the project's original source and branding remain separately under 0BSD.

## Rebuild the native audio libraries

1. Extract `pyav-ffmpeg-7.1.1-6.tar.gz`. Consult its committed workflow for
   the macOS/Xcode build environment. Use the architecture matching the app.
2. Copy the archived dependencies into its `source/` directory, with the
   filenames from vendor-sources.json. The upstream script verifies their
   SHA-256 hashes, applies its patches, and builds the recorded versions.
3. Install the recipe's Python requirements, then run its
   `python scripts/build-ffmpeg.py /tmp/vendor --community` on macOS.
   For Ventura support, set MACOSX_DEPLOYMENT_TARGET=13.0 for compilation.
4. Extract PyAV-15.1.0.tar.gz, and build/repair a CPython 3.12 wheel using
   the matching `/tmp/vendor` libraries, following its macOS wheel workflow.
   Delocate copies dylibs and fixes their loader paths for redistribution.
5. Rebuild DisWhisper with that wheel and `scripts/build_macos.sh`.
   `scripts/audit_macos_bundle.py` checks every bundled Mach-O deployment
   target and rejects external library paths.

The frozen app keeps dynamic libraries under
`DisWhisper.app/Contents/Resources/backend/_internal/`, including the PyAV
codec dylibs. Compatible rebuilt libraries may replace them. Re-sign the
modified app locally with `codesign --force --deep --sign - DisWhisper.app`.
There is no DisWhisper restriction on modifications or reverse engineering
needed for those changes. Apple's system frameworks are not redistributed.

Python metadata/license files and the CPython license are included in the
application bundle. The davey source archive matches the same pinned
0.1.6 release used by the Windows build. Other native speech libraries
retain their MIT/Apache notices and public upstream source links. Speech
model weights and user data are not bundled.
