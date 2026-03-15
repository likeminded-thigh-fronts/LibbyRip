#!/usr/bin/env python3
"""
LibbyRip - Convert Libby audiobook downloads to M4B format with chapters

Usage:
    easym4b.py <input_directory_or_zip> [--output-dir DIR] [--output-author-dir]
    easym4b.py --help

Examples:
    easym4b.py "$HOME/Downloads/My Book"
    easym4b.py "$HOME/Downloads/My Book.zip" --output-dir /tmp
    easym4b.py "$HOME/Downloads/My Book" --output-dir /tmp --output-author-dir
"""

import sys
import json
import os
import subprocess
import argparse
import shutil
import zipfile
import re
from datetime import datetime
from pathlib import Path
import tempfile

from buildChapters import Metadata, metadata_to_ffmpeg

SETTINGS_DIR = Path.home() / ".config" / "easym4b"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# Common ffmpeg install locations on macOS
_FFMPEG_SEARCH_PATHS = [
    "/opt/homebrew/bin/ffmpeg",      # Apple Silicon Homebrew
    "/usr/local/bin/ffmpeg",         # Intel Homebrew
    "/opt/local/bin/ffmpeg",         # MacPorts
]


def is_xcode_installed():
    """Check if Xcode command line tools are installed."""
    try:
        subprocess.run(['xcode-select', '-p'],
                        capture_output=True,
                        text=True,
                        check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def _load_settings():
    """Load settings from config file."""
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_settings(settings):
    """Save settings to config file."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def save_ffmpeg_path(path):
    """Save ffmpeg path to persistent config."""
    settings = _load_settings()
    settings["ffmpeg_path"] = str(path)
    _save_settings(settings)


def load_ffmpeg_path():
    """Load saved ffmpeg path from config, or None."""
    return _load_settings().get("ffmpeg_path")


def _is_valid_ffmpeg(path):
    """Check if a path points to a working ffmpeg binary."""
    try:
        subprocess.run(
            (str(path), "-version"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return True
    except (FileNotFoundError, PermissionError, OSError):
        return False


def find_ffmpeg():
    """Search for ffmpeg in PATH and common install locations.

    Returns the full path as a string, or None if not found.
    """
    which_result = shutil.which("ffmpeg")
    if which_result:
        return which_result

    for path in _FFMPEG_SEARCH_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    return None


def resolve_ffmpeg():
    """Resolve ffmpeg path, checking saved config first, then auto-detecting.

    Returns the full path as a string, or None if not found.
    """
    saved = load_ffmpeg_path()
    if saved and _is_valid_ffmpeg(saved):
        return saved

    # Clear invalid saved path
    if saved:
        settings = _load_settings()
        settings.pop("ffmpeg_path", None)
        _save_settings(settings)

    found = find_ffmpeg()
    if found:
        save_ffmpeg_path(found)
        return found

    return None


def check_dependencies(ffmpeg_path="ffmpeg", log_file=None):
    """Check if ffmpeg is installed"""
    try:
        subprocess.run(
            (ffmpeg_path, "-version"),
            stdout=log_file if log_file else subprocess.DEVNULL,
            stderr=log_file if log_file else subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "FFmpeg not found. Please install it from https://www.ffmpeg.org/download.html"
        ) from exc


def validate_input_directory(directory):
    """Validate that the input directory has required files"""
    input_path = Path(directory)

    if not input_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Check for metadata.json
    metadata_file = input_path / "metadata" / "metadata.json"
    if not metadata_file.exists():
        raise FileNotFoundError(f"metadata/metadata.json not found in {directory}")

    # Check for MP3 files
    mp3_files = list(input_path.glob("Part *.mp3"))
    if not mp3_files:
        raise FileNotFoundError(f"No MP3 files (Part *.mp3) found in {directory}")

    return input_path


def get_audiobook_title(metadata_file):
    """Extract title from metadata.json"""
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    return metadata.get("title", "Audiobook")


def get_audiobook_author(metadata_file):
    """Extract author name from metadata.json.

    Looks for the first creator with role == "author", falling back to
    "author and narrator" combined role.
    """
    with open(metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    for creator in metadata.get("creator", []):
        if creator.get("role") == "author":
            return creator["name"]

    # Fallback: check for combined "author and narrator" role
    for creator in metadata.get("creator", []):
        if "author" in creator.get("role", ""):
            return creator["name"]

    return None


def sanitize_filename(name):
    """Sanitize a string for use as a filename/directory name."""
    # Replace characters that are problematic on macOS/Windows filesystems
    return re.sub(r'[/:*?"<>|\\]', '_', name).strip()


def extract_zip_to_temp(zip_path):
    """Extract a zip file to a temporary directory.

    Returns the path to the extracted contents. If the zip contains a single
    top-level directory, returns that directory.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="easym4b_"))

    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(temp_dir)

    # Check if zip contained a single top-level directory
    contents = list(temp_dir.iterdir())
    if len(contents) == 1 and contents[0].is_dir():
        return contents[0], temp_dir
    return temp_dir, temp_dir


