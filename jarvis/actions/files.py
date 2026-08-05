"""Find, open, move, and browse files using macOS Spotlight (`mdfind`) and Finder."""

import shutil
import subprocess
from pathlib import Path


def find_files(query: str, limit: int = 10) -> str:
    result = subprocess.run(["mdfind", query], capture_output=True, text=True)
    if result.returncode != 0:
        return f"Search failed: {result.stderr.strip()}"
    paths = [p for p in result.stdout.splitlines() if p][:limit]
    if not paths:
        return f"No files found matching '{query}'."
    return "Found:\n" + "\n".join(paths)


def open_path(path: str) -> str:
    resolved = Path(path).expanduser()
    result = subprocess.run(["open", str(resolved)], capture_output=True, text=True)
    if result.returncode != 0:
        return f"Couldn't open {path}: {result.stderr.strip()}"
    return f"Opened {path}."


def reveal_in_finder(path: str) -> str:
    resolved = Path(path).expanduser()
    result = subprocess.run(["open", "-R", str(resolved)], capture_output=True, text=True)
    if result.returncode != 0:
        return f"Couldn't reveal {path}: {result.stderr.strip()}"
    return f"Revealed {path} in Finder."


def list_dir(path: str = "~") -> str:
    resolved = Path(path).expanduser()
    if not resolved.exists():
        return f"{path} does not exist."
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in resolved.iterdir())
    if not entries:
        return f"{path} is empty."
    return "\n".join(entries)


def move_file(source: str, destination: str) -> str:
    src, dst = Path(source).expanduser(), Path(destination).expanduser()
    if not src.exists():
        return f"{source} does not exist."
    shutil.move(str(src), str(dst))
    return f"Moved {source} to {destination}."
