# AI Life Assistant

Jarvis-style desktop + web assistant with FastAPI backend and React/Electron frontend.

## Stack

- Backend: FastAPI, SQLAlchemy, JWT auth, Google OAuth integrations
- Frontend: React (Vite) + Electron shell
- Data: SQLite by default (`backend/app/data/database/assistant.db`)

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm

## Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` in `backend/`:

```env
JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_EXPIRE_MINUTES=10080
GOOGLE_CLIENT_ID=your-google-oauth-web-client-id
```

Run backend:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## One-Command Workflow (CMake + Make)

From project root (`ai-life-assistant/`):

```bash
make install
make run
```

If `make` is not installed in your shell, run the equivalent commands:

```bash
cmake -DPROJECT_ROOT="%cd%" -P cmake/Install.cmake
cmake -DPROJECT_ROOT="%cd%" -P cmake/Run.cmake
```

What this does:

- `make install`: creates `backend/.venv`, installs Python requirements, installs frontend dependencies (`npm ci` when lockfile is present), and creates default `.env` files if missing.
- `make run`: starts backend (`uvicorn`) + frontend (`npm run dev`) from one command.

Optional:

```bash
make run-backend
make run-frontend
```

Use Electron separately when needed:

```bash
cd frontend
npm run start
```

Create `frontend/.env`:

```env
VITE_API_URL=http://127.0.0.1:8000
```

## Electron Desktop

In `frontend/`:

```bash
npm run electron
```

## Run Locally (Windows, Recommended)

Use 3 terminals in this exact order.

Terminal 1 (`backend`):

```powershell
cd C:\CODE\aiSYSTEMass\ai-life-assistant\backend
$env:DEBUG='false'
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 (`frontend`):

```powershell
cd C:\CODE\aiSYSTEMass\ai-life-assistant\frontend
npm run dev
```

Terminal 3 (`frontend`, Electron):

```powershell
cd C:\CODE\aiSYSTEMass\ai-life-assistant\frontend
Get-Process electron -ErrorAction SilentlyContinue | Stop-Process -Force
npm run electron
```

If Electron exits immediately, clear this env var once and restart terminals:

```powershell
[Environment]::SetEnvironmentVariable("ELECTRON_RUN_AS_NODE", $null, "User")
[Environment]::SetEnvironmentVariable("ELECTRON_RUN_AS_NODE", $null, "Process")
```

Build Windows installer:

```bash
npm run dist:win
```

Installer output is created in `frontend/release/`.

## Standalone EXE Installer (Frontend + Backend)

This build packages:
- Electron frontend
- bundled Python backend executable (`jarvis-backend.exe`)
- NSIS installer

From project root (`ai-life-assistant/`):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-win-standalone.ps1
```

Output:
- Installer: `frontend/release/*.exe`
- Unpacked app: `frontend/release/win-unpacked/`

When installed, Electron auto-starts the bundled backend on `127.0.0.1:8000`.

## Auth Flow

1. Google OAuth completes in `/api/auth/gmail/login`.
2. Backend upserts local user and issues internal JWT.
3. Frontend stores JWT in `localStorage` and sends `Authorization: Bearer <token>`.

## Security Notes

- Never commit real `backend/app/data/*` tokens, credentials, or local databases.
- Use `.env` for secrets.
- Rotate `JWT_SECRET_KEY` before production deploy.

## Architecture Maintenance

- Consolidation plan for legacy model paths: `docs/model-consolidation-plan.md`

## Auto Updates (GitHub Releases)

1. In GitHub repo settings, add:
   - `Secrets and variables` -> `Actions` -> secret `GH_TOKEN` (classic PAT with `repo` scope).
   - variables `GH_OWNER` and `GH_REPO` (your GitHub username/org and repo name).
2. Bump `version` in `frontend/package.json`.
3. Commit and push a version tag, for example:

```bash
git tag v0.2.0
git push origin v0.2.0
```

4. GitHub Actions workflow [release-desktop.yml](c:/CODE/aiSYSTEMass/ai-life-assistant/.github/workflows/release-desktop.yml) builds:
   - backend executable (PyInstaller)
   - Electron NSIS installer
   - update metadata (`latest.yml`)
   and publishes them to the GitHub Release for that tag.
5. Installed app checks on startup and auto-downloads/installs newer versions.
