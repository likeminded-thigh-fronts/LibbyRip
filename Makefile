.PHONY: help install clean all app

UNAME_S := $(shell uname -s)

help:
	@echo "LibbyRip - Libby to M4B Converter"
	@echo "=================================="
	@echo ""
	@echo "Usage:"
	@echo "  make install          - Install dependencies with uv"
	@echo "  make clean            - Remove temporary files from downloads"
	@echo "  make app              - Build standalone application"
	@echo ""
	@echo "Direct usage:"
	@echo "  uv run easym4b <input_directory_or_zip>"
	@echo "  uv run easym4b <input> --output-dir /path/to/output"
	@echo "  uv run easym4b <input> --output-dir /path --output-author-dir"
	@echo "  uv run easym4b <input> --keep-temp"

check_binaries:
	@echo "Checking FFmpeg installation..."
	@which ffmpeg > /dev/null || (echo "FFmpeg not found. Install with: brew install ffmpeg" && exit 1)
	@echo "✓ FFmpeg is installed"
	@echo ""
	@echo "Checking uv..."
	@which uv > /dev/null || (echo "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" && exit 1)
	@echo "✓ uv is installed"

install: check_binaries
	uv sync

clean:
	@echo "Cleaning up temporary files..."
	@find "$HOME/Downloads" -name "combined.mp3" -delete
	@find "$HOME/Downloads" -name "concat.txt" -delete
	@find "$HOME/Downloads" -name "chapters.ffmetadata" -delete
	@echo "✓ Cleaned temporary files"

app:
ifeq ($(UNAME_S),Darwin)
	@echo "Building standalone macOS application..."
	uv run --extra build pyinstaller --name easym4b --windowed gui.py
	@echo "✓ Built: dist/easym4b.app"
else
	@echo "Building standalone Windows application..."
	uv run --extra build pyinstaller --name easym4b --windowed --onefile gui.py
	@echo "✓ Built: dist/easym4b.exe"
endif

all: install
	@echo "Setup complete!"
