# AI Life Assistant - Complete Command Reference

## **Quick Start (Development)**

```bash
# From project root: ai-life-assistant/

# Step 1: Setup (one-time)
cmake -DPROJECT_ROOT="%cd%" -P cmake/Install.cmake

# Step 2: Run everything
cmake -DPROJECT_ROOT="%cd%" -P cmake/Run.cmake
```

**Or with Make (if available):**
```bash
make install
make run
```

---

## **Backend Commands**

### **Setup & Installation**

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Activate virtual environment (Unix/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
copy .env.example .env
# -- Edit .env with your configuration ---
```

### **Database Initialization**

```bash
cd backend

# Initialize database (automatic on first app run)
python -c "from app.database.init_db import init_db; init_db()"

# View database schema
sqlite3 data/database/assistant.db ".schema"

# Clear database (reset to empty)
rm data/database/assistant.db
```

### **Running the Backend**

```bash
cd backend

# Development (with auto-reload)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Production (no reload)
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
```

### **Testing**

```bash
cd backend

# Run all tests (verbose output)
python run_tests.py

# Run with coverage report
python run_tests.py --coverage
# View report: open htmlcov/index.html

# Run specific test file
python run_tests.py --specific test_command_schema.py

# Run quick tests only (skip integration tests)
python run_tests.py --quick

# Run pytest directly
pytest tests/
pytest tests/test_command_schema.py -v
pytest tests/ --cov=app --cov-report=html
```

### **Building Backend Executable**

```bash
cd backend

# Option 1: Quick build (backend EXE only)
# From project root:
.\build-backend-exe.ps1

# Option 2: Build with PyInstaller directly
pip install pyinstaller
python -m PyInstaller jarvis-backend.spec --clean

# Output location
# dist/jarvis-backend-single.exe
```

### **Running Standalone Backend EXE**

```bash
cd backend/dist

# Run the standalone .exe
jarvis-backend-single.exe
# Will start on http://127.0.0.1:8000
```

### **Voice Assistant (Standalone)**

```bash
cd backend

# Run voice CLI interface
python app/voice/voice_assistant.py
# Starts listening and speaking via microphone
```

---

## **Frontend Commands**

### **Setup & Installation**

```bash
cd frontend

# Install dependencies
npm install
# or for locked versions:
npm ci

# Create .env file
echo VITE_API_URL=http://127.0.0.1:8000 > .env
```

### **Development Server**

```bash
cd frontend

# Start Vite dev server (port 5173)
npm run dev
# Accessible at http://localhost:5173

# Stop: Ctrl+C
```

### **Building (Desktop)**

```bash
cd frontend

# Build static assets
npm run build:renderer
# Output: dist/

# Run standalone Electron app (requires backend running)
npm run electron
# or
npm run electron:dev

# Run both together (concurrent)
npm start
# Starts Vite dev server + Electron windows
```

### **Building Installer**

```bash
cd frontend

# Build Windows NSIS installer
npm run dist:win
# Output: release/Jarvis Assistant Setup *.exe

# Portable executable (no installer)
npm run dist:win:standalone
# Output: release/win-unpacked/
```

### **Full Build (Backend + Frontend)**

```bash
# From project root
.\build-win-standalone.ps1

# With options
.\build-win-standalone.ps1 -BackendOnly      # Just backend .exe
.\build-win-standalone.ps1 -FrontendOnly     # Just Electron installer
.\build-win-standalone.ps1 -NoClean          # Skip cleanup
```

---

## **API Endpoints**

### **Health Check**

```bash
curl http://127.0.0.1:8000/health
# Response: {"status": "healthy"}

curl http://127.0.0.1:8000/
# Response: {"message": "AI Life Assistant Backend Running"}
```

### **Chat (Main Endpoint)**

```bash
# Send chat message
curl -X POST http://127.0.0.1:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "default",
    "provider": "ollama",
    "model": "llama3",
    "messages": [
      {"role": "user", "content": "What time is it?"}
    ]
  }'

# Response:
# {"response": "It is 2:45 PM on Wednesday, March 05, 2025 (PST)."}
```

### **Voice Transcription**

```bash
# Upload audio file and transcribe
curl -X POST http://127.0.0.1:8000/voice \
  -F "audio=@voice_recording.webm"

# Response:
# {"text": "What are my upcoming events?"}
```

### **Chat (Voice Input)**

```bash
# Combine voice transcription + chat
# 1. POST to /voice to get text
# 2. POST that text to /api/ai/chat

# After getting voice text:
curl -X POST http://127.0.0.1:8000/api/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "default",
    "messages": [
      {"role": "user", "content": "What are my upcoming events?"}
    ]
  }'
```

### **List Available Models**

```bash
curl "http://127.0.0.1:8000/api/ai/models?provider=ollama"
# Response:
# {"models": ["llama3", "mistral", "neural-chat", ...]}
```

### **Provider Health**

```bash
curl "http://127.0.0.1:8000/api/ai/health?provider=ollama"
# Response:
# {"healthy": true}
```

---

## **Database Commands**

### **SQLite Operations**

```bash
cd backend/data/database

