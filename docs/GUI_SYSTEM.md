# GUI System (Electron + React)

## Overview

The GUI is the primary control surface for the Jarvis assistant. It provides:

- Chat interface (typed commands + responses)
- Voice input (microphone capture -> backend -> transcript + response)
- Command/status feedback (live backend events)
- Notifications (email, document ingestion, task errors)
- Document upload + document list
- Settings panel (AI + Gmail + local UI preferences)

## Architecture

### Main UI surfaces

- `frontend/src/components/JarvisAvatar.jsx`
  - Floating orb + activity states (idle/listening/thinking/speaking)
  - Inline chat popup (renders `ChatPanel`)

- `frontend/src/components/ChatPanel.jsx`
  - Message bubbles (user vs assistant), timestamps, copy button
  - Scroll-to-bottom behavior
  - Typing indicator while waiting for backend
  - Integrates:
    - `VoiceButton`
    - `SystemStatus`
    - `Notifications`
    - `DocumentUpload` (modal)

- `frontend/src/components/SettingsPanel.jsx`
  - Setup + integrations (AI provider, Gmail OAuth)
  - UI preferences persisted in `localStorage`

## API Communication

All API calls are centralized in:

- `frontend/src/utils/apiService.js`

Key functions:

- `sendChatMessage(text)` -> `POST /api/ai/chat`
- `sendVoiceInput({ audioBlob | text })` -> `POST /api/voice/input`
- `uploadDocument(file)` -> `POST /api/documents/upload`
- `listDocuments()` -> `GET /api/documents/list`
- `getMemoryHistory()` -> `GET /memory/history`

## Events (Status + Notifications)

The frontend listens to backend events using a WebSocket client:

- `frontend/src/utils/eventService.js`
  - Connects to `GET /api/events/ws`
  - Reconnects with backoff
  - Broadcasts parsed `{type, data}` events to subscribers

Backend events include:

- `task_started`, `task_completed`, `task_error`
- `email.new`
- `document_uploaded`, `document_ingested`

`SystemStatus` shows recent events as “what Jarvis is doing”, and `Notifications` displays toast popups.

## Electron Integration

Electron runs with secure defaults:

- `nodeIntegration: false`
- `contextIsolation: true`
- `sandbox: true`
- `preload.js` exposes a minimal `window.electronAPI` surface

Backend startup is managed from:

- `frontend/electron.js`

## Notes

- Voice capture uses `MediaRecorder` and sends `audio/webm` to the backend.
- If the backend is unavailable, the UI keeps working but shows errors in chat/notifications.

