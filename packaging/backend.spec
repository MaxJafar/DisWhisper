# Build in an isolated Python 3.12 x64 environment; never collect developer data.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

root = Path(SPECPATH).parent
datas, binaries, hiddenimports = [], [], []
for package in ("sherpa_onnx", "vosk", "davey", "ctranslate2"):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
datas += collect_data_files("discord", includes=["bin/**"])
datas += collect_data_files("faster_whisper", includes=["assets/**"])
for distribution in ("faster-whisper", "huggingface-hub", "tokenizers", "discord.py", "discord-ext-voice-recv", "davey"):
    datas += copy_metadata(distribution)
hiddenimports += ["discord.ext.voice_recv", "nacl", "_cffi_backend"]

analysis = Analysis(
    [str(root / "packaging" / "backend_entry.py")],
    pathex=[str(root)],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
    excludes=["torch", "tensorflow", "transformers", "pytest", "ruff", "pip", "tkinter"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True,
    name="diswhisper-backend", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=True,
    icon=str(root / "companion/windows/DisWhisper.Companion/Assets/DisWhisper.ico"))
collect = COLLECT(exe, analysis.binaries, analysis.datas,
    strip=False, upx=False, name="diswhisper-backend")
