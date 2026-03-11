from __future__ import annotations

import os
import queue
import threading
from dataclasses import dataclass
from typing import Optional

import pyttsx3


class TextToSpeechError(RuntimeError):
    pass


@dataclass(frozen=True)
class TTSSettings:
    rate: int = 185
    volume: float = 1.0


class AsyncTextToSpeech:
    """
    Non-blocking TTS wrapper around pyttsx3.

    `speak()` enqueues text and returns immediately.
    A dedicated worker thread performs playback.
    """

    def __init__(self, *, settings: Optional[TTSSettings] = None):
        self.settings = settings or TTSSettings(
            rate=int(os.getenv("TTS_RATE", "185")),
            volume=float(os.getenv("TTS_VOLUME", "1.0")),
        )
        self._q: queue.Queue[str] = queue.Queue(maxsize=50)
        self._stop_event = threading.Event()
        self._engine_lock = threading.Lock()
        self._engine = pyttsx3.init()
        self._apply_settings()

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _apply_settings(self) -> None:
        try:
            self._engine.setProperty("rate", int(self.settings.rate))
        except Exception:
            pass
        try:
            vol = float(self.settings.volume)
            self._engine.setProperty("volume", max(0.0, min(1.0, vol)))
        except Exception:
            pass

    def speak(self, text: str) -> None:
        cleaned = (text or "").strip()
        if not cleaned:
            return
        try:
            self._q.put_nowait(cleaned)
        except queue.Full:
            # Drop oldest to keep latency low.
            try:
                _ = self._q.get_nowait()
            except Exception:
                pass
            try:
                self._q.put_nowait(cleaned)
            except Exception:
                return

    def stop_speaking(self) -> None:
        self._stop_event.set()
        with self._engine_lock:
            try:
                self._engine.stop()
            except Exception:
                pass
        self._stop_event.clear()
        self._drain_queue()

    def _drain_queue(self) -> None:
        try:
            while True:
                self._q.get_nowait()
        except Exception:
            return

    def _run(self) -> None:
        while True:
            text = self._q.get()
            if not text:
                continue
            if self._stop_event.is_set():
                continue
            with self._engine_lock:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception:
                    # Keep worker alive on TTS engine errors.
                    continue

    def is_alive(self) -> bool:
        try:
            return bool(self._thread and self._thread.is_alive())
        except Exception:
            return False


_tts_lock = threading.Lock()
_tts: AsyncTextToSpeech | None = None


def _ensure_tts() -> AsyncTextToSpeech:
    global _tts
    with _tts_lock:
        if _tts is None:
            _tts = AsyncTextToSpeech()
        return _tts


def speak(text: str) -> None:
    _ensure_tts().speak(text)


def stop_speaking() -> None:
    tts = _tts
    if tts is None:
        return
    tts.stop_speaking()


def health() -> dict:
    """
    Best-effort health info for monitoring.
    """
    try:
        tts = _tts
        if tts is None:
            return {"ok": True, "thread_alive": False, "lazy": True}
        alive = tts.is_alive()
        return {"ok": bool(alive), "thread_alive": bool(alive)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def reset_tts() -> None:
    """
    Best-effort reset for the TTS engine (safe restart).

    Note: any existing worker thread is daemonized; we avoid blocking on teardown.
    """
    global _tts
    with _tts_lock:
        try:
            if _tts is not None:
                _tts.stop_speaking()
        except Exception:
            pass
        _tts = AsyncTextToSpeech()
