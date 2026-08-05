"""Raw shell command execution. This is the 'full access' escape hatch --
every call is logged, and callers are expected to route anything matching
safety.is_dangerous() through a confirmation step first (see brain/llm.py).
"""

import subprocess

from jarvis import safety
from jarvis.config import config


def run_command(command: str) -> str:
    if not config.allow_shell:
        return "Shell access is disabled (ALLOW_SHELL=false)."

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=config.command_timeout,
        )
        output = (result.stdout + result.stderr).strip() or "(no output)"
        summary = f"exit {result.returncode}: {output[:2000]}"
    except subprocess.TimeoutExpired:
        summary = f"Command timed out after {config.command_timeout}s."

    safety.log_command(command, summary)
    return summary
