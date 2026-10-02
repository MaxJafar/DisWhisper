# Third-party software and models

The 0BSD license applies to DisWhisper's original code and branding. It does not replace the licenses of dependencies, Windows components, or downloaded models. Keep their required notices when redistributing a build.

Windows portable releases contain a `licenses/` directory with Python distribution metadata/license files, native audio library notices, and available .NET/NuGet notices. The pinned release dependency list is in `requirements-windows.lock`. PyInstaller's bootloader has its own license and distribution exception.

The Windows package includes FFmpeg 8.0.1 shared libraries from PyAV 16.1.0, including the GPL-licensed x264 and x265 libraries. The combined portable application is therefore distributed under **GPL-3.0-or-later**; its original source and branding remain separately available under 0BSD. The wheel's FFmpeg license-query string alone does not describe the licenses of its external codecs. There is no proprietary DisWhisper EULA or restriction on modifying or replacing these libraries.

The [same release page](https://github.com/MaxJafar/DisWhisper/releases) provides `DisWhisper-0.2.0-third-party-source.zip`: matching source archives, upstream build scripts and patches, checksums, and the FFmpeg configure line. DisWhisper's own corresponding source is the release's tagged GitHub source archive. Native libraries are separate DLLs in `backend/_internal/av.libs`, so rebuilt compatible DLLs can replace them. See `packaging/vendor-sources.json` for exact upstream sources and versions. Keep the source download and notices available when redistributing the binaries.

macOS portable builds keep their notices in `DisWhisper.app/Contents/Resources/licenses/`. Their pinned runtime is in `requirements-macos.lock`, and their native audio manifest is `packaging/vendor-sources-macos.json`. For Ventura compatibility the Mac package uses PyAV 15.1.0 with FFmpeg 7.1.1 from the upstream 7.1.1-6 vendor recipe. Its x264/x265 and audio codecs also make the combined portable Mac application **GPL-3.0-or-later**, while original DisWhisper source remains 0BSD. `scripts/build_macos.sh` produces `DisWhisper-0.2.0-macos-third-party-source.zip` with matching archives, hashes, and rebuild instructions. Publish that source archive alongside any Mac binary release. Compatible rebuilt dylibs can replace the libraries under `Contents/Resources/backend/_internal/`; re-sign a modified bundle locally as described in the source archive. Apple system frameworks and system fonts are not bundled.

Principal components include:

| Component | Upstream license/source |
|---|---|
| Python | [Python license](https://docs.python.org/3/license.html) |
| discord.py | [MIT](https://github.com/Rapptz/discord.py/blob/master/LICENSE) |
| discord-ext-voice-recv | [MIT](https://github.com/imayhaveborkedit/discord-ext-voice-recv/blob/main/LICENSE) |
| davey | [MIT](https://github.com/Snazzah/davey/blob/master/LICENSE) |
| faster-whisper | [MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) |
| CTranslate2 | [MIT](https://github.com/OpenNMT/CTranslate2/blob/master/LICENSE) |
| sherpa-onnx | [Apache-2.0](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE) |
| Vosk | [Apache-2.0](https://github.com/alphacep/vosk-api/blob/master/COPYING) |
| PyAV and bundled FFmpeg | [PyAV BSD notices](https://github.com/PyAV-Org/PyAV/blob/main/LICENSE.txt), [FFmpeg license details](https://ffmpeg.org/legal.html); GPL-3.0-or-later for this combined codec build; license texts and corresponding source accompany the release |
| Windows App SDK / WinUI / .NET / Community Toolkit | Notices in the package's `licenses/dotnet` directory and their upstream Microsoft repositories |

Speech model weights are downloaded from upstream and are not bundled:

- Whisper weights/conversions: [OpenAI Whisper](https://github.com/openai/whisper/blob/main/LICENSE), [Systran model cards](https://huggingface.co/Systran).
- SenseVoice: [model repository and card](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17).
- Vosk: [official model catalog and per-model licenses](https://alphacephei.com/vosk/models).
- Ollama models: each model has its own license; follow the source link on its card before downloading or redistributing weights.

Discord, Groq, OpenAI, Hugging Face, and other optional services have their own usage terms. DisWhisper does not grant rights to their names or logos. The wordmark uses system fonts at rendering time; those fonts are not redistributed.
