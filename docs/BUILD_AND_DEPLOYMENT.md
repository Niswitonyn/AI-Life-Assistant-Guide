# Build & Deployment (Portable Windows)

## Goal

Produce a single portable Windows executable:

`release/Jarvis Assistant Portable.exe`

When launched, it automatically starts:

- the bundled Python FastAPI backend
- the Electron + React frontend

## Directory / Packaging Strategy

- Backend is bundled with PyInstaller in *onedir* mode:
  - output: `backend/dist/backend/backend.exe`
- Electron Builder packages the frontend and includes the backend folder as `extraResources`:
  - packaged location: `<app>/resources/backend/backend.exe`
- On portable builds, runtime data is stored next to the portable EXE:
  - `<portableRoot>/data` (SQLite DB, tokens, RAG store, documents)
  - `<portableRoot>/logs` (backend/voice/system/memory/rag logs)
  - `<portableRoot>/downloads`

Electron sets environment variables for the backend:

- `AI_LIFE_DATA_DIR` -> `<portableRoot>/data`
- `AI_LIFE_LOG_DIR` -> `<portableRoot>/logs`
- `AI_LIFE_DOWNLOAD_DIR` -> `<portableRoot>/downloads`
- `API_PORT` (optional)

## Build (One Command)

From `ai-life-assistant/`:

```powershell
.\build-full-installer.ps1
```

Outputs:

- `ai-life-assistant/release/Jarvis Assistant Portable.exe`

## Manual Build Steps

### 1) Backend (PyInstaller)

```powershell
cd ai-life-assistant\backend
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
.venv\Scripts\pip.exe install pyinstaller
.venv\Scripts\pyinstaller.exe jarvis-backend.spec --clean
```

Verify:

- `backend/dist/backend/backend.exe`

Entry point:

- `backend/start_backend.py`

### 2) Frontend (Vite + Electron Builder)

```powershell
cd ai-life-assistant\frontend
npm ci
npm run build:renderer
npm run dist:win
```

Portable output:

- `frontend/release/*.exe`

## Runtime Troubleshooting

### Backend fails to start

- The splash screen shows an error if `/health` does not become ready.
- Check logs in:
  - `<portableRoot>/logs/backend-stdout.log`
  - `<portableRoot>/logs/backend-stderr.log`
  - `<portableRoot>/logs/backend.log` (if configured)

### Wrong API port

- Default is `8000`.
- Set `API_PORT` (and update `VITE_API_URL` at build time if needed).

### Data not persisting

- Confirm `AI_LIFE_DATA_DIR` is set (Electron sets it automatically for portable).
- Confirm `<portableRoot>/data` is writable.

## Key Files

- Backend entry point: `backend/start_backend.py`
- PyInstaller spec: `backend/jarvis-backend.spec`
- Electron launcher: `frontend/electron.js`
- Electron Builder config: `frontend/package.json` (`build.extraResources`)
- Full build script: `build-full-installer.ps1`

