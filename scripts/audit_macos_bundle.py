"""Reject a release with newer-than-Ventura binaries or developer library paths."""

import argparse
import re
import subprocess
from pathlib import Path

MAGIC = {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


def audit(bundle: Path, minimum: tuple[int, int]) -> int:
    count = 0
    failures = []
    for path in bundle.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as stream:
            if stream.read(4) not in MAGIC:
                continue
        count += 1
        output = subprocess.run(["otool", "-l", str(path)], check=True, capture_output=True, text=True).stdout
        for block in output.split("Load command"):
            if "LC_BUILD_VERSION" not in block and "LC_VERSION_MIN_MACOSX" not in block:
                continue
            match = re.search(r"(?:minos|version)\s+(\d+)\.(\d+)", block)
            if match and tuple(map(int, match.groups())) > minimum:
                failures.append(f"{path.relative_to(bundle)} requires macOS {match[1]}.{match[2]}")
        libraries = subprocess.run(["otool", "-L", str(path)], check=True, capture_output=True, text=True).stdout
        for line in libraries.splitlines()[1:]:
            library = line.strip().split(" (", 1)[0]
            if library.startswith("/") and not library.startswith(("/usr/lib/", "/System/Library/")):
                failures.append(f"{path.relative_to(bundle)} links outside the bundle: {library}")
    if failures:
        raise SystemExit("macOS portability audit failed:\n" + "\n".join(sorted(set(failures))))
    print(f"Portability audit passed: {count} Mach-O files, macOS {minimum[0]}.{minimum[1]} or earlier, no external library paths.")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--minimum", default="13.0")
    args = parser.parse_args()
    audit(args.bundle.resolve(), tuple(map(int, args.minimum.split(".")[:2])))
