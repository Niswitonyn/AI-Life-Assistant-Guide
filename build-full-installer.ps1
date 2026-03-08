# ============================================================================
# Full Build Script for Jarvis Assistant Windows Installer
# ============================================================================
# This script performs all steps to create a production-ready Windows installer
#
# Steps:
#   1. Install backend dependencies
#   2. Build backend EXE with PyInstaller
#   3. Install frontend dependencies
#   4. Build Vite renderer bundle
#   5. Package Electron + backend into NSIS installer
# ============================================================================

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Jarvis Assistant - Full Build Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# STEP 1: Install Backend Dependencies
# ============================================================================
Write-Host "[Step 1/5] Installing backend dependencies..." -ForegroundColor Yellow

Set-Location "$RootDir\backend"

# Create venv if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "  Creating Python virtual environment..." -ForegroundColor Gray
    python -m venv .venv
}

# Activate venv and install dependencies
Write-Host "  Installing Python packages..." -ForegroundColor Gray
& ".venv\Scripts\pip.exe" install -r requirements.txt --quiet
& ".venv\Scripts\pip.exe" install pyinstaller --quiet

Write-Host "  ✓ Backend dependencies installed" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 2: Build Backend EXE with PyInstaller
# ============================================================================
Write-Host "[Step 2/5] Building backend EXE with PyInstaller..." -ForegroundColor Yellow

# Clean previous builds
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

Write-Host "  Running PyInstaller..." -ForegroundColor Gray
& ".venv\Scripts\pyinstaller.exe" jarvis-backend.spec --clean

if (Test-Path "dist\jarvis-backend-single.exe") {
    $exeSize = (Get-Item "dist\jarvis-backend-single.exe").Length / 1MB
    Write-Host "  ✓ Backend EXE created: dist/jarvis-backend-single.exe ($([math]::Round($exeSize, 2)) MB)" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to create backend EXE" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ============================================================================
# STEP 3: Install Frontend Dependencies
# ============================================================================
Write-Host "[Step 3/5] Installing frontend dependencies..." -ForegroundColor Yellow

Set-Location "$RootDir\frontend"

Write-Host "  Running npm ci..." -ForegroundColor Gray
npm ci --loglevel=error

Write-Host "  ✓ Frontend dependencies installed" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 4: Build Vite Renderer Bundle
# ============================================================================
Write-Host "[Step 4/5] Building Vite renderer bundle..." -ForegroundColor Yellow

Write-Host "  Running npm run build:renderer..." -ForegroundColor Gray
npm run build:renderer

if (Test-Path "dist\index.html") {
    Write-Host "  ✓ Renderer bundle created: frontend/dist/" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to create renderer bundle" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ============================================================================
# STEP 5: Package Electron + Backend into NSIS Installer
# ============================================================================
Write-Host "[Step 5/5] Packaging Electron + backend into NSIS installer..." -ForegroundColor Yellow

Write-Host "  Running electron-builder..." -ForegroundColor Gray
npx electron-builder --win nsis --config.win.signAndEditExecutable=false

# Find the generated installer
$installer = Get-ChildItem -Path "release" -Filter "*.exe" | Select-Object -First 1

if ($installer) {
    $installerSize = $installer.Length / 1MB
    Write-Host "  ✓ Installer created: frontend/release/$($installer.Name) ($([math]::Round($installerSize, 2)) MB)" -ForegroundColor Green
} else {
    Write-Host "  ✗ Failed to create installer" -ForegroundColor Red
    exit 1
}
Write-Host ""

# ============================================================================
# BUILD COMPLETE
# ============================================================================
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "BUILD COMPLETE!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Output:" -ForegroundColor White
Write-Host "  Backend EXE: backend/dist/jarvis-backend-single.exe" -ForegroundColor White
Write-Host "  Frontend bundle: frontend/dist/" -ForegroundColor White
Write-Host "  Installer: frontend/release/$($installer.Name)" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Test the installer on a clean Windows VM" -ForegroundColor Gray
Write-Host "  2. Launch Jarvis Assistant and verify backend starts on port 8000" -ForegroundColor Gray
Write-Host "  3. Navigate through login and onboarding" -ForegroundColor Gray
Write-Host "  4. Verify API calls to http://127.0.0.1:8000 succeed" -ForegroundColor Gray
Write-Host ""

Set-Location $RootDir
