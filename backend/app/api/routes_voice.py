from __future__ import annotations

import base64
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.auth import get_optional_current_user
from app.core.brain_controller import BrainController
from app.core.voice_logs import log_voice_event
from app.database.db import get_db
from app.database.models import User
from app.services.event_bus import get_event_bus
from app.voice.speech_to_text import SpeechToTextError, transcribe_audio_bytes_async


router = APIRouter()


class VoiceTextRequest(BaseModel):
    user_id: str = "default"
    provider: Optional[str] = None
    model: Optional[str] = None
    text: Optional[str] = None
    audio_base64: Optional[str] = None
    filename: Optional[str] = None
    session_id: str = "default"


def _resolve_user_id(request_user_id: str, current_user: User | None) -> str:
    if current_user:
        return (current_user.user_id or "").strip() or "default"
    return (request_user_id or "").strip() or "default"


@router.post("/voice/input")
async def voice_input(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
    stream: bool = False,
):
    """
    Unified voice endpoint.

    Supports:
    - JSON: {text} OR {audio_base64}
    - multipart/form-data: audio=<file>

    Returns transcript + assistant response from the same BrainController pipeline as chat.
    """
    req_id = uuid.uuid4().hex
    started = time.perf_counter()

    content_type = (request.headers.get("content-type") or "").lower()
    payload: Dict[str, Any] = {}
    audio_bytes: bytes | None = None
    filename_hint = "audio.webm"

    if "multipart/form-data" in content_type:
        form = await request.form()
        audio = form.get("audio")
        if audio is None:
            raise HTTPException(status_code=400, detail={"error": "missing_audio", "message": "Missing form field: audio"})
        try:
            filename_hint = getattr(audio, "filename", None) or filename_hint
            audio_bytes = await audio.read()
        except Exception:
            raise HTTPException(status_code=400, detail={"error": "bad_audio", "message": "Could not read audio"})
        payload = {
            "user_id": form.get("user_id") or "default",
            "provider": form.get("provider"),
            "model": form.get("model"),
            "session_id": form.get("session_id") or "default",
        }
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        parsed = VoiceTextRequest(**payload) if isinstance(payload, dict) else VoiceTextRequest()
        payload = parsed.model_dump()
        if payload.get("audio_base64"):
            try:
                audio_bytes = base64.b64decode(payload["audio_base64"])
                filename_hint = payload.get("filename") or filename_hint
            except Exception:
                raise HTTPException(status_code=400, detail={"error": "bad_audio_base64", "message": "Invalid audio_base64"})

    user_id = _resolve_user_id(str(payload.get("user_id") or "default"), current_user)
    provider = payload.get("provider")
    model = payload.get("model")
    session_id = str(payload.get("session_id") or "default")

    async def _transcribe() -> tuple[str, float]:
        transcript = (payload.get("text") or "").strip()
        confidence = 1.0

        if audio_bytes is not None:
            log_voice_event("voice.api_audio_received", {"request_id": req_id, "user_id": user_id, "bytes": len(audio_bytes)})
            try:
                tr = await transcribe_audio_bytes_async(audio_bytes, filename_hint=filename_hint, timeout_s=20.0)
                transcript = (tr.text or "").strip()
                confidence = float(tr.confidence or 0.0)
            except SpeechToTextError as e:
                log_voice_event("voice.api_transcribe_failed", {"request_id": req_id, "user_id": user_id}, error=str(e))
                raise HTTPException(status_code=500, detail={"error": "transcription_failed", "message": str(e)})

        if not transcript:
            raise HTTPException(status_code=422, detail={"error": "empty_transcript", "message": "No speech detected"})

        return transcript, confidence

    async def _run_brain(transcript: str) -> tuple[str, list[dict]]:
        brain = BrainController(db=db, user_id=user_id, provider=provider, model=model, is_authenticated=bool(current_user))
        result = await brain.handle_text(transcript, session_id=session_id, source="voice")
        if result.get("status") == "needs_confirmation":
            prompt = ((result.get("result") or {}).get("prompt") or "").strip()
            response_text = prompt or "Please confirm to proceed."
            tasks = []
        else:
            response_text = (result.get("response_text") or "").strip()
            tasks = list(result.get("tasks") or [])
        return response_text, tasks

    async def _compute() -> Dict[str, Any]:
        transcript, confidence = await _transcribe()

        bus = get_event_bus()
        try:
            await bus.publish("voice.transcript", {"request_id": req_id, "user_id": user_id, "text": transcript, "confidence": confidence})
        except Exception:
            pass

        response_text, tasks = await _run_brain(transcript)
        latency_ms = int((time.perf_counter() - started) * 1000)

        try:
            await bus.publish("voice.response", {"request_id": req_id, "user_id": user_id, "response_text": response_text, "latency_ms": latency_ms})
        except Exception:
            pass

        log_voice_event(
            "voice.api_response",
            {
                "request_id": req_id,
                "user_id": user_id,
                "transcript": transcript,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "tasks": len(tasks),
            },
        )

        return {
            "status": "success",
            "request_id": req_id,
            "transcript": transcript,
            "confidence": confidence,
            "response_text": response_text,
            "tasks": tasks,
            "latency_ms": latency_ms,
        }

    if not stream:
        return await _compute()

    async def _sse():
        import json

        yield "event: voice.start\n"
        yield f"data: {req_id}\n\n"

        transcript, confidence = await _transcribe()
        yield "event: voice.transcript\n"
        yield f"data: {json.dumps({'request_id': req_id, 'transcript': transcript, 'confidence': confidence}, ensure_ascii=False)}\n\n"

        response_text, tasks = await _run_brain(transcript)
        latency_ms = int((time.perf_counter() - started) * 1000)
        final = {
            "status": "success",
            "request_id": req_id,
            "transcript": transcript,
            "confidence": confidence,
            "response_text": response_text,
            "tasks": tasks,
            "latency_ms": latency_ms,
        }
        yield "event: voice.done\n"
        yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"

    return StreamingResponse(_sse(), media_type="text/event-stream")
