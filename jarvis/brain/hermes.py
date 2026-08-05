"""Hermes (Nous Research) brain via a local Ollama server -- private, no API key.

Requires `ollama serve` running locally with a Hermes model pulled, e.g.:
    ollama pull hermes3
Hermes was one of the first open-weight fine-tunes trained for structured
tool/function calling, which Ollama exposes through an OpenAI-style `tools`
field on /api/chat.
"""

import json
import urllib.error
import urllib.request
from typing import Callable

from jarvis import safety
from jarvis.brain.tools import DISPATCH, TOOLS
from jarvis.config import config

SYSTEM_PROMPT = """You are Jarvis, a voice-controlled desktop assistant running on the \
user's own Mac, which they have given you full permission to operate on their behalf. \
Use the available tools to actually carry out requests -- don't just describe what you \
would do. Keep spoken replies short (1-2 sentences), since they are read aloud by \
text-to-speech. If a request is ambiguous, make a reasonable choice rather than asking \
endless clarifying questions. If a tool call fails or is declined, tell the user plainly."""


def _to_ollama_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


OLLAMA_TOOLS = _to_ollama_tools(TOOLS)


class HermesBrain:
    def __init__(self, confirm: Callable[[str], bool] | None = None):
        self.host = config.hermes_host.rstrip("/")
        self.model = config.hermes_model
        self.name = f"Hermes ({self.model})"
        self.confirm = confirm or (lambda prompt: input(f"{prompt} [y/N] ").strip().lower().startswith("y"))
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _execute_tool(self, name: str, tool_input: dict) -> str:
        if name not in DISPATCH:
            return f"Unknown tool: {name}"

        if name == "run_shell_command":
            command = tool_input.get("command", "")
            if config.confirm_dangerous and safety.is_dangerous(command):
                if not self.confirm(f"That command looks risky: `{command}`. Should I run it?"):
                    safety.log_command(command, "declined by user")
                    return "Command declined by the user."

        try:
            return DISPATCH[name](tool_input)
        except Exception as e:
            return f"Tool '{name}' failed: {e}"

    def _chat(self) -> dict:
        payload = json.dumps({
            "model": self.model,
            "messages": self.history,
            "tools": OLLAMA_TOOLS,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=payload, headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Couldn't reach Ollama at {self.host} ({e}). Is `ollama serve` running, "
                f"and have you pulled the model with `ollama pull {self.model}`?"
            ) from e

    def handle(self, user_text: str) -> str:
        self.history.append({"role": "user", "content": user_text})

        for _ in range(6):  # bounded agent loop to avoid runaway tool chains
            data = self._chat()
            message = data.get("message", {})
            self.history.append(message)

            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return (message.get("content") or "").strip()

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                result = self._execute_tool(name, args)
                self.history.append({"role": "tool", "content": result})

        return "That took more steps than expected, so I stopped -- try breaking it into smaller requests."
