# Project Architecture (Jarvis Assistant)

This repository is a modular Jarvis-style desktop assistant that ships as a portable Windows Electron app with an embedded Python FastAPI backend.

## High-Level Data Flow (Chat + Voice)

All user input (chat or voice transcript) goes through the same “brain” pipeline:

1. **Frontend** (Electron + React)
   - User types a message or uses the mic button
   - UI connects to backend via HTTP + WebSocket events
2. **Backend API** (FastAPI)
   - Receives user input and forwards to `BrainController`
3. **BrainController**
   - Applies security + confirmation flow
   - Uses `SmartRouter` and `ReasoningEngine` to interpret intent
   - Uses `TaskPlanner` for multi-step commands
   - Uses `TaskExecutor` to run steps sequentially and publish progress events
4. **Agents**
   - Execute scoped actions (browser, gmail, system, file, document)
5. **Memory + RAG**
   - Conversation and interactions stored in SQLite
   - Optional semantic memory + document RAG context used for responses
6. **Response**
   - Structured result returned to the API caller
   - Events published for UI status/notifications

## Backend Modules

**Core orchestration**
- `backend/app/core/brain_controller.py`: unified controller for chat + voice transcripts
- `backend/app/router/smart_router.py`: rule-based routing for common commands + task-chain helpers
- `backend/app/core/reasoning_engine.py`: intent reasoning for ambiguous/complex inputs
- `backend/app/core/task_planner.py`: splits natural language into ordered tasks
- `backend/app/core/task_executor.py`: executes tasks sequentially with progress events

**Agents**
- `backend/app/agents/browser_agent.py`: browser automation tasks
- `backend/app/agents/gmail_agent.py`: Gmail read/search/send flows
- `backend/app/agents/system_agent.py`: Windows PC control (apps, lock, shutdown, volume, folders)
- `backend/app/agents/file_agent.py`: safe filesystem operations (search/open/create/delete/list)
- `backend/app/agents/document_agent.py`: document list/summarize/Q&A using the RAG pipeline

**Security**
- `backend/app/security/security_manager.py`: SAFE/SENSITIVE/CRITICAL validation + path restrictions
- `backend/app/security/confirmation_service.py`: confirmation gating for sensitive/critical tasks

**Memory + learning**
- `backend/app/memory/*`: conversation + long-term memory persistence
- `backend/app/learning/*`: behavior tracking, preferences, and suggestion generation

**RAG (Personal Knowledge System)**
- `backend/app/rag/document_processor.py`: extract + chunk documents
- `backend/app/rag/embeddings.py`: local embedding implementation (hash-based)
- `backend/app/rag/vector_store.py`: local JSON-backed vector store
- `backend/app/rag/retriever.py`: similarity retrieval with filters

**Monitoring**
- `backend/app/monitoring/health_monitor.py`: periodic health checks + recovery
- `backend/app/monitoring/performance_metrics.py`: API/task timings + process stats (best-effort)
- `backend/app/monitoring/alert_manager.py`: alert emission to UI

**Events**
- `backend/app/services/event_bus.py`: in-process async event bus
- `backend/app/api/routes_events.py`: WebSocket/SSE event stream to the frontend

## Frontend Architecture

**Core UI pieces**
- `frontend/src/components/ChatPanel.jsx`: chat UI, typing indicator, upload + voice integrations
- `frontend/src/components/VoiceButton.jsx`: mic recording + `/api/voice/input`
- `frontend/src/components/SystemStatus.jsx`: live status + health badge (events + polling fallback)
- `frontend/src/components/Notifications.jsx`: toast notifications from backend events
- `frontend/src/components/DocumentUpload.jsx`: uploads to `/api/documents/upload`

**API + events**
- `frontend/src/utils/apiService.js`: central HTTP API client
- `frontend/src/utils/eventService.js`: WebSocket client with reconnect

## API Surface (Key Endpoints)

- Chat: `POST /api/ai/chat`
- Voice (text or audio): `POST /api/voice/input` (and legacy `POST /voice/input`)
- Documents: `POST /api/documents/upload`, `GET /api/documents/list`
- Events: `WS /api/events/ws` (and SSE `GET /api/events/stream`)
- Health: `GET /api/system/health`

## Portable Windows Build Layout

Electron launches the bundled backend executable and sets environment variables for portable paths:
- `AI_LIFE_DATA_DIR`
- `AI_LIFE_LOG_DIR`
- `AI_LIFE_DOWNLOAD_DIR`

These are used by backend path helpers (see `backend/app/config/paths.py`) so data/logs are written next to the portable executable rather than inside the app install directory.

