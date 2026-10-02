"""Check the frozen backend in a temporary profile, without a bot token/model."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def main():
    executable = Path(sys.argv[1]).resolve()
    # First-launch macOS code assessment can scan the complete native library bundle.
    subprocess.run([str(executable), "--check-native"], check=True, timeout=90)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="diswhisper-release-check-") as folder:
        root = Path(folder)
        (root / "config.json").write_text(json.dumps({"API_SERVER_PORT": port}), encoding="utf-8")
        environment = os.environ.copy()
        # A release test cannot inherit a developer's bot/cloud credentials.
        for key in ("DISCORD_TOKEN", "GUILD_ID", "GROQ_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "AUTO_CONNECT_BOT"):
            environment.pop(key, None)
        environment["HF_HOME"] = str(root / "cache")
        log = root / "service.log"
        with log.open("wb") as output:
            process = subprocess.Popen([str(executable), "--companion", "--data-dir", str(root), "--session-id", "release-smoke"], stdout=output, stderr=output, env=environment)
            base = f"http://127.0.0.1:{port}"
            def call(path, payload=None):
                request = Request(base + path, data=json.dumps(payload).encode() if payload is not None else None, headers={"Content-Type": "application/json"})
                with urlopen(request, timeout=5) as response:
                    return json.load(response)
            try:
                for _ in range(90):
                    if process.poll() is not None:
                        raise RuntimeError("Packaged service exited early:\n" + log.read_text(errors="replace"))
                    try:
                        status = call("/api/status")
                        break
                    except (URLError, TimeoutError):
                        time.sleep(0.5)
                else:
                    raise RuntimeError("Packaged service did not become ready.")
                assert status["status"] == "idle"
                assert status["managed"] and status["session_id"] == "release-smoke"
                assert not status["token_configured"] and not status["engine_loaded"]
                config = call("/api/config")
                assert "DISCORD_TOKEN" not in config and config["STT_ENGINE"] == "whisper"
                models = call("/api/models")["models"]
                assert any(model["id"] == "whisper-base" for model in models)
                assert not call("/api/transcripts")["transcripts"]
                call("/api/config", {"LANGUAGE": "ru"})
                assert call("/api/config")["LANGUAGE"] == "ru"
                call("/api/system/shutdown", {})
                process.wait(timeout=15)
                assert process.returncode == 0
                print("Frozen service passed: first run, model inventory, redacted config, settings, transcripts, orderly shutdown.")
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)


if __name__ == "__main__":
    main()
