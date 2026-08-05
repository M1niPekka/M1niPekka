"""Text-to-speech via macOS's built-in `say` command -- no extra deps, no API key."""

import subprocess

from jarvis.config import config


class Speaker:
    def __init__(self, voice: str | None = None):
        self.voice = voice or config.voice

    def say(self, text: str) -> None:
        if not text:
            return
        print(f"Jarvis: {text}")
        try:
            subprocess.run(["say", "-v", self.voice, text], check=False)
        except FileNotFoundError:
            # Not on macOS / `say` unavailable -- fall back to text only.
            pass
