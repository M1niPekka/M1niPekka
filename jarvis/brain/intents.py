"""Rule-based fallback brain, used when no ANTHROPIC_API_KEY is configured.

Covers a handful of common commands with simple keyword matching so Jarvis
is still useful out of the box before you set up Claude tool-calling.
"""

import re
from typing import Callable

from jarvis.actions import apps, system


class IntentBrain:
    def __init__(self, confirm: Callable[[str], bool] | None = None):
        self.name = "Rule-based (no AI)"
        self.confirm = confirm  # accepted for interface parity with ClaudeBrain, unused here

    def handle(self, text: str) -> str:
        text = text.strip().lower()

        if match := re.match(r"open (.+)", text):
            return apps.open_app(match.group(1).strip())

        if match := re.match(r"(?:search|google) (?:for )?(.+)", text):
            return apps.search_web(match.group(1).strip())

        if "battery" in text:
            return system.get_battery()

        if "screenshot" in text:
            return system.take_screenshot()

        if "lock" in text and ("screen" in text or "mac" in text or "computer" in text):
            return system.lock_screen()

        if "sleep" in text:
            return system.sleep_mac()

        if match := re.match(r"(?:set )?volume (?:to )?(\d+)", text):
            return system.set_volume(int(match.group(1)))

        if "volume up" in text:
            return system.set_volume(80)

        if "volume down" in text:
            return system.set_volume(20)

        if "mute" in text:
            return system.set_volume(0)

        return (
            "I didn't recognize that command. Set ANTHROPIC_API_KEY in your .env "
            "to unlock full natural-language understanding."
        )
