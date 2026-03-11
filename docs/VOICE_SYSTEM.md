# Voice System

## Goal

Support voice and chat through the same backend “brain” pipeline:

`User Input` -> `BrainController` -> `SmartRouter` -> `TaskPlanner` -> `Agents` -> `Response`

Voice differs only in how input is captured (audio -> transcript) and how output is played (TTS).

## Backend Modules

- `backend/app/voice/speech_to_text.py`
  - Offline transcription using `faster-whisper`
  - Supports microphone capture (`transcribe_microphone`) and uploaded audio bytes (`transcribe_audio_bytes_async`)
  - Returns `{"text": "...", "confidence": 0.xx}`

- `backend/app/voice/text_to_speech.py`
  - Non-blocking TTS wrapper around `pyttsx3`
  - `speak(text)` enqueues playback; `stop_speaking()` cancels

- `backend/app/voice/voice_controller.py`
  - Orchestrates STT -> `BrainController.handle_text(source="voice")` -> optional TTS
  - Produces a structured `VoiceResponse` (transcript, confidence, response_text, tasks, latency)

- `backend/app/voice/wake_word_detector.py` (optional)
  - Background thread detecting wake words like “Jarvis”

## API

- `POST /voice/input` (also available as `/api/voice/input`)
  - Accepts:
    - JSON: `{ "text": "open chrome" }` or `{ "audio_base64": "...", "filename": "recording.webm" }`
    - multipart/form-data: `audio=<file>`
  - Returns:
    - `transcript`, `confidence`, `response_text`, `tasks`, `latency_ms`
  - All conversations are stored in the same memory tables with `source="voice"`.

- `POST /api/voice`
  - Legacy compatibility endpoint used by older frontend flows
  - Returns transcript only: `{ "text": "..." }`

## Frontend

- `frontend/src/components/JarvisAvatar.jsx`
  - Uses Web Speech API when available
  - Falls back to recording `audio/webm` and sending to `POST /api/voice/input`
  - For voice text transcripts, calls `POST /api/voice/input` (so voice is tagged as `source="voice"`)

## Logging

Voice events are logged as JSON to:

- `backend/data/logs/voice.log`
- `backend/logs/voice.log` (compat)

Fields include transcript, confidence, latency, and errors.