# Open database shell
sqlite3 assistant.db

# View all tables
.tables

# View table schema
.schema users
.schema conversation_memory
.schema tasks

# Query examples
SELECT COUNT(*) as user_count FROM users;
SELECT * FROM conversation_memory WHERE user_id='default' LIMIT 10;
SELECT * FROM tasks WHERE completed=0;

# Export data
.mode csv
.output backup.csv
SELECT * FROM conversation_memory;
.quit
```

### **Database Export/Backup**

```bash
# Backup entire database
cp backend/data/database/assistant.db backend/data/database/assistant.db.backup

# Dump to SQL file
sqlite3 backend/data/database/assistant.db ".dump" > backup.sql

# Restore from dump
sqlite3 backend/data/database/assistant.db < backup.sql
```

---

## **Troubleshooting Commands**

### **Check Python Setup**

```bash
python --version
# Should be 3.11 or higher

python -m venv --help
# Should work

python -c "import fastapi; print(fastapi.__version__)"
# Should print version (checks if dependencies installed)
```

### **Check Node.js Setup**

```bash
node --version
# Should be 18 or higher

npm --version
# Should be 8 or higher
```

### **Check Ports**

```bash
# Windows: Check if port 8000 is in use
netstat -an | findstr "8000"

# Windows: Check if port 5173 is in use
netstat -an | findstr "5173"

# Kill process on port 8000
taskkill /F /PID <PID>
```

### **Test Audio Devices**

```bash
# Python: Test speech recognition
python -c "import speech_recognition as sr; print(sr.Microphone().list_microphone_indexes())"

# Python: Test text-to-speech
python -c "import pyttsx3; e = pyttsx3.init(); e.say('Hello'); e.runAndWait()"
```

### **View Logs**

```bash
# Backend logs appear in terminal where uvicorn runs

# View log files
type backend\data\logs\*.log

# View latest activity
tail -f backend/data/logs/*.log  # (Unix/Git Bash)
```

---

## **Configuration Files**

### **Backend Configuration**

- `.env` → Environment variables (JWT, Google OAuth, API keys)
- `.env.example` → Template for .env
- `alembic.ini` → Database migration configuration
- `requirements.txt` → Python package dependencies

### **Frontend Configuration**

- `.env` → Frontend environment (API_URL)
- `vite.config.js` → Vite build configuration
- `package.json` → Dependencies and scripts
- `electron.js` → Electron main process setup

### **Build Configuration**

- `CMakeLists.txt` → CMake build system
- `jarvis-backend.spec` → PyInstaller configuration
- `build-backend-exe.ps1` → Backend build script
- `build-win-standalone.ps1` → Full build script

---

## **Project Structure Reference**

```
ai-life-assistant/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API routes (ai, auth, voice, tasks...)
│   │   ├── agents/            # Gmail, Calendar, Browser, File agents
│   │   ├── ai/                # LLM provider abstraction
│   │   ├── database/          # SQLAlchemy models & init
│   │   ├── memory/            # Conversation memory & personalization
│   │   ├── voice/             # Voice transcription & synthesis
│   │   ├── router/            # Command routing logic
│   │   ├── config/            # Settings & paths
│   │   └── ...
│   ├── tests/                 # Unit tests (pytest)
│   ├── data/                  # Runtime data (database, tokens, logs)
│   ├── requirements.txt       # Python dependencies
│   ├── .env.example          # Configuration template
│   ├── jarvis-backend.spec   # PyInstaller config
│   └── run_tests.py          # Test runner
│
├── frontend/                   # React + Electron
│   ├── src/
│   │   ├── components/        # React components
│   │   └── ...
│   ├── electron.js           # Electron main
│   ├── package.json          # Dependencies & scripts
│   ├── vite.config.js        # Vite configuration
│   └── release/              # Built installers
│
├── cmake/                      # CMake scripts
├── scripts/                    # Build scripts
├── build/                      # CMake build output
└── docs/                       # Documentation
```

---

## **Environment Setup Checklist**

- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed
- [ ] Git installed (for version control)
- [ ] Virtual environment created: `python -m venv .venv`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` configured with JWT_SECRET_KEY and GOOGLE_CLIENT_ID
- [ ] Google OAuth credentials downloaded (credentials.json)
- [ ] Database initialized: `python -c "from app.database.init_db import init_db; init_db()"`
- [ ] Frontend dependencies: `cd frontend && npm install`
- [ ] Tests passing: `python run_tests.py`
- [ ] Backend running: `uvicorn app.main:app --reload`
- [ ] Frontend running: `npm run dev`

---

## **Distribution Checklist**

- [ ] All tests passing
- [ ] Backend .exe built: `.\build-backend-exe.ps1`
- [ ] Frontend installer built: `npm run dist:win`
- [ ] Both executables tested on clean Windows 10/11 system
- [ ] .env.example included in distribution
- [ ] README with setup instructions included
- [ ] Google OAuth setup guide provided
- [ ] Known issues documented
- [ ] Version number updated
- [ ] Release notes created
