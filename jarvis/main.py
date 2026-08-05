"""Entrypoint. Voice mode (default): say the wake word, then speak a command.
Text mode (`--text`): type commands instead, useful for testing without a mic.
UI mode (`--ui`): a local Claude-styled web chat window at localhost.
"""

import argparse
import sys

from jarvis.config import config


def build_brain(confirm):
    choice = config.brain

    if choice == "claude" or (choice == "auto" and config.anthropic_api_key):
        from jarvis.brain.llm import ClaudeBrain
        return ClaudeBrain(confirm=confirm)

    if choice == "hermes" or choice == "auto":
        from jarvis.brain.hermes import HermesBrain
        print(f"[jarvis] Using Hermes ({config.hermes_model} via {config.hermes_host}) as the brain.")
        print("[jarvis] If Ollama isn't running, replies will explain how to start it.")
        return HermesBrain(confirm=confirm)

    print("[jarvis] Using limited rule-based commands (BRAIN=intents).")
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


def _lan_ips() -> list[tuple[str, str]]:
    """(interface, ipv4) pairs for every non-loopback address on the machine,
    Wi-Fi/Ethernet interfaces first. On a VPN, the "obvious" route can point
    at a tunnel interface instead of the actual LAN -- so we list every
    candidate rather than guessing just one."""
    import psutil
    import socket

    candidates = []
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                candidates.append((iface, addr.address))

    def rank(item: tuple[str, str]) -> int:
        iface = item[0]
        if iface.startswith("en"):  # macOS Wi-Fi/Ethernet
            return 0
        if iface.startswith(("utun", "ppp", "awdl", "llw", "tun", "tap")):  # VPNs, AirDrop, etc.
            return 2
        return 1

    candidates.sort(key=rank)
    return candidates


def run_ui_mode(lan: bool = False, port: int = 5050, open_browser: bool = True) -> None:
    import secrets
    import webbrowser

    from jarvis.ui.app import JarvisState, create_app

    from jarvis.audio.speaker import Speaker
    speaker = Speaker()

    try:
        from jarvis.audio.listener import Listener
        listener = Listener()
    except Exception as e:
        print(f"[jarvis] No microphone available ({e}) -- voice toggle disabled, chat still works.")
        listener = None

    state = JarvisState(brain=None, speaker=speaker, listener=listener)

    def confirm(prompt: str) -> bool:
        # Only voice can confirm risky commands in UI mode; with no active
        # voice session there's no channel to ask through, so default to no.
        if state.listening and listener is not None:
            speaker.say(prompt)
            reply = listener.listen_command(timeout=6, phrase_time_limit=4)
            return reply.strip().lower().startswith(("yes", "yeah", "confirm", "go ahead", "do it"))
        return False

    state.brain = build_brain(confirm)

    host = "0.0.0.0" if lan else "127.0.0.1"
    token = config.ui_token
    if lan and not token:
        token = secrets.token_urlsafe(12)
        print("[jarvis] --lan is on but JARVIS_UI_TOKEN isn't set -- generated a one-time password for this session.")

    app = create_app(state, token=token)

    if lan:
        candidates = _lan_ips()
        if not candidates:
            print("[jarvis] Couldn't find any network IP -- are you connected to WiFi?")
        else:
            best_iface, best_ip = candidates[0]
            print(f"[jarvis] UI reachable on your network at http://{best_ip}:{port}  (interface: {best_iface})")
            if len(candidates) > 1:
                others = ", ".join(f"http://{ip}:{port} ({iface})" for iface, ip in candidates[1:])
                print(f"[jarvis]   If that one doesn't load on your phone, also try: {others}")
            print(f"[jarvis]   On your phone: open the URL (same WiFi), username can be anything, password: {token}")
            print("[jarvis]   Can't reach it? See 'Troubleshooting phone access' in jarvis/README.md.")
        local_url = f"http://127.0.0.1:{port}"
    else:
        local_url = f"http://{host}:{port}"
        print(f"[jarvis] UI running at {local_url}")

    if open_browser:
        webbrowser.open(local_url)
    app.run(host=host, port=port, debug=False, threaded=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis desktop assistant")
    parser.add_argument("--text", action="store_true", help="Run in text mode instead of voice mode")
    parser.add_argument("--ui", action="store_true", help="Run the local Claude-styled web UI")
    parser.add_argument(
        "--lan", action="store_true",
        help="With --ui, bind to your network (not just localhost) so other devices, e.g. your phone, can reach it. Requires a password -- see JARVIS_UI_TOKEN.",
    )
    parser.add_argument("--no-browser", action="store_true", help="With --ui, don't auto-open a browser tab")
    args = parser.parse_args()

    if args.ui:
        run_ui_mode(lan=args.lan, open_browser=not args.no_browser)
    elif args.text:
        run_text_mode()
    else:
        run_voice_mode()


if __name__ == "__main__":
    sys.exit(main())
