"""Fail publication if runtime data or credentials appear in source or Git history."""
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values


def git(*args, data=None):
    return subprocess.run(["git", *args], input=data, check=True, stdout=subprocess.PIPE).stdout


def main():
    candidates = git("ls-files", "-co", "--exclude-standard", "-z").decode().split("\0")
    known = []
    for value in dotenv_values(".env").values():
        if value and len(value) >= 20:
            known.append(value.encode())
    patterns = [
        rb"[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{25,}",
        rb"gh[pousr]_[A-Za-z0-9]{30,}",
        rb"sk-(?:proj-)?[A-Za-z0-9_-]{32,}",
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
    def secret(data):
        return any(value in data for value in known) or any(re.search(pattern, data) for pattern in patterns)
    problems = []
    for name in candidates:
        if not name:
            continue
        path = Path(name)
        if path.name in {".env", "config.json"} or path.parts[0] in {"transcripts", "models", ".cache", ".venv", "dist"} and path.name != ".gitkeep":
            problems.append("Private/runtime file: " + name)
        if path.is_file() and secret(path.read_bytes()):
            problems.append("Credential-like content: " + name)
    objects = git("rev-list", "--objects", "--all").decode().splitlines()
    object_names = {line.split(" ", 1)[0]: line.split(" ", 1)[1] if " " in line else "(Git object)" for line in objects}
    batch = git("cat-file", "--batch", data=("\n".join(object_names) + "\n").encode())
    offset = 0
    while offset < len(batch):
        end = batch.index(b"\n", offset)
        oid, kind, size = batch[offset:end].decode().split()
        size = int(size)
        content = batch[end + 1:end + 1 + size]
        if kind == "blob" and secret(content):
            problems.append("Credential-like Git history: " + object_names[oid])
        offset = end + 2 + size
    if problems:
        print("\n".join(sorted(set(problems))))
        raise SystemExit(1)
    print(f"Publication audit passed: {len([p for p in candidates if p])} source files and {len(object_names)} Git objects. No runtime data or credential-like content found.")


if __name__ == "__main__":
    main()
