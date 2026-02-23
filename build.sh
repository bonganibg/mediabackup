#!/bin/bash
## Build mediabackup.exe using PyInstaller
## Run from the project root on Windows (Git Bash):
##   bash build.sh

set -e

BUILD_VENV=".build-venv-win"

# Create build venv if it doesn't exist
if [ ! -f "$BUILD_VENV/Scripts/python.exe" ]; then
    echo "Creating build venv..."
    python -m venv "$BUILD_VENV"
    "$BUILD_VENV/Scripts/pip" install --upgrade pip
    "$BUILD_VENV/Scripts/pip" install pyinstaller requests
fi

echo "Building mediabackup.exe..."

"$BUILD_VENV/Scripts/pyinstaller" \
    --onefile \
    --name mediabackup \
    --paths src \
    src/mediabackup/cli.py

echo ""
echo "Build complete: dist/mediabackup.exe"
