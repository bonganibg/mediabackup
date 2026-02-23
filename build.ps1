## Build mediabackup.exe using PyInstaller
## Run from the project root in PowerShell:
##   .\build.ps1

$ErrorActionPreference = "Stop"
$BuildVenv = ".build-venv-win"

# Create build venv if it doesn't exist
if (-not (Test-Path "$BuildVenv\Scripts\python.exe")) {
    Write-Host "Creating build venv..." -ForegroundColor Cyan
    python -m venv $BuildVenv
    & "$BuildVenv\Scripts\pip" install --upgrade pip
    & "$BuildVenv\Scripts\pip" install pyinstaller requests
}

Write-Host "Building mediabackup.exe..." -ForegroundColor Cyan

& "$BuildVenv\Scripts\pyinstaller" `
    --onefile `
    --name mediabackup `
    --paths src `
    src/mediabackup/cli.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Build complete: dist\mediabackup.exe" -ForegroundColor Green
} else {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}
