from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from app.voice.speech_to_text import SpeechToText, SpeechToTextError


@dataclass(frozen=True)
class WakeWordConfig:
    wake_words: tuple[str, ...] = ("jarvis", "assistant")
    poll_delay_s: float = 0.2
    phrase_time_limit_s: float = 2.5


class WakeWordDetector:
    """
    Optional wake word detector.

    This is intentionally lightweight and conservative:
    - Runs in a background thread
    - Uses short microphone captures
    - Fires callback when any wake word is detected in transcript
    """

    def __init__(
        self,
        *,
        on_wake: Callable[[str], None],
        config: Optional[WakeWordConfig] = None,
    ):
        self.on_wake = on_wake
        self.config = config or WakeWordConfig()
        self._stt = SpeechToText()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        words = tuple(w.lower() for w in (self.config.wake_words or ()))
        while not self._stop.is_set():
            try:
                res = self._stt.transcribe_microphone(
                    timeout_s=3.0,
                    phrase_time_limit_s=float(self.config.phrase_time_limit_s),
                    ambient_noise_s=0.2,
                )
                text = (res.text or "").lower()
                if any(w in text for w in words):
                    try:
                        self.on_wake(text)
                    except Exception:
                        pass
                    # Avoid repeated triggers.
                    time.sleep(1.0)
            except SpeechToTextError:
                time.sleep(0.5)
            except Exception:
                time.sleep(0.5)
            finally:
                time.sleep(float(self.config.poll_delay_s))

