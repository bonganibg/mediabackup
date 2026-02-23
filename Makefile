BUILD_VENV := .build-venv
OUTPUT := dist/mediabackup

.PHONY: build clean setup dev

# Create the build venv with pyinstaller and project deps
setup:
	python3 -m venv $(BUILD_VENV)
	$(BUILD_VENV)/bin/pip install --upgrade pip
	$(BUILD_VENV)/bin/pip install pyinstaller requests

# Build the standalone executable (Linux)
build: setup
	$(BUILD_VENV)/bin/pyinstaller \
		--onefile \
		--name mediabackup \
		--paths src \
		src/mediabackup/cli.py
	@echo ""
	@echo "Build complete: $(OUTPUT)"

# Install in dev venv (editable mode)
dev:
	venv/bin/pip install -e .

# Remove build artifacts
clean:
	rm -rf dist/ build/ $(BUILD_VENV) *.spec
