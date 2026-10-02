"""Standalone backend entry point used by Windows and macOS portable releases."""
import os
import sys
from multiprocessing import freeze_support

# Frozen speech libraries can spawn Python resource/worker processes on macOS.
# Route those helpers before importing the CLI or loading native speech engines.
if __name__ == "__main__":
    freeze_support()

for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
# HTTP transfer callbacks make cancellation interruptible between chunks.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

# Bootstrap encoding and Hugging Face flags before importing the core.
from diswhisper.main import main  # noqa: E402

if __name__ == "__main__":
    if sys.argv[1:] == ["--check-native"]:
        import importlib

        import discord.opus

        from diswhisper.audio.opus import ensure_opus_loaded

        for provider in ("davey", "sherpa_onnx", "vosk"):
            importlib.import_module(provider)

        ensure_opus_loaded()
        decoder = discord.opus.Decoder()
        print("Native speech and Discord voice libraries loaded.")
        del decoder
    elif len(sys.argv) == 5 and sys.argv[1] == "--check-audio":
        # Release verification uses a synthetic sample and an already downloaded model.
        import json

        from faster_whisper import decode_audio

        from diswhisper.config import Config
        from diswhisper.transcriber.factory import create_stt_engine

        config = Config(WHISPER_MODEL_SIZE="tiny", LOCAL_MODEL_DIR=sys.argv[3], DEVICE="cpu", LANGUAGE=sys.argv[4])
        engine = create_stt_engine(config)
        text, language = engine.transcribe(decode_audio(sys.argv[2], sampling_rate=16000))
        print(json.dumps({"text": text, "language": language, "device": engine.active_device}, ensure_ascii=False))
        if not text:
            raise SystemExit("The packaged model produced no text for the verification sample.")
    else:
        main()
