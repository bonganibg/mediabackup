## Build mediabackup.exe using Nuitka
## Run from the project root in PowerShell:
##   .\build.ps1

$ErrorActionPreference = "Stop"
$BuildVenv = ".build-venv-win"

# Create build venv if it doesn't exist
if (-not (Test-Path "$BuildVenv\Scripts\python.exe")) {
    Write-Host "Creating build venv..." -ForegroundColor Cyan
    python -m venv $BuildVenv
    & "$BuildVenv\Scripts\pip" install --upgrade pip
    & "$BuildVenv\Scripts\pip" install nuitka requests
}

Write-Host "Building mediabackup.exe..." -ForegroundColor Cyan

$env:PYTHONPATH = "src"

& "$BuildVenv\Scripts\python" -m nuitka `
    --mode=onefile `
    --follow-imports `
    --include-package=mediabackup `
    --include-package=requests `
    --include-package=charset_normalizer `
    --include-package=certifi `
    --include-package=urllib3 `
    --include-package=idna `
    --include-package-data=certifi `
    --output-dir=dist `
    --output-filename=mediabackup.exe `
    src/mediabackup/cli.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Build complete: dist\mediabackup.exe" -ForegroundColor Green
} else {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}
