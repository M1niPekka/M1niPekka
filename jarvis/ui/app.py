"""Local web UI for Jarvis: a Claude-styled chat window with live status and a
command-log tail. By default this only binds to localhost; jarvis/main.py's
`--lan` flag opens it up to your network (e.g. for phone access) and requires
an HTTP Basic Auth token to do so -- see create_app()'s `token` argument.
"""

import hmac
import threading
from pathlib import Path
from typing import Optional

from flask import Flask, Response, jsonify, request, send_from_directory

from jarvis import safety
from jarvis.config import config

STATIC_DIR = Path(__file__).parent / "static"


class JarvisState:
    """Shared, thread-safe state between the Flask request threads and the
    background voice-loop thread."""

    def __init__(self, brain, speaker, listener=None):
        self.brain = brain
        self.speaker = speaker
        self.listener = listener
        self.listening = False
        self._messages: list[dict] = []
        self._lock = threading.Lock()
        self._voice_thread: Optional[threading.Thread] = None

    def add_message(self, role: str, text: str) -> None:
        with self._lock:
            self._messages.append({"role": role, "text": text})

    def get_messages(self) -> list[dict]:
        with self._lock:
            return list(self._messages)

    def start_voice_loop(self) -> bool:
        if self.listener is None or self.listening:
            return self.listening
        self.listening = True
        self._voice_thread = threading.Thread(target=self._voice_loop, daemon=True)
        self._voice_thread.start()
        return True

    def stop_voice_loop(self) -> bool:
        self.listening = False
        return False

    def _voice_loop(self) -> None:
        while self.listening:
            if not self.listener.listen_for_wake_word(config.wake_word):
                continue
            self.speaker.say("Yes?")
            text = self.listener.listen_command()
            if not text:
                continue
            self.add_message("user", text)
            reply = self.brain.handle(text)
            self.add_message("assistant", reply)
            self.speaker.say(reply)


def create_app(state: JarvisState, token: str = "") -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")

    if token:
        @app.before_request
        def _check_auth():
            auth = request.authorization
            if not auth or not hmac.compare_digest(auth.password or "", token):
                return Response(
                    "Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Jarvis"'},
                )

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/status")
    def status():
        return jsonify({
            "brain": getattr(state.brain, "name", "unknown"),
            "wake_word": config.wake_word,
            "listening": state.listening,
            "voice_available": state.listener is not None,
            "allow_shell": config.allow_shell,
        })

    @app.get("/api/messages")
    def messages():
        return jsonify(state.get_messages())

    @app.post("/api/chat")
    def chat():
        text = (request.get_json(silent=True) or {}).get("text", "").strip()
        if not text:
            return jsonify({"error": "empty message"}), 400
        state.add_message("user", text)
        try:
            reply = state.brain.handle(text)
        except Exception as e:
            reply = f"Something went wrong: {e}"
        state.add_message("assistant", reply)
        return jsonify({"reply": reply})

    @app.post("/api/voice/start")
    def voice_start():
        return jsonify({"listening": state.start_voice_loop()})

    @app.post("/api/voice/stop")
    def voice_stop():
        return jsonify({"listening": state.stop_voice_loop()})

    @app.get("/api/logs")
    def logs():
        if not safety.LOG_PATH.exists():
            return jsonify({"log": ""})
        lines = safety.LOG_PATH.read_text().splitlines()[-200:]
        return jsonify({"log": "\n".join(lines)})

    return app
