# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AI Life Assistant Backend (Standalone Windows EXE)

This creates a single-file executable that includes:
- FastAPI server with all dependencies
- SQLite database
- configuration files
- data directories

Build command:
    pyinstaller jarvis-backend.spec

The resulting executable will be in:
    dist/jarvis-backend-single.exe
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# ============================================================================
# HIDDEN IMPORTS (Required for proper functioning)
# ============================================================================

hiddenimports = [
    # FastAPI & ASGI
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'multipart',
    
    # Collect all app submodules automatically
    'app',
    'app.api',
    'app.agents',
    'app.ai',
    'app.automation',
    'app.config',
    'app.core',
    'app.database',
    'app.memory',
    'app.models',
    'app.notifications',
    'app.rag',
    'app.router',
    'app.scheduler',
    'app.security',
    'app.services',
    'app.voice',
    
    # Google APIs
    'google.auth',
    'google.oauth2',
    'googleapiclient',
    'google_auth_oauthlib',
    'google.generativeai',
    
    # AI providers
    'openai',
    
    # Speech
    'speech_recognition',
    'faster_whisper',
    'pyttsx3',
]

hiddenimports += collect_submodules('app')

backend_dir = Path(SPECPATH).resolve()

# ============================================================================
# DATA FILES
# ============================================================================

datas = [
    (str(backend_dir / 'app'), 'app'),
    (str(backend_dir / 'alembic.ini'), '.') if (backend_dir / 'alembic.ini').exists() else None,
]
datas = [d for d in datas if d is not None]

# ============================================================================
# ANALYSIS
# ============================================================================

a = Analysis(
    ['run_packaged_backend.py'],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# ============================================================================
# PYZ (Python Archive)
# ============================================================================

pyz = PYZ(a.pure)

# ============================================================================
# EXECUTABLE (Single file)
# ============================================================================

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='jarvis-backend-single',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Uncomment below for multi-file distribution (folder instead of single .exe)
# coll = COLLECT(
#     exe,
#     a.binaries,
#     a.datas,
#     strip=False,
#     upx=True,
#     upx_exclude=[],
#     name='jarvis-backend',
)
