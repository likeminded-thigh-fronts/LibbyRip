.PHONY: help install test clean all

help:
	@echo "LibbyRip - Libby to M4B Converter"
	@echo "=================================="
	@echo ""
	@echo "Usage:"
	@echo "  make install          - Install dependencies"
	@echo "  make test             - Test with example directory"
	@echo "  make clean            - Remove temporary files from downloads"
	@echo ""
	@echo "Direct usage:"
	@echo "  python3 easym4b.py <input_directory>"
	@echo "  python3 easym4b.py <input_directory> --output-name FILENAME"
	@echo "  python3 easym4b.py <input_directory> --keep-temp"

check_binaries:
	@echo "Checking FFmpeg installation..."
	@which ffmpeg > /dev/null || (echo "FFmpeg not found. Install with: brew install ffmpeg" && exit 1)
	@echo "✓ FFmpeg is installed"
	@echo ""
	@echo "Checking Python 3..."
	@/usr/bin/env python3 --version
	@echo "✓ Python 3 is installed"

install: check_binaries
	@/usr/bin/env python3 -m venv .venv
	@/usr/bin/env python3 -m pip install -r requirements.txt

clean:
	@echo "Cleaning up temporary files..."
	@find "$HOME/Downloads" -name "combined.mp3" -delete
	@find "$HOME/Downloads" -name "concat.txt" -delete
	@find "$HOME/Downloads" -name "chapters.ffmetadata" -delete
	@echo "✓ Cleaned temporary files"

all: install
	@echo "Setup complete!"
