# AI Life Assistant Development Startup Script
Stop-Process -Name "node" -ErrorAction SilentlyContinue
Stop-Process -Name "python" -ErrorAction SilentlyContinue

Write-Host "Starting AI Life Assistant Development Environment..." -ForegroundColor Cyan

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$baseDir = Split-Path -Parent $baseDir

# 1. Start FastApi Backend
$backendDir = Join-Path $baseDir "backend"
Write-Host "Starting Backend in $backendDir" -ForegroundColor Yellow
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "cd '$backendDir'; & .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload" -WindowStyle Normal -WorkingDirectory $backendDir

# 2. Start React/Electron Frontend (npm start uses concurrently)
$frontendDir = Join-Path $baseDir "frontend"
Write-Host "Starting Frontend in $frontendDir" -ForegroundColor Yellow
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "npm start" -WindowStyle Normal -WorkingDirectory $frontendDir

Write-Host "✅ Dev Environment Launched successfully!" -ForegroundColor Green
