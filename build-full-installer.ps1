# ============================================================================
# Full Build Script for Jarvis Assistant Portable (Windows)
# ============================================================================
# Produces:
#   release/Jarvis Assistant Portable.exe
#
# Steps:
#   1) Install backend deps into backend/.venv
#   2) Build backend (PyInstaller onedir) -> backend/dist/backend/backend.exe
#   3) Install frontend deps (npm ci)
#   4) Build renderer (vite) -> frontend/dist/
#   5) Build Electron portable -> frontend/release/*.exe
#   6) Copy/rename final artifact -> release/Jarvis Assistant Portable.exe

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Jarvis Assistant - Full Portable Build" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------------------------------------------
# STEP 1: Backend deps
# ----------------------------------------------------------------------------
Write-Host "[Step 1/6] Installing backend dependencies..." -ForegroundColor Yellow
Set-Location "$RootDir\\backend"

if (-not (Test-Path ".venv")) {
    Write-Host "  Creating Python virtual environment..." -ForegroundColor Gray
    python -m venv .venv
}

Write-Host "  Installing Python packages..." -ForegroundColor Gray
& ".venv\\Scripts\\pip.exe" install -r requirements.txt --quiet
& ".venv\\Scripts\\pip.exe" install --upgrade pyinstaller --quiet
Write-Host "  ✓ Backend dependencies installed" -ForegroundColor Green
Write-Host ""

# ----------------------------------------------------------------------------
# STEP 2: Backend EXE
# ----------------------------------------------------------------------------
Write-Host "[Step 2/6] Building backend (PyInstaller)..." -ForegroundColor Yellow

if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue }

Write-Host "  Running PyInstaller..." -ForegroundColor Gray
& ".venv\\Scripts\\pyinstaller.exe" jarvis-backend.spec --clean

$BackendExe = "dist\\backend\\backend.exe"
if (-not (Test-Path $BackendExe)) {
    Write-Host "  ✗ Failed to create backend EXE ($BackendExe not found)" -ForegroundColor Red
    exit 1
}
$ExeSize = (Get-Item $BackendExe).Length / 1MB
Write-Host "  ✓ Backend EXE created: $BackendExe ($([math]::Round($ExeSize, 2)) MB)" -ForegroundColor Green
Write-Host ""

# ----------------------------------------------------------------------------
# STEP 3: Frontend deps
# ----------------------------------------------------------------------------
Write-Host "[Step 3/6] Installing frontend dependencies..." -ForegroundColor Yellow
Set-Location "$RootDir\\frontend"
Write-Host "  Running npm ci..." -ForegroundColor Gray
npm ci --loglevel=error
Write-Host "  ✓ Frontend dependencies installed" -ForegroundColor Green
Write-Host ""

# ----------------------------------------------------------------------------
# STEP 4: Renderer build
# ----------------------------------------------------------------------------
Write-Host "[Step 4/6] Building renderer (vite)..." -ForegroundColor Yellow
npm run build:renderer

if (-not (Test-Path "dist\\index.html")) {
    Write-Host "  ✗ Failed to build renderer (frontend/dist/index.html not found)" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Renderer bundle created: frontend/dist/" -ForegroundColor Green
Write-Host ""

# ----------------------------------------------------------------------------
# STEP 5: Electron portable
# ----------------------------------------------------------------------------
Write-Host "[Step 5/6] Building Electron portable..." -ForegroundColor Yellow

if (Test-Path "release") { Remove-Item -Recurse -Force "release" -ErrorAction SilentlyContinue }

npm run dist:win

$Portable = Get-ChildItem -Path "release" -Filter "*.exe" | Select-Object -First 1
if (-not $Portable) {
    Write-Host "  ✗ Portable EXE not found in frontend/release/" -ForegroundColor Red
    exit 1
}
$PortableSize = $Portable.Length / 1MB
Write-Host "  ✓ Portable created: frontend/release/$($Portable.Name) ($([math]::Round($PortableSize, 2)) MB)" -ForegroundColor Green
Write-Host ""

# ----------------------------------------------------------------------------
# STEP 6: Copy final artifact
# ----------------------------------------------------------------------------
Write-Host "[Step 6/6] Copying final artifact..." -ForegroundColor Yellow
$FinalDir = Join-Path $RootDir "release"
New-Item -ItemType Directory -Force -Path $FinalDir | Out-Null
$FinalExe = Join-Path $FinalDir "Jarvis Assistant Portable.exe"
Copy-Item -Force $Portable.FullName $FinalExe
Write-Host "  ✓ Final artifact: $FinalExe" -ForegroundColor Green
Write-Host ""

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "BUILD COMPLETE" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Backend: backend/dist/backend/backend.exe" -ForegroundColor White
Write-Host "Frontend: frontend/release/$($Portable.Name)" -ForegroundColor White
Write-Host "Final:   release/Jarvis Assistant Portable.exe" -ForegroundColor White

Set-Location $RootDir

