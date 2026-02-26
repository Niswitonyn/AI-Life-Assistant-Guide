from fastapi import APIRouter, UploadFile, File, HTTPException
from faster_whisper import WhisperModel
import asyncio
import tempfile
import os
import logging
import time

router = APIRouter()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TRANSCRIBE_TIMEOUT_SECONDS = int(os.getenv("VOICE_TRANSCRIBE_TIMEOUT_SECONDS", "20"))

# Load model once
try:
    model_size = os.getenv("WHISPER_MODEL_SIZE", "tiny")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    logger.info(
        f"Whisper model loaded successfully (model={model_size}, device=cpu, compute_type=int8)"
    )
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    model = None


def _transcribe_file(path: str):
    segments, info = model.transcribe(
        path,
        language="en",
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
        without_timestamps=True,
    )
    text = " ".join(seg.text.strip() for seg in segments if seg.text).strip()
    return text, info


@router.post("/voice")
async def voice_chat(audio: UploadFile = File(...)):
    temp_path = None
    try:
        if not model:
            raise HTTPException(status_code=500, detail="Whisper model not loaded")

        logger.info(f"Received audio file: {audio.filename}")

        # Determine file extension
        filename = audio.filename or "recording.webm"
        file_ext = os.path.splitext(filename)[1] or ".webm"

        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            content = await audio.read()
            tmp.write(content)
            temp_path = tmp.name

        file_size = os.path.getsize(temp_path)
        logger.info(f"Temp file saved: {temp_path}, size: {file_size} bytes")

        logger.info("Transcribing audio...")
        try:
            started = time.perf_counter()
            text, info = await asyncio.wait_for(
                asyncio.to_thread(_transcribe_file, temp_path),
                timeout=TRANSCRIBE_TIMEOUT_SECONDS,
            )
            elapsed = time.perf_counter() - started
            logger.info(
                f"Transcription complete in {elapsed:.2f}s: '{text}' (language: {info.language})"
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Transcription timed out after {TRANSCRIBE_TIMEOUT_SECONDS}s"
            )
            raise HTTPException(
                status_code=504,
                detail=f"Transcription timed out after {TRANSCRIBE_TIMEOUT_SECONDS}s",
            )
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

        return {"text": text}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in voice endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Cleanup
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"Cleaned up temp file: {temp_path}")
            except Exception as e:
                logger.warning(f"Could not delete temp file: {e}")
