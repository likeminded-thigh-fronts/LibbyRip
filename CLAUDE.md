# easym4b

Convert Libby audiobook downloads to M4B format with chapters.

## Setup

```
make install
```

Requires `uv` and `ffmpeg` to be installed. On macOS: `brew install uv ffmpeg`.

## Usage

### CLI

```bash
# Convert from directory
uv run easym4b "$HOME/Downloads/My Book"

# Convert from zip file
uv run easym4b "$HOME/Downloads/My Book.zip" --output-dir /tmp

# Output to specific directory with author subdirectory
uv run easym4b "$HOME/Downloads/My Book" --output-dir /tmp --output-author-dir

# Custom output name, keep temp files
uv run easym4b "$HOME/Downloads/My Book" --output-name "MyBook" --keep-temp
```

### GUI

```bash
uv run easym4b-gui
```

### Standalone App

```bash
make app
```

Builds `dist/easym4b.app` using PyInstaller. Logs are written to `~/Library/Logs/easym4b/`.
