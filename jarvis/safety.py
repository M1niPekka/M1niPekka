"""Guardrails for the raw-shell tool: logging + confirmation on risky commands."""

import re
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path(__file__).parent / "logs" / "commands.log"

# Patterns that should always trigger a spoken confirmation before running,
# even with ALLOW_SHELL enabled. Not a sandbox -- just a "are you sure?" net.
DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\brm\s+-rf\s+~",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{.*\}\s*;\s*:",  # fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bdiskutil\s+(erase|partition)",
    r"\bsudo\b",
    r">\s*/dev/sd",
    r"\bchmod\s+-R\s+777\s+/",
    r"\bkillall\b",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]


def is_dangerous(command: str) -> bool:
    return any(p.search(command) for p in _COMPILED)


def log_command(command: str, result: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with LOG_PATH.open("a") as f:
        f.write(f"[{timestamp}] CMD: {command}\nRESULT: {result}\n---\n")
