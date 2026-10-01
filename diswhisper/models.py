"""Shared companion model catalog, local availability checks, and downloads."""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Awaitable, Callable
from urllib.request import urlopen

import aiohttp

from diswhisper.config import Config


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    engine: str
    model_name: str
    category: str
    size_mb: int
    description: str
    languages: tuple[str, ...]
    repo_id: str = ""

    @property
    def downloadable(self) -> bool:
        return self.category != "cloud_stt"


CATALOG = [
    ModelSpec(
        "sensevoice",
        "Alibaba SenseVoice Small",
        "sensevoice",
        "SenseVoiceSmall-int8",
        "local_stt",
        240,
        "ONNX speech recognition with emotion and audio event tags.",
        ("English", "Chinese", "Cantonese", "Japanese", "Korean"),
    ),
]
for size, mb, repo, description in (
    (
        "tiny",
        75,
        "Systran/faster-whisper-tiny",
        "Smallest Whisper model; suitable for CPU use.",
    ),
    (
        "base",
        145,
        "Systran/faster-whisper-base",
        "Lightweight multilingual speech recognition.",
    ),
    ("small", 485, "Systran/faster-whisper-small", "Balances accuracy and memory use."),
    (
        "medium",
        1530,
        "Systran/faster-whisper-medium",
        "Higher accuracy with more memory use.",
    ),
    (
        "large-v3",
        3100,
        "Systran/faster-whisper-large-v3",
        "Full multilingual Whisper model.",
    ),
    (
        "large-v3-turbo",
        1620,
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "Faster large model with fewer decoder layers.",
    ),
    (
        "distil-large-v3",
        1520,
        "Systran/faster-distil-whisper-large-v3",
        "Distilled Whisper for English speech.",
    ),
):
    CATALOG.append(
        ModelSpec(
            f"whisper-{size}",
            f"Whisper {size}",
            "whisper",
            size,
            "local_stt",
            mb,
            description,
            ("English",) if size.startswith("distil") else ("Multilingual",),
            repo,
        )
    )

for model, language, mb in (
    ("vosk-model-small-en-us-0.15", "English", 40),
    ("vosk-model-small-ru-0.22", "Russian", 45),
    ("vosk-model-small-de-0.15", "German", 45),
    ("vosk-model-small-tr-0.3", "Turkish", 35),
):
    CATALOG.append(
        ModelSpec(
            model,
            f"Vosk Small — {language}",
            "vosk",
            model,
            "local_stt",
            mb,
            "Offline CPU speech recognition; no GPU required.",
            (language,),
        )
    )

for id_, model, mb, name in (
    ("ollama-llama3.2", "llama3.2:3b", 2000, "Llama 3.2 3B"),
    ("ollama-qwen2.5", "qwen2.5:3b", 1900, "Qwen 2.5 3B"),
    ("ollama-mistral", "mistral:7b", 4100, "Mistral 7B"),
):
    CATALOG.append(
        ModelSpec(
            id_,
            f"Ollama — {name}",
            "ollama",
            model,
            "local_llm",
            mb,
            "Private local meeting summaries. Requires Ollama to be running.",
            ("Multilingual",),
        )
    )

for provider in ("groq", "openai"):
    CATALOG.append(
        ModelSpec(
            f"cloud-{provider}",
            f"Cloud Whisper — {provider.title()}",
            provider,
            "whisper-large-v3-turbo" if provider == "groq" else "whisper-1",
            "cloud_stt",
            0,
            "Requires a configured API key.",
            ("Multilingual",),
        )
    )

_BY_ID = {model.id: model for model in CATALOG}
_ALIASES = {
    model.model_name: model.id for model in CATALOG if model.engine == "whisper"
}
_ALIASES["local-llm-ollama"] = "ollama-llama3.2"
VOSK_REQUIRED_FILES = ("am/final.mdl", "conf/mfcc.conf", "conf/model.conf")


def get_model(model_id: str) -> ModelSpec:
    if not isinstance(model_id, str):
        raise ValueError("model_id must be a string")
    key = model_id.strip().lower()
    try:
        return _BY_ID[_ALIASES.get(key, key)]
    except KeyError:
        raise ValueError(f"Unknown model: {key}") from None


def model_path(config: Config, model: ModelSpec) -> Path:
    return Path(config.LOCAL_MODEL_DIR) / model.engine / model.model_name


def _files_exist(directory: Path, filenames: tuple[str, ...]) -> bool:
    return all(
        (directory / filename).is_file() and (directory / filename).stat().st_size > 0
        for filename in filenames
    )


def _cached_files(repo: str, filenames: tuple[str, ...]) -> bool:
    from huggingface_hub import try_to_load_from_cache

    return all(
        isinstance(path := try_to_load_from_cache(repo, filename), str)
        and Path(path).is_file()
        for filename in filenames
    )


