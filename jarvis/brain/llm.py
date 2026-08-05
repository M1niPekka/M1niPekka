"""Claude-powered brain: turns natural language into tool calls against the desktop."""

from typing import Callable

import anthropic

from jarvis import safety
from jarvis.brain.tools import DISPATCH, TOOLS
from jarvis.config import config

SYSTEM_PROMPT = """You are Jarvis, a voice-controlled desktop assistant running on the \
user's own Mac, which they have given you full permission to operate on their behalf. \
Use the available tools to actually carry out requests -- don't just describe what you \
would do. Keep spoken replies short (1-2 sentences), since they are read aloud by \
text-to-speech. If a request is ambiguous, make a reasonable choice rather than asking \
endless clarifying questions. If a tool call fails or is declined, tell the user plainly."""


class ClaudeBrain:
    def __init__(self, confirm: Callable[[str], bool] | None = None):
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.confirm = confirm or (lambda prompt: input(f"{prompt} [y/N] ").strip().lower().startswith("y"))
        self.history: list[dict] = []

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

    def handle(self, user_text: str) -> str:
        self.history.append({"role": "user", "content": user_text})

        for _ in range(6):  # bounded agent loop to avoid runaway tool chains
            response = self.client.messages.create(
                model=config.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.history,
            )
            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                return "".join(block.text for block in response.content if block.type == "text").strip()

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result = self._execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
            self.history.append({"role": "user", "content": tool_results})

        return "That took more steps than expected, so I stopped -- try breaking it into smaller requests."
