"""Entrypoint. Voice mode (default): say the wake word, then speak a command.
Text mode (`--text`): type commands instead, useful for testing without a mic.
"""

import argparse
import sys

from jarvis.config import config


def build_brain(confirm):
    if config.anthropic_api_key:
        from jarvis.brain.llm import ClaudeBrain
        return ClaudeBrain(confirm=confirm)
    print("[jarvis] No ANTHROPIC_API_KEY set -- using limited rule-based commands.")
    from jarvis.brain.intents import IntentBrain
    return IntentBrain(confirm=confirm)


def run_text_mode() -> None:
    confirm = lambda prompt: input(f"{prompt} [y/N] ").strip().lower().startswith("y")
    brain = build_brain(confirm)
    print("Jarvis text mode. Type 'exit' to quit.")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("exit", "quit"):
            break
        if not text:
            continue
        print(brain.handle(text))


def run_voice_mode() -> None:
    from jarvis.audio.listener import Listener
    from jarvis.audio.speaker import Speaker

    speaker = Speaker()
    listener = Listener()

    def confirm(prompt: str) -> bool:
        speaker.say(prompt)
        reply = listener.listen_command(timeout=6, phrase_time_limit=4)
        return reply.strip().lower().startswith(("yes", "yeah", "confirm", "go ahead", "do it"))

    brain = build_brain(confirm)

    speaker.say("Jarvis online.")
    print(f"[jarvis] Listening for wake word '{config.wake_word}'... (Ctrl+C to quit)")
    try:
        while True:
            if not listener.listen_for_wake_word(config.wake_word):
                continue
            speaker.say("Yes?")
            text = listener.listen_command()
            if not text:
                speaker.say("I didn't catch that.")
                continue
            if text.lower() in ("exit", "quit", "goodbye", "shut down jarvis", "stop listening"):
                speaker.say("Goodbye.")
                break
            speaker.say(brain.handle(text))
    except KeyboardInterrupt:
        speaker.say("Goodbye.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis desktop assistant")
    parser.add_argument("--text", action="store_true", help="Run in text mode instead of voice mode")
    args = parser.parse_args()

    if args.text:
        run_text_mode()
    else:
        run_voice_mode()


if __name__ == "__main__":
    sys.exit(main())
