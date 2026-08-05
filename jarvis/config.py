"""Central configuration, loaded from environment / .env."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    # Which brain to use: "auto" (Claude if a key is set, else Hermes, else
    # rule-based), "claude", "hermes", or "intents".
    brain: str = os.getenv("BRAIN", "auto").lower()

    # Hermes (Nous Research) runs locally via Ollama -- no API key needed.
    hermes_host: str = os.getenv("HERMES_HOST", "http://localhost:11434")
    hermes_model: str = os.getenv("HERMES_MODEL", "hermes3")

    wake_word: str = os.getenv("WAKE_WORD", "jarvis").lower()
    voice: str = os.getenv("TTS_VOICE", "Daniel")
    allow_shell: bool = _env_bool("ALLOW_SHELL", True)
    confirm_dangerous: bool = _env_bool("CONFIRM_DANGEROUS", True)
    command_timeout: int = int(os.getenv("SHELL_TIMEOUT", "30"))


config = Config()
