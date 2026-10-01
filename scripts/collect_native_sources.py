"""Collect pinned native-library notices and corresponding sources for redistribution."""
import argparse
import hashlib
import json
import ssl
import tarfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

import certifi

ROOT = Path(__file__).resolve().parents[1]


def fetch(component, cache):
    target = cache / component["filename"]
    expected = component["sha256"]
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
        return target
    temporary = target.with_suffix(target.suffix + ".part")
    for attempt in range(3):
        try:
            digest = hashlib.sha256()
            request = Request(component["url"], headers={"User-Agent": "DisWhisper-release-source/0.2"})
            context = ssl.create_default_context(cafile=certifi.where())
            with urlopen(request, timeout=45, context=context) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != expected:
                raise ValueError(f"Source checksum differs: {component['name']}")
            temporary.replace(target)
            print(f"Source verified: {component['name']}", flush=True)
            return target
        except (OSError, ValueError):
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("Download did not finish")


def notices(source):
    if source.name.endswith(".txt"):
        yield source.name, source.read_bytes()
        return
    with tarfile.open(source, "r:*") as archive:
        for entry in archive.getmembers():
            name = Path(entry.name).name.lower()
            if not entry.isfile() or entry.size > 256 * 1024:
                continue
            if not any(word in name for word in ("license", "copying", "notice", "patents")):
                continue
            if Path(name).suffix in {".c", ".h", ".py", ".rs", ".sh", ".cmake"}:
                continue
            stream = archive.extractfile(entry)
            if stream is not None:
                # Flatten paths; never extract untrusted archive paths into the filesystem.
                yield entry.name.replace("/", "_").replace("\\", "_").replace("..", "_"), stream.read()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("licenses", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    manifest_path = ROOT / "packaging/vendor-sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cache = ROOT / ".cache/vendor-sources"
    cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as executor:
        sources = list(executor.map(lambda item: fetch(item, cache), manifest["components"]))
    args.licenses.mkdir(parents=True, exist_ok=True)
    for component, source in zip(manifest["components"], sources, strict=True):
        folder = args.licenses / component["name"]
        folder.mkdir(exist_ok=True)
        for name, content in notices(source):
            (folder / name).write_bytes(content)
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    prefix = "DisWhisper-0.2.0-third-party-source/"
    with zipfile.ZipFile(args.archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for source in sources:
            output.write(source, prefix + "archives/" + source.name)
        output.write(manifest_path, prefix + "vendor-sources.json")
        output.write(ROOT / "THIRD_PARTY_NOTICES.md", prefix + "THIRD_PARTY_NOTICES.md")
        output.writestr(prefix + "BUILD.md", manifest["build_instructions"])
    checksum = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    args.archive.with_suffix(args.archive.suffix + ".sha256").write_text(f"{checksum}  {args.archive.name}\n", encoding="ascii")
    print(f"Native notices and matching source archive ready: {args.archive.name}")


if __name__ == "__main__":
    main()
