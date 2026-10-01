"""Create the portable archive without hidden settings, logs, or model caches."""
import sys
import zipfile
from pathlib import Path

source, target = map(Path, sys.argv[1:])
blocked = {".env", "config.json", "appearance.json", "backend.log"}
files = sorted(p for p in source.rglob("*") if p.is_file())
for file in files:
    relative = file.relative_to(source)
    runtime_folder = relative.parts[0] in {"models", "transcripts", ".cache", ".venv"}
    if file.name in blocked or runtime_folder:
        raise SystemExit(f"Private or runtime data cannot enter a release: {relative}")
with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for file in files:
        archive.write(file, str(Path(source.name) / file.relative_to(source)))
print(f"Archived {len(files)} files, {target.stat().st_size / 1024**2:.1f} MiB")
