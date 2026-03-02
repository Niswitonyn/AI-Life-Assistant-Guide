Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root "backend"
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "==> Creating backend virtual environment"
    Push-Location $backendDir
    python -m venv .venv
    Pop-Location
}

$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"

Write-Host "==> Installing backend dependencies"
Push-Location $backendDir
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r requirements.txt pyinstaller

Write-Host "==> Building backend executable with PyInstaller"
& $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name jarvis-backend `
    --paths "$backendDir" `
    --collect-submodules app `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets.auto `
    run_packaged_backend.py
Pop-Location

Write-Host "Backend executable ready at backend/dist/jarvis-backend/"