def is_downloaded(config: Config, model: ModelSpec) -> bool:
    if model.engine == "sensevoice":
        return _files_exist(
            Path.cwd(), ("model.int8.onnx", "tokens.txt")
        ) or _cached_files(
            config.SENSEVOICE_MODEL_ID, ("model.int8.onnx", "tokens.txt")
        )
    if model.engine == "whisper":
        files = ("model.bin", "config.json", "tokenizer.json")
        return _files_exist(model_path(config, model), files) or _cached_files(
            model.repo_id, files
        )
    if model.engine == "vosk":
        return _files_exist(model_path(config, model), VOSK_REQUIRED_FILES)
    if model.category == "cloud_stt":
        return bool(
            config.GROQ_API_KEY if model.engine == "groq" else config.OPENAI_API_KEY
        )
    return False


async def ollama_models(config: Config) -> tuple[bool, set[str]]:
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=2)
        ) as session:
            async with session.get(f"{config.LOCAL_LLM_URL}/api/tags") as response:
                response.raise_for_status()
                data = await response.json()
                return True, {model["name"] for model in data.get("models", [])}
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError):
        return False, set()


async def model_inventory(config: Config) -> list[dict]:
    available, installed = await ollama_models(config)

    def build_inventory() -> list[dict]:
        result = []
        for model in CATALOG:
            item = asdict(model)
            item.pop("repo_id")
            item["source_url"] = (
                "https://huggingface.co/" + (config.SENSEVOICE_MODEL_ID if model.engine == "sensevoice" else model.repo_id)
                if model.engine in ("sensevoice", "whisper") else
                "https://alphacephei.com/vosk/models" if model.engine == "vosk" else
                "https://ollama.com/library/" + model.model_name.split(":")[0] if model.engine == "ollama" else
                "https://console.groq.com/docs/speech-to-text" if model.engine == "groq" else
                "https://platform.openai.com/docs/guides/speech-to-text"
            )
            item["downloadable"] = model.downloadable
            item["downloaded"] = (
                model.model_name in installed
                if model.engine == "ollama"
                else is_downloaded(config, model)
            )
            item["available"] = available if model.engine == "ollama" else True
            item["active"] = (
                config.SUMMARIZER_PROVIDER == "local"
                and config.LOCAL_SUMMARIZER_MODEL == model.model_name
                if model.engine == "ollama"
                else (
                    config.STT_ENGINE in (model.engine, "cloud")
                    and config.CLOUD_STT_PROVIDER == model.engine
                )
                if model.category == "cloud_stt"
                else config.STT_ENGINE == model.engine
                and (
                    model.engine == "sensevoice"
                    or model.model_name
                    == (
                        config.WHISPER_MODEL_SIZE
                        if model.engine == "whisper"
                        else config.VOSK_MODEL_ID
                    )
                )
            )
            result.append(item)
        return result

    return await asyncio.to_thread(build_inventory)


def activation_updates(config: Config, model: ModelSpec) -> dict:
    if model.engine == "ollama":
        return {
            "SUMMARIZER_PROVIDER": "local",
            "LOCAL_SUMMARIZER_MODEL": model.model_name,
        }
    updates = {"STT_ENGINE": model.engine}
    if model.engine == "whisper":
        updates["WHISPER_MODEL_SIZE"] = model.model_name
    elif model.engine == "vosk":
        updates["VOSK_MODEL_ID"] = model.model_name
    elif model.category == "cloud_stt":
        updates["CLOUD_STT_PROVIDER"] = model.engine
    return updates


Progress = Callable[[int | None, str], Awaitable[None]]


def _extract_vosk(archive: Path, directory: Path, expected_name: str) -> Path:
    """Reject archives that could write outside their staging directory."""
    root = directory.resolve()
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            name = PurePosixPath(member.filename)
            target = (root / member.filename).resolve()
            if (
                not name.parts
                or name.parts[0] != expected_name
                or ".." in name.parts
                or "\\" in member.filename
                or not target.is_relative_to(root)
                or ((member.external_attr >> 16) & 0o170000) == 0o120000
            ):
                raise ValueError("Unsafe path in Vosk model archive")
        zipped.extractall(root)
    result = root / expected_name
    if not _files_exist(result, VOSK_REQUIRED_FILES):
        raise ValueError("Vosk archive is missing required model files")
    return result


