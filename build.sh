#!/bin/bash
## Build mediabackup.exe using Nuitka
## Run from the project root:
##   bash build.sh

set -e

BUILD_VENV=".build-venv-win"

# Create build venv if it doesn't exist
if [ ! -f "$BUILD_VENV/Scripts/python.exe" ]; then
    echo "Creating build venv..."
    python -m venv "$BUILD_VENV"
    "$BUILD_VENV/Scripts/pip" install --upgrade pip
    "$BUILD_VENV/Scripts/pip" install nuitka requests
fi

echo "Building mediabackup.exe..."

PYTHONPATH=src "$BUILD_VENV/Scripts/python" -m nuitka \
    --mode=onefile \
    --follow-imports \
    --include-package=mediabackup \
    --include-package=requests \
    --include-package=charset_normalizer \
    --include-package=certifi \
    --include-package=urllib3 \
    --include-package=idna \
    --include-package-data=certifi \
    --output-dir=dist \
    --output-filename=mediabackup.exe \
    src/mediabackup/cli.py

echo ""
echo "Build complete: dist/mediabackup.exe"
