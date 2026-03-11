from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.brain_controller import BrainController
from app.core.voice_logs import log_voice_event
from app.voice.speech_to_text import SpeechToText, SpeechToTextError, TranscriptionResult
from app.voice.text_to_speech import speak, stop_speaking


@dataclass(frozen=True)
class VoiceResponse:
    transcript: str
    confidence: float
    response_text: str
    tasks: list[dict]
    latency_ms: int


class VoiceController:
    """
    Coordinates voice input -> BrainController -> (optional) TTS output.

    This is intended for local voice mode. The HTTP API reuses the same
    pipeline but typically lets the frontend handle audio playback.
    """

    def __init__(
        self,
        *,
        db: Session,
        user_id: str = "default",
        provider: str | None = None,
        model: str | None = None,
    ):
        self.db = db
        self.user_id = (user_id or "").strip() or "default"
        self.provider = provider
        self.model = model
        self.stt = SpeechToText()

    async def listen_once(self) -> VoiceResponse:
        started = time.perf_counter()
        try:
            tr = await asyncio.to_thread(self.stt.transcribe_microphone)
        except SpeechToTextError as e:
            log_voice_event("voice.transcribe_error", {"user_id": self.user_id}, error=str(e))
            raise

        return await self.handle_text(tr, started=started)

    async def handle_audio_bytes(self, audio_bytes: bytes, *, filename_hint: str = "audio.webm") -> VoiceResponse:
        started = time.perf_counter()
        tr = await asyncio.to_thread(self.stt.transcribe_audio_bytes, audio_bytes, filename_hint=filename_hint)
        return await self.handle_text(tr, started=started)

    async def handle_text(self, tr: TranscriptionResult, *, started: float | None = None) -> VoiceResponse:
        started = started or time.perf_counter()
        transcript = (tr.text or "").strip()
        if not transcript:
            log_voice_event("voice.empty_transcript", {"user_id": self.user_id, "confidence": tr.confidence})
            return VoiceResponse(
                transcript="",
                confidence=float(tr.confidence or 0.0),
                response_text="I didn't catch that. Please try again.",
                tasks=[],
                latency_ms=int((time.perf_counter() - started) * 1000),
            )

        log_voice_event("voice.transcript", {"user_id": self.user_id, "text": transcript, "confidence": tr.confidence})

        brain = BrainController(
            db=self.db,
            user_id=self.user_id,
            provider=self.provider,
            model=self.model,
        )
        result = await brain.handle_text(transcript, source="voice")
        response_text = (result.get("response_text") or "").strip()
        tasks = list(result.get("tasks") or [])

        latency_ms = int((time.perf_counter() - started) * 1000)
        log_voice_event(
            "voice.response",
            {"user_id": self.user_id, "transcript": transcript, "latency_ms": latency_ms},
        )

        return VoiceResponse(
            transcript=transcript,
            confidence=float(tr.confidence or 0.0),
            response_text=response_text,
            tasks=tasks,
            latency_ms=latency_ms,
        )

    def speak(self, text: str) -> None:
        speak(text)

    def stop_speaking(self) -> None:
        stop_speaking()

