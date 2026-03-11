# AI Life Assistant - Complete Architecture Documentation

## **1. PROJECT OVERVIEW**
- **Name**: AI Life Assistant (Jarvis-style Desktop Assistant)
- **Type**: Full-stack desktop application (Electron + FastAPI)
- **Python Version**: 3.11+
- **Node.js Version**: 18+
- **Database**: SQLite (default: `backend/data/database/assistant.db`)
- **Architecture Pattern**: Microservices-lite with modular agents

---

## **2. SYSTEM ARCHITECTURE DIAGRAM**

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERACTION LAYER                   │
├─────────────────┬───────────────────┬──────────────────────────┤
│  Electron UI    │   Voice Commands  │   Chat Interface        │
│  (React/Vite)   │   (Microphone)    │   (Text Input)           │
└────────┬────────┴─────────┬─────────┴──────────────┬───────────┘
         │                  │                       │
         └──────────────────┼───────────────────────┘
                            │
                  ┌─────────▼─────────┐
                  │   FRONTEND LAYER   │  (Port 5173)
                  │  - Voice Input     │
                  │  - UI Components   │
                  │  - Settings Panel  │
                  └─────────┬─────────┘
                            │ HTTP/WebSocket (CORS enabled)
         ┌──────────────────┼───────────────────────┐
         │                  │                       │
    ┌────▼─────────┐  ┌────▼──────────┐  ┌────────▼───────┐
    │  /voice      │  │  /api/ai/chat │  │   /api/* routes│
    │  Transcribe  │  │  Command exec │  │   Auth,Tasks,  │
    │              │  │  RAG search   │  │   Settings     │
    └────┬─────────┘  └────┬──────────┘  └────────┬───────┘
         │                 │                      │
         └─────────────────┼──────────────────────┘
                          │
        ┌─────────────────▼──────────────────┐
        │    FASTAPI BACKEND (Port 8000)     │
        ├────────────────────────────────────┤
        │  Main Components:                  │
        ├────────────────────────────────────┤
        │ 1. API ROUTERS (FastAPI routes)    │
        │    - routes_ai.py        (AI chat) │
        │    - routes_auth.py      (Auth)    │
        │    - routes_tasks.py     (Tasks)   │
        │    - routes_settings.py (Settings)│
        │    - voice.py           (Voice)    │
        │    - routes_rag.py      (RAG)     │
        │                                    │
        │ 2. AGENTS (Business Logic)         │
        │    - GmailAgent ──→ Google API    │
        │    - CalendarAgent ──→ Google API │
        │    - ChromeAgent ──→ Browser ctrl │
        │    - FileAgent ──→ File system    │
        │    - ImageAgent ──→ Image gen     │
        │                                    │
        │ 3. CORE SYSTEMS                    │
        │    - Command Executor (routes_ai) │
        │    - AI Provider Factory          │
        │    - Voice Assistant Service      │
        │    - Memory Service               │
        │    - RAG Retriever                │
        │    - Personalization Engine       │
        │                                    │
        │ 4. DATABASE (SQLAlchemy ORM)      │
        │    - Users                        │
        │    - Conversations                │
        │    - Tasks                        │
        │    - Memories                     │
        │                                    │
        │ 5. SCHEDULERS                      │
        │    - ReminderScheduler (daemon)   │
        │                                    │
        │ 6. SERVICES                        │
        │    - VoiceAssistant               │
        │    - EmailNotifier                │
        │    - SystemAgent (OS control)     │
        │    - TaskAgent (task mgmt)        │
        └────────────────────────────────────┘
                          │
        ┌─────────────────┼──────────── ───┐
        │                 │                 │
    ┌───▼────┐    ┌──────▼────┐    ┌──────▼─────┐
    │ SQLite │    │  Google   │    │  AI Models │
    │   DB   │    │   APIs    │    │ (OpenAI,  │
    │        │    │(Gmail,Cal)│    │  Ollama,  │
    └────────┘    └───────────┘    │  Gemini)  │
                                    └───────────┘
```

---

## **3. DETAILED MODULE BREAKDOWN**

### **3.1 Backend Structure** (`backend/app/`)

| Module | Purpose | Key Files |
|--------|---------|-----------|
| **api/** | FastAPI route handlers | `routes_ai.py`, `routes_auth.py`, `routes_tasks.py`, `voice.py` |
| **agents/** | Agent implementations (standard interface) | `base_agent.py`, `browser_agent.py`, `gmail_agent.py`, `calendar_agent.py`, `file_agent.py`, `system_agent.py` |
| **core/** | Authentication & authorization | `auth.py` (`get_optional_current_user`) |
| **database/** | ORM models & initialization | `models.py` (User, Task, ConversationMemory), `db.py`, `init_db.py` |
| **router/** | Command routing & intent detection | `smart_router.py` (primary), `command_router.py` (legacy) |
| **automation/** | Legacy automation helpers | `task_agent.py`, `system_agent.py` (legacy) |
| **ai/** | LLM provider abstraction | `provider_factory.py`, base providers (ollama, openai, gemini) |
| **memory/** | Conversation & user memory | `memory_service.py`, `memory_manager.py`, `personalization.py` |
| **rag/** | Vector search & retrieval | `retriever.py` (semantic search over past conversations) |
| **scheduler/** | Background job scheduling | `reminder_scheduler.py` (daemon thread) |
| **voice/** | Voice I/O services | `voice_assistant.py`, `speech_to_text.py`, `text_to_speech.py` |
| **config/** | Settings & environment paths | `settings.py`, `paths.py` |

### **3.2 Frontend Structure** (`frontend/`)

| Module | Purpose | Technologies |
|--------|---------|--------------|
| **src/components/** | React UI components | React 18, Electron IPC |
| **electron.js** | Electron main process | Window management, IPC handlers |
| **vite.config.js** | Build config | Vite bundler |
| **package.json** | Dependencies & build scripts | npm, electron-builder |

---

## **4. COMMAND EXECUTION FLOW (Chat & Voice)**

### **4.1 Chat Command Flow (`/api/ai/chat`)**

```
User Input (ChatRequest)
        ↓
[1] Parse Time Commands → _handle_time_command()
    ├─ Match: "what time", "date", etc.
    └─ Return: Formatted time/date response
        ↓ [NOT MATCHED]
[2] Parse Schema → _parse_command_schema()
    ├─ Detect commands like: "send email", "open chrome", "create task"
    ├─ Split multi-clauses: "and then", comma separators
    └─ Return: {"schema": "phase3.command.v1", "commands": [...]}
        ↓ [COMMAND FOUND]
[3] Execute Commands → _execute_command_schema()
    ├─ For each command:
    │  ├─ _execute_single_action(action, params)
    │  └─ Return: action result strings
    └─ Combine results, save to memory, update RAG
        ↓ [NO COMMAND FOUND]
[4] LLM Fallback (with context)
    ├─ Retrieve recent conversation memory
    ├─ Search RAG for relevant context
    ├─ Build system prompt (personalization + profile)
    ├─ Call LLM provider
    ├─ Save conversation to DB
    └─ Update RAG with new exchange
        ↓
Return ChatResponse(response: str)
```

### **4.2 Voice Command Flow (To Be Unified)**

**Current voice_assistant.py flow:**
```
Microphone Input
        ↓
voice_assistant.listen() → Google Speech Recognition
        ↓
text = transcribed_user_input
        ↓
smart_router.route(text) → routes to gmail/email
        ↓
smart_router.classify(text) → intent detection
        ↓
command_router.execute(data) → system/browser/file actions
        ↓
If no match: ask_ai(text) → HTTP calls /api/ai/chat
        ↓
voice_assistant.speak(reply) → pyttsx3 TTS
```

**NOTE**: Voice and chat now share the same execution path via the BrainController (`POST /api/ai/chat`).

### **4.3 Unified Approach (Implemented)**

Both voice and chat:
1. Receive text input (transcribed or user-typed)
2. Call `POST /api/ai/chat` (backend BrainController)
3. BrainController runs: SmartRouter → TaskPlanner → Agent Execution → Memory/RAG updates
4. If no command is detected, BrainController falls back to the LLM chat flow
5. Returns `{"response": "<text>"}` to UI / voice TTS (frontend contract unchanged)

---

## **5. KEY EXECUTION HANDLERS**

### **Brain Controller** (`backend/app/core/brain_controller.py`)
- Unified entrypoint for chat + voice
- Runs: SmartRouter → TaskPlanner → Agent Execution → Memory/RAG updates
- Produces structured JSON task results internally while returning display text via the existing HTTP response contract

### **Smart Router** (`backend/app/router/smart_router.py`)
- Intent classification + agent mapping + command-to-action parsing
- Multi-command parsing via `TaskPlanner`

### **Task Planner** (`backend/app/core/task_planner.py`)
- Splits compound commands into ordered task clauses

### **Agent Interface** (`backend/app/agents/base_agent.py`)
- Standard async `execute(task: dict)` interface for agents

### **LLM Provider** (`ai/provider_factory.py`)
- Abstracts Ollama, OpenAI, Gemini
- Factory pattern: `get_provider(provider_name, model)`
- Async: `await provider.generate_response(messages)`

---

## **6. DEPENDENCIES & DATA FLOW**

### **External APIs**
- **Google APIs**: Gmail (send, read), Calendar (list events)
- **LLM APIs**: OpenAI, Gemini, Local Ollama
- **System APIs**: Windows system commands (shutdown, lock, volume)
- **Whisper**: Voice transcription (local via `faster-whisper`)

### **Data Storage**
- **SQLite Database** (`data/database/assistant.db`):
  - Users
  - Conversations (for chat history)
  - Tasks
  - Memories
- **JSON Files** (`data/`):
  - `credentials.json` → Google OAuth tokens
  - `rag_store.json` → Vector embeddings for RAG
  - `pubsub_users.json` → Gmail webhook user mappings

### **Configuration**
- `.env` file (backend root):
  ```
  JWT_SECRET_KEY=...
  JWT_EXPIRE_MINUTES=10080
  GOOGLE_CLIENT_ID=...
  AI_LIFE_DATA_DIR=...  (optional override)
  ```

---

## **7. MULTI-USER ARCHITECTURE**

- **Default user**: `"default"`
- **Multi-user support**: Each request includes `user_id`
- **Gmail webhook routing**: `main.py` `/gmail/webhook` → maps to specific user
- **Database isolation**: All queries filtered by `user_id`
- **Email notification**: Per-user `GmailAgent` instance

---

## **8. KEY ENTRY POINTS**

| Entry Point | Role |
|-------------|------|
| `backend/app/main.py` | FastAPI app initialization, lifespan, route registration |
| `backend/run_packaged_backend.py` | CLI entry for standalone exe |
| `frontend/electron.js` | Electron main process (window, IPC) |
| `frontend/src/main.jsx` | React app root |
| `backend/app/voice/voice_assistant.py` | Standalone voice CLI |

---

## **9. CONFIGURATION & ENVIRONMENT**

### **Startup Sequence**
1. Python venv created (if missing)
2. Requirements installed
3. Frontend dependencies installed (npm)
4. `.env` file created (if missing)
5. Database initialized (`init_db()`)
6. Scheduler daemon started
7. FastAPI server starts on port 8000
8. Frontend (Vite) starts on port 5173
9. Electron loads Vite dev server

### **Environment Variables**
- `JWT_SECRET_KEY` → JWT token signing
- `JWT_EXPIRE_MINUTES` → Token lifetime
- `GOOGLE_CLIENT_ID` → OAuth client ID
- `AI_LIFE_DATA_DIR` → Custom data directory (default: `backend/data/`)
- `WHISPER_MODEL_SIZE` → Model size: tiny.en, base.en, small.en (default: tiny.en)
- `VOICE_TRANSCRIBE_TIMEOUT_SECONDS` → Timeout for voice (default: 20)

---

## **10. KNOWN ISSUES & IMPROVEMENTS**

### **Current Issues**
1. **Some agent actions are synchronous**: long-running tasks can block the request thread
2. **Image search endpoints can be rate-limited**: consider adding retries/backoff or a provider-backed approach
3. **Limited test coverage**: task splitting and routing are not yet unit tested

### **Recommendations**
1. **Add tests**: unit tests for `TaskPlanner.split()` and `SmartRouter.route()`
2. **Async IO**: make network-heavy agent calls fully async (or move to background jobs)
3. **Observability**: add structured logging around task execution and failures

---

## **11. BUILD & DEPLOYMENT**

### **Development**
```bash
make install      # Setup venv, npm, .env
make run          # Start backend + frontend
```

### **Production (Standalone .exe)**
```bash
# PyInstaller for backend
pyinstaller --onefile backend/run_packaged_backend.py -o build/

# Electron-builder for frontend
cd frontend
npm run dist:win  # Builds NSIS installer + portable exe
```

The `.exe` can run independently on Windows without Python/Node installed.

---

## **STATUS: IMPLEMENTED (BrainController Unification)**

This architecture supports:
- ✅ Multi-user isolation
- ✅ Command execution (system, email, calendar, browser, files)
- ✅ AI fallback with context (RAG + memory + personalization)
- ✅ Voice & chat interfaces (unified via BrainController)
- ✅ Standalone Windows executable
