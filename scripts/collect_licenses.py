"""Preserve installed Python distributions' license files in a portable release."""
import argparse
import json
import shutil
from importlib.metadata import distributions
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    inventory = []
    for dist in sorted(distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        if name.lower() in {"diswhisper", "pip", "pytest", "ruff", "pyinstaller", "pyinstaller-hooks-contrib"}:
            continue
        folder = args.destination / f"{name}-{dist.version}"
        folder.mkdir(exist_ok=True)
        # Metadata retains author, upstream project, copyright, and license text.
        (folder / "METADATA.txt").write_text(dist.read_text("METADATA") or "", encoding="utf-8")
        saved = []
        for relative in dist.files or []:
            filename = str(relative)
            if not any(part in relative.name.lower() for part in ("license", "copying", "notice")):
                continue
            source = Path(dist.locate_file(relative))
            if source.is_file() and source.suffix.lower() not in {".py", ".pyc", ".pyd", ".dll"}:
                safe_name = filename.replace("\\", "_").replace("/", "_").replace("..", "_")
                shutil.copyfile(source, folder / safe_name)
                saved.append(safe_name)
        inventory.append({"name": name, "version": dist.version, "license": dist.metadata.get("License-Expression") or dist.metadata.get("License", ""), "files": saved})
    (args.destination / "inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
