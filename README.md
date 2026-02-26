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

## Electron Desktop

In `frontend/`:

```bash
npm run electron
```

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
