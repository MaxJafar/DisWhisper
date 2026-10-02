"""Reject local artifacts in source and credentials in source or Git history."""

import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ASSISTANT_FILES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "CODEX.md", "copilot-instructions.md"}
ASSISTANT_DIRS = {".codex", ".claude", ".cursor"}
RUNTIME_DIRS = {
    ".cache", ".venv", "venv", "ENV", "dist", "build", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".build", "xcuserdata", ".vs", ".idea", ".vscode", "bin", "obj",
}


def file_problem(path):
    """Classify files that belong only in a local checkout."""
    if (
        path.name == "config.json"
        or path.name == ".env"
        or path.name.startswith(".env.") and path.name != ".env.example"
    ):
        return "Private configuration"
    if (
        path.name in ASSISTANT_FILES
        or ASSISTANT_DIRS.intersection(path.parts)
        or any(part.startswith(".aider") for part in path.parts)
        or path.name.startswith("codex-clipboard-")
    ):
        return "Local assistant artifact"
    if RUNTIME_DIRS.intersection(path.parts) or (
        path.parts[0] in {"transcripts", "models"} and path.as_posix() != "transcripts/.gitkeep"
    ):
        return "Runtime/build file"
    if (
        path.name in {".DS_Store", "Thumbs.db", ".coverage"}
        or path.suffix in {".bak", ".orig", ".rej", ".swp", ".swo", ".tmp", ".log"}
        or path.name.endswith("~")
    ):
        return "Temporary/local file"
    return None


def git(*args, data=None):
    return subprocess.run(["git", *args], input=data, check=True, stdout=subprocess.PIPE).stdout


def main():
    candidates = [
        Path(name)
        for name in dict.fromkeys(
            git("ls-files", "-co", "--exclude-standard", "-z").decode().split("\0")
        )
        if name and Path(name).is_file()
    ]
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
        return any(value in data for value in known) or any(
            re.search(pattern, data) for pattern in patterns
        )

    problems = []
    for path in candidates:
        problem = file_problem(path)
        if problem:
            problems.append(f"{problem}: {path}")
        if secret(path.read_bytes()):
            problems.append(f"Credential-like content: {path}")
    objects = git("rev-list", "--objects", "--all").decode().splitlines()
    object_names = {
        line.split(" ", 1)[0]: line.split(" ", 1)[1] if " " in line else "(Git object)"
        for line in objects
    }
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
    print(
        f"Publication audit passed: {len(candidates)} source files and "
        f"{len(object_names)} Git objects. "
        "No local artifacts, runtime data, or credential-like content found."
    )


if __name__ == "__main__":
    main()