def _download_vosk(
    config: Config,
    model: ModelSpec,
    progress: Callable[[int | None, str], None],
    cancelled: threading.Event,
) -> None:
    destination = model_path(config, model).resolve()
    if _files_exist(destination, VOSK_REQUIRED_FILES):
        return
    if destination.exists():
        raise ValueError(
            f"Incomplete model directory: {destination}. Move it aside and retry."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".vosk-", dir=destination.parent
    ) as staging:
        archive = Path(staging) / "model.zip"
        with urlopen(
            f"https://alphacephei.com/vosk/models/{model.model_name}.zip", timeout=30
        ) as response:
            total = int(response.headers.get("Content-Length", 0))
            completed = 0
            last_percent = -1
            with archive.open("wb") as file:
                while block := response.read(256 * 1024):
                    if cancelled.is_set():
                        raise RuntimeError("Vosk download cancelled")
                    file.write(block)
                    completed += len(block)
                    percent = min(99, completed * 100 // total) if total else None
                    if percent != last_percent:
                        progress(percent, "Downloading Vosk model")
                        last_percent = percent
        progress(None, "Validating and extracting Vosk model")
        extracted = _extract_vosk(archive, Path(staging), model.model_name)
        if cancelled.is_set():
            raise RuntimeError("Vosk download cancelled")
        extracted.rename(destination)


async def _download_huggingface(config: Config, model: ModelSpec, progress: Progress) -> None:
    """Publish file transfer progress and stop the worker before a cancelled retry."""
    from huggingface_hub import hf_hub_download, snapshot_download
    from tqdm import tqdm

    loop = asyncio.get_running_loop()
    cancelled = threading.Event()

    class CompanionProgress(tqdm):
        def __init__(self, *args, **kwargs):
            self.transferred = 0
            self.last_percent = None
            self.unit = kwargs.get("unit", "it")
            self.desc = kwargs.get("desc", "")
            kwargs["disable"] = True
            super().__init__(*args, **kwargs)

        def update(self, amount=1):
            if cancelled.is_set():
                raise RuntimeError("Model download cancelled")
            self.transferred += amount or 0
            if self.unit == "B" and self.total:
                percent = min(99, int(self.transferred * 100 / self.total))
                if percent != self.last_percent:
                    detail = f"Downloading {self.desc or 'model files'}"
                    future = asyncio.run_coroutine_threadsafe(progress(percent, detail), loop)
                    try:
                        future.result(timeout=5)
                    except TimeoutError:
                        future.cancel()
                        raise RuntimeError("Download progress listener stopped responding") from None
                    self.last_percent = percent
            return super().update(amount)

    def transfer():
        if model.engine == "sensevoice":
            for filename in ("model.int8.onnx", "tokens.txt"):
                if cancelled.is_set():
                    raise RuntimeError("Model download cancelled")
                hf_hub_download(repo_id=config.SENSEVOICE_MODEL_ID, filename=filename, token=False, tqdm_class=CompanionProgress)
        else:
            snapshot_download(
                model.repo_id, local_dir=str(model_path(config, model)),
                allow_patterns=["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"],
                token=False, max_workers=1, tqdm_class=CompanionProgress,
            )

    task = asyncio.create_task(asyncio.to_thread(transfer))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        cancelled.set()
        # Joining the worker avoids two downloads writing the same files on retry.
        await asyncio.gather(task, return_exceptions=True)
        raise


async def download_model(config: Config, model: ModelSpec, progress: Progress) -> None:
    if not model.downloadable:
        raise ValueError("Cloud providers do not have downloadable models")
    await progress(None, "Preparing download")
    if model.engine in ("sensevoice", "whisper"):
        await progress(None, "Downloading model files")
        await _download_huggingface(config, model, progress)
    elif model.engine == "vosk":
        loop = asyncio.get_running_loop()
        cancelled = threading.Event()

        def thread_progress(percent: int | None, detail: str) -> None:
            if cancelled.is_set() or loop.is_closed():
                raise RuntimeError("Vosk download cancelled")
            future = asyncio.run_coroutine_threadsafe(progress(percent, detail), loop)
            try:
                future.result(timeout=5)
            except TimeoutError:
                future.cancel()
                raise RuntimeError(
                    "Download progress listener stopped responding"
                ) from None

        try:
            await asyncio.to_thread(
                _download_vosk, config, model, thread_progress, cancelled
            )
        except asyncio.CancelledError:
            cancelled.set()
            raise
    elif model.engine == "ollama":
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=300)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{config.LOCAL_LLM_URL}/api/pull",
                json={"model": model.model_name, "stream": True},
            ) as response:
                response.raise_for_status()
                success = False
                last_update = None
                async for line in response.content:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise RuntimeError(data["error"])
                    detail = data.get("status", "Downloading Ollama model")
                    total = data.get("total", 0)
                    percent = (
                        min(99, int(data.get("completed", 0) * 100 / total))
                        if total
                        else None
                    )
                    update = (percent, detail)
                    if update != last_update:
                        await progress(percent, detail)
                        last_update = update
                    success = detail == "success"
                if not success:
                    raise RuntimeError("Ollama download ended before reporting success")
    if model.engine != "ollama" and not await asyncio.to_thread(
        is_downloaded, config, model
    ):
        raise RuntimeError("Download finished but required model files are missing")
    await progress(100, "Download complete")
