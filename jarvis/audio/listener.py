"""Microphone capture: wake-word spotting + full command transcription.

Uses SpeechRecognition with the free Google Web Speech API for STT. No API
key is required for this endpoint, but it does need network access.
"""

from __future__ import annotations

import speech_recognition as sr


class Listener:
    def __init__(self, energy_threshold: int | None = None):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        if energy_threshold:
            self.recognizer.energy_threshold = energy_threshold

    def _transcribe(self, audio: sr.AudioData) -> str:
        try:
            return self.recognizer.recognize_google(audio).lower()
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            print(f"[listener] speech recognition service error: {e}")
            return ""

    def listen_for_wake_word(self, wake_word: str, timeout: float = 5, phrase_time_limit: float = 3) -> bool:
        """Blocks until the wake word is heard, or returns False after `timeout` with silence."""
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError:
                return False
        text = self._transcribe(audio)
        return wake_word in text

    def listen_command(self, timeout: float = 6, phrase_time_limit: float = 12) -> str:
        """Blocks for a spoken command and returns the transcript (possibly empty)."""
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError:
                return ""
        return self._transcribe(audio)
