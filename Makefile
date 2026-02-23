PYTHON_BUILD := python3.12
BUILD_VENV := .build-venv
NUITKA := $(BUILD_VENV)/bin/python -m nuitka
OUTPUT := dist/mediabackup

.PHONY: build clean setup dev

# Create the build venv with nuitka and project deps
setup:
	$(PYTHON_BUILD) -m venv $(BUILD_VENV)
	$(BUILD_VENV)/bin/pip install --upgrade pip
	$(BUILD_VENV)/bin/pip install nuitka requests

# Build the standalone executable
build: setup
	PYTHONPATH=src $(NUITKA) \
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
		--output-filename=mediabackup \
		src/mediabackup/cli.py
	@echo ""
	@echo "Build complete: $(OUTPUT)"

# Install in dev venv (editable mode)
dev:
	venv/bin/pip install -e .

# Remove build artifacts
clean:
	rm -rf dist/ build/ $(BUILD_VENV)
	rm -rf src/mediabackup/cli.build src/mediabackup/cli.dist src/mediabackup/cli.onefile-build
