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
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $pythonExe -m pip install -r requirements.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

Write-Host "==> Stopping running backend process (if any)"
Get-Process "jarvis-backend" -ErrorAction SilentlyContinue | Stop-Process -Force

Write-Host "==> Building backend executable with PyInstaller"
& $pythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    jarvis-backend.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
Pop-Location

Write-Host "Backend executable ready at backend/dist/jarvis-backend/"
