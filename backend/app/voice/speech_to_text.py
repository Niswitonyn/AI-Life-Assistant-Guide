from __future__ import annotations

import asyncio
import os
import re
import tempfile
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import speech_recognition as sr


class SpeechToTextError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    confidence: float
    language: str | None = None
    timed_out: bool = False


def _clean_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _logprob_to_confidence(avg_logprob: float) -> float:
    # faster-whisper avg_logprob is typically in [-5, 0]. Map loosely into [0,1].
    try:
        x = float(avg_logprob)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, (x + 5.0) / 5.0))


class SpeechToText:
    """
    Speech-to-text helper.

    - Microphone capture uses SpeechRecognition for VAD/sentence detection.
    - Transcription is performed with faster-whisper (offline) when possible.
    """

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = float(os.getenv("VOICE_PAUSE_THRESHOLD", "0.8"))
        self.recognizer.non_speaking_duration = float(os.getenv("VOICE_NON_SPEAKING_DURATION", "0.5"))

        self._whisper_model = None
        self._whisper_model_error: str | None = None

    def transcribe_microphone(
        self,
        *,
        timeout_s: float = 8.0,
        phrase_time_limit_s: float = 12.0,
        ambient_noise_s: float = 0.6,
    ) -> TranscriptionResult:
        """
        Capture from the default microphone and return a cleaned transcript.

        Sentence detection is provided by SpeechRecognition's silence detection.
        """
        try:
            with sr.Microphone(sample_rate=16000) as source:
                if ambient_noise_s and ambient_noise_s > 0:
                    try:
                        self.recognizer.adjust_for_ambient_noise(source, duration=float(ambient_noise_s))
                    except Exception:
                        pass
                audio = self.recognizer.listen(
                    source,
                    timeout=max(0.1, float(timeout_s)),
                    phrase_time_limit=max(0.5, float(phrase_time_limit_s)),
                )
        except sr.WaitTimeoutError as e:
            raise SpeechToTextError("Microphone listen timed out.") from e
        except Exception as e:
            raise SpeechToTextError(f"Microphone not available: {e}") from e

        wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
        return self.transcribe_audio_bytes(wav_bytes, filename_hint="mic.wav")

    def transcribe_audio_bytes(self, audio_bytes: bytes, *, filename_hint: str = "audio.webm") -> TranscriptionResult:
        if not audio_bytes or len(audio_bytes) < int(os.getenv("VOICE_MIN_AUDIO_BYTES", "2000")):
            raise SpeechToTextError("Audio too short or empty.")

        suffix = os.path.splitext(filename_hint)[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            text, language, avg_logprob = self._transcribe_file(tmp_path)
            cleaned = _clean_text(text)
            if not cleaned:
                return TranscriptionResult(text="", confidence=0.0, language=language)
            return TranscriptionResult(text=cleaned, confidence=_logprob_to_confidence(avg_logprob), language=language)
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    def _get_whisper_model(self):
        if self._whisper_model is not None:
            return self._whisper_model
        if self._whisper_model_error is not None:
            raise SpeechToTextError(self._whisper_model_error)

        try:
            from faster_whisper import WhisperModel

            model_size = os.getenv("WHISPER_MODEL_SIZE", "tiny.en")
            self._whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
            return self._whisper_model
        except Exception as e:
            self._whisper_model_error = str(e) or "Failed to initialize Whisper model"
            raise SpeechToTextError(self._whisper_model_error) from e

    def _transcribe_file(self, path: str) -> Tuple[str, Optional[str], float]:
        model = self._get_whisper_model()
        beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "2"))
        best_of = int(os.getenv("WHISPER_BEST_OF", "2"))
        temperature = float(os.getenv("WHISPER_TEMPERATURE", "0.0"))
        vad_filter = os.getenv("WHISPER_VAD_FILTER", "true").lower() == "true"

        segments, info = model.transcribe(
            path,
            language="en",
            beam_size=beam_size,
            best_of=best_of,
            temperature=temperature,
            vad_filter=vad_filter,
            condition_on_previous_text=False,
            without_timestamps=True,
        )

        texts = []
        logprobs = []
        for seg in segments:
            if getattr(seg, "text", None):
                texts.append(seg.text.strip())
            if getattr(seg, "avg_logprob", None) is not None:
                logprobs.append(float(seg.avg_logprob))

        avg_logprob = sum(logprobs) / len(logprobs) if logprobs else -5.0
        language = getattr(info, "language", None)
        return " ".join([t for t in texts if t]).strip(), language, avg_logprob


_stt = SpeechToText()


def transcribe_microphone() -> dict:
    """
    Compatibility function required by the project spec.

    Returns:
      {"text": "...", "confidence": 0.92}
    """
    res = _stt.transcribe_microphone()
    return {"text": res.text, "confidence": float(res.confidence)}


async def transcribe_audio_bytes_async(
    audio_bytes: bytes,
    *,
    filename_hint: str = "audio.webm",
    timeout_s: float = 20.0,
) -> TranscriptionResult:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_stt.transcribe_audio_bytes, audio_bytes, filename_hint=filename_hint),
            timeout=float(timeout_s),
        )
    except asyncio.TimeoutError as e:
        raise SpeechToTextError(f"Transcription timed out after {timeout_s}s") from e

