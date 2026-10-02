"""Verify the complete release and its checksums before publishing anything."""
import argparse
import hashlib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    prefix = f"DisWhisper-{args.version}"
    packages = [f"{prefix}-windows-x64-setup.exe", f"{prefix}-windows-x64.zip", f"{prefix}-windows-third-party-source.zip"]
    for architecture in ("arm64", "x86_64"):
        packages.extend(f"{prefix}-macos-{architecture}{suffix}" for suffix in (".dmg", ".zip", "-third-party-source.zip"))
    expected = set(packages) | {name + ".sha256" for name in packages}
    actual = {path.name for path in args.folder.iterdir() if path.is_file()}
    if actual != expected:
        raise ValueError(f"Release asset inventory differs: missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}")
    for name in packages:
        fields = (args.folder / (name + ".sha256")).read_text(encoding="ascii").strip().split()
        if len(fields) != 2 or fields[1] != name:
            raise ValueError(f"Invalid checksum filename: {name}")
        with (args.folder / name).open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != fields[0]:
            raise ValueError(f"Release checksum differs: {name}")
        print(f"Verified: {name}")
    print(f"Complete release verified: {len(packages)} packages and {len(packages)} checksums.")


if __name__ == "__main__":
    main()
