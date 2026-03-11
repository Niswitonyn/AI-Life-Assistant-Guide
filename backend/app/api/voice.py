from __future__ import annotations

import os

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.voice_logs import log_voice_event
from app.voice.speech_to_text import SpeechToTextError, transcribe_audio_bytes_async

router = APIRouter()

MIN_AUDIO_BYTES = int(os.getenv("VOICE_MIN_AUDIO_BYTES", "2000"))
MIN_TRANSCRIPT_CHARS = int(os.getenv("VOICE_MIN_TRANSCRIPT_CHARS", "2"))


@router.post("/voice")
async def voice_chat(audio: UploadFile = File(...)):
    try:
        content = await audio.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty audio payload")
        if len(content) < MIN_AUDIO_BYTES:
            raise HTTPException(status_code=422, detail="Audio too short")

        filename = (audio.filename or "recording.webm").strip() or "recording.webm"
        filename_hint = os.path.basename(filename)

        try:
            tr = await transcribe_audio_bytes_async(content, filename_hint=filename_hint, timeout_s=20.0)
        except SpeechToTextError as e:
            log_voice_event("voice.legacy_endpoint_transcribe_failed", {"filename": filename_hint, "bytes": len(content)}, error=str(e))
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

        text = (tr.text or "").strip()
        if len(text) < MIN_TRANSCRIPT_CHARS:
            raise HTTPException(status_code=422, detail="No speech detected")

        # Keep legacy contract: return only transcript.
        return {"text": text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