def create_concat_file(input_path):
    """Create FFmpeg concat file content for combining MP3s"""
    mp3_files = sorted(input_path.glob("Part *.mp3"))
    return "\n".join(f"file '{f.name}'" for f in mp3_files)


def get_log_dir():
    """Get log directory for standalone app (PyInstaller)."""
    if getattr(sys, 'frozen', False):
        if sys.platform == 'win32':
            log_dir = Path(os.environ.get('LOCALAPPDATA',
                                          str(Path.home()))) / "easym4b" / "Logs"
        elif sys.platform == 'darwin':
            log_dir = Path.home() / "Library" / "Logs" / "easym4b"
        else:
            log_dir = Path.home() / ".local" / "share" / "easym4b" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    return None


def resolve_log_path(output_dir):
    """Determine log file path, avoiding overwrites."""
    frozen_log_dir = get_log_dir()
    log_dir = frozen_log_dir if frozen_log_dir else output_dir

    log_file_path = log_dir / "conversion.log"
    if log_file_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_path = log_dir / f"conversion_{timestamp}.log"

    return log_file_path


def run_conversion(
    input_path,
    output_dir=None,
    output_name=None,
    author_dir=False,
    keep_temp=False,
    log_dir=None,
    overwrite=False,
    progress_callback=None,
    ffmpeg_path="ffmpeg",
):
    """Run the full conversion pipeline.

    Args:
        input_path: Path to directory containing Libby audiobook files
        output_dir: Where to write the .m4b (defaults to input_path)
        output_name: Output filename without extension (defaults to title)
        author_dir: If True, create author subdirectory inside output_dir
        keep_temp: If True, keep intermediate files
        log_dir: Override log file directory
        overwrite: If True, overwrite existing output without prompting
        progress_callback: Optional callable(message: str)
        ffmpeg_path: Path to ffmpeg binary (defaults to "ffmpeg")

    Returns:
        Path to the output .m4b file
    """
    input_path = Path(input_path)

    def emit(msg):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

    # Validate
    mp3_files = list(input_path.glob("Part *.mp3"))
    emit(f"Found {len(mp3_files)} MP3 files")

    # Check dependencies
    check_dependencies(ffmpeg_path)

    # Get metadata file
    metadata_file = input_path / "metadata" / "metadata.json"

    # Determine output filename
    if output_name:
        output_filename = output_name
    else:
        output_filename = get_audiobook_title(metadata_file)

    # Resolve output directory
    if output_dir is None:
        output_dir = input_path
    else:
        output_dir = Path(output_dir)

    # Author subdirectory
    if author_dir:
        author_name = get_audiobook_author(metadata_file)
        if author_name:
            safe_author = sanitize_filename(author_name)
            output_dir = output_dir / safe_author
            emit(f"Author directory: {safe_author}")
        else:
            emit("Warning: No author found in metadata, skipping author directory")

    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{output_filename}.m4b"

    # Check if output file already exists
    if output_file.exists() and not overwrite:
        raise FileExistsError(f"{output_file} already exists. Use overwrite=True to replace.")

    # Resolve log path
    if log_dir:
        log_file_path = resolve_log_path(Path(log_dir))
    else:
        log_file_path = resolve_log_path(output_dir)

    emit(f"Input directory: {input_path}")
    emit(f"Output file: {output_file}")
    emit(f"Log file: {log_file_path}")

    with open(log_file_path, "w", encoding="utf-8") as log_file:
        # Step 1: Combine MP3 files
        emit("Combining MP3 files...")
        combined_file = input_path / "combined.mp3"
        concat_file = input_path / "concat.txt"

        with open(concat_file, "w", encoding="utf-8") as f:
            f.write(create_concat_file(input_path))

        result = subprocess.run(
            [
                ffmpeg_path, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(combined_file),
            ],
            stdout=log_file,
            stderr=log_file,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError("Error combining MP3 files. Check the log file for details.")

        emit(f"Combined MP3 created: {combined_file.name}")

        # Step 2: Convert to M4B with chapters
        emit("Converting to M4B format with chapters...")

        # Build chapter metadata using direct import
        with open(metadata_file, "r", encoding="utf-8") as f:
            raw_metadata = json.load(f)
        metadata = Metadata.from_json(raw_metadata)
        chapters_content = metadata_to_ffmpeg(metadata)

        chapters_metadata_file = input_path / "chapters.ffmetadata"
        with open(chapters_metadata_file, "w", encoding="utf-8") as f:
            f.write(chapters_content)

        # Check for cover art
        cover_file = input_path / "metadata" / "cover.jpg"

        # Select audio codec
        if sys.platform.startswith('darwin') and is_xcode_installed():
            CODEC = "aac_at"
        else:
            CODEC = "aac"

        # Build FFmpeg command
        ffmpeg_cmd = [
            ffmpeg_path, "-y",
            "-i", str(combined_file),
            "-i", str(chapters_metadata_file),
        ]

        if cover_file.exists():
            emit("Found cover art")
            ffmpeg_cmd.extend(["-i", str(cover_file)])
            ffmpeg_cmd.extend([
                "-c:a", CODEC,
                "-b:a", "64k",
                "-c:v", "copy",
                "-disposition:v:0", "attached_pic",
                "-map", "0:a",
                "-map", "2:v",
                "-map_metadata", "1",
                "-map_chapters", "1",
            ])
        else:
            emit("Cover art not found, skipping")
            ffmpeg_cmd.extend([
                "-c:a", CODEC,
                "-b:a", "64k",
                "-map_metadata", "1",
                "-map_chapters", "1",
            ])

        ffmpeg_cmd.append(str(output_file))

        result = subprocess.run(
            ffmpeg_cmd,
            stdout=log_file,
            stderr=log_file,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError("Error converting to M4B. Check the log file for details.")

        # Show results
        size = output_file.stat().st_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                size_str = f"{size:.1f} {unit}"
                break
            size /= 1024
        else:
            size_str = f"{size:.1f} TB"

        emit(f"Success! Output: {output_file}")
        emit(f"File size: {size_str}")

        # Cleanup temp files in input_path
        if not keep_temp:
            for filename in ["combined.mp3", "concat.txt", "chapters.ffmetadata"]:
                file_path = input_path / filename
                if file_path.exists():
                    file_path.unlink()

    return output_file


def main():
    """CLI entry point for easym4b."""
    parser = argparse.ArgumentParser(
        description="Convert Libby audiobook downloads to M4B format with chapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  easym4b "$HOME/Downloads/My Book"
  easym4b "$HOME/Downloads/My Book.zip" --output-dir /tmp
  easym4b "$HOME/Downloads/My Book" --output-dir /tmp --output-author-dir
        """,
    )

    parser.add_argument(
        "input", help="Path to directory or .zip file containing Libby audiobook files"
    )
    parser.add_argument(
        "--output-name",
        help="Output filename (without extension). Defaults to audiobook title from metadata",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to write output M4B file to. Defaults to input directory",
    )
    parser.add_argument(
        "--output-author-dir",
        action="store_true",
        help="Create author subdirectory inside output dir",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary files (combined.mp3, concat.txt, chapters.ffmetadata)",
    )

    args = parser.parse_args()

    print("LibbyRip - Libby to M4B Converter")
    print("=" * 50)

    ffmpeg_path = resolve_ffmpeg()
    if not ffmpeg_path:
        print(
            "\nError: FFmpeg not found. Please install it from "
            "https://www.ffmpeg.org/download.html"
        )
        sys.exit(1)

    input_arg = Path(args.input)
    temp_dir = None

    try:
        # Handle zip input
        if input_arg.suffix.lower() == '.zip':
            if not input_arg.exists():
                print(f"Error: File not found: {input_arg}")
                sys.exit(1)
            print(f"Extracting zip file: {input_arg.name}")
            extracted_path, temp_dir = extract_zip_to_temp(input_arg)
            input_path = validate_input_directory(extracted_path)

            # Default output_dir to cwd when using zip (can't write to temp dir)
            if not args.output_dir:
                args.output_dir = str(Path.cwd())
        else:
            input_path = validate_input_directory(input_arg)

        # Get metadata file for overwrite check
        metadata_file = input_path / "metadata" / "metadata.json"

        # Determine output location for overwrite check
        output_dir = Path(args.output_dir) if args.output_dir else input_path
        output_name = args.output_name or get_audiobook_title(metadata_file)

        if args.output_author_dir:
            author = get_audiobook_author(metadata_file)
            if author:
                output_dir = output_dir / sanitize_filename(author)

        output_file = output_dir / f"{output_name}.m4b"

        if output_file.exists():
            response = (
                input(f"\n{output_file} already exists. Overwrite? (y/n): ")
                .strip()
                .lower()
            )
            if response != "y":
                print("Cancelled")
                sys.exit(0)

        print()
        run_conversion(
            input_path=input_path,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            output_name=args.output_name,
            author_dir=args.output_author_dir,
            keep_temp=args.keep_temp,
            overwrite=True,  # Already prompted above
            ffmpeg_path=ffmpeg_path,
        )

    except (FileNotFoundError, RuntimeError, FileExistsError) as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        if temp_dir is not None:
            print("Cleaning up extracted zip contents...")
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
