Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $root "frontend"

& (Join-Path $PSScriptRoot "build-backend-exe.ps1")

Write-Host "==> Building Windows installer (Electron NSIS)"
Push-Location $frontendDir
if (-not $env:GH_OWNER -or -not $env:GH_REPO) {
    $remoteUrl = git -C $root remote get-url origin 2>$null
    if ($remoteUrl -match "github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(\.git)?$") {
        if (-not $env:GH_OWNER) { $env:GH_OWNER = $Matches.owner }
        if (-not $env:GH_REPO) { $env:GH_REPO = $Matches.repo }
    }
}

if (-not $env:GH_OWNER -or -not $env:GH_REPO) {
    throw "GH_OWNER/GH_REPO are not set and could not be inferred from git remote."
}

& npm.cmd run build:renderer
& .\node_modules\.bin\electron-builder.cmd --win nsis --config.win.signAndEditExecutable=false
Pop-Location

Write-Host "Done. Installer output is in frontend/release/"
