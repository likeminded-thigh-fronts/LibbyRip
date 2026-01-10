#!/usr/bin/env python3
"""
LibbyRip - Convert Libby audiobook downloads to M4B format with chapters

Usage:
    easym4b.py <input_directory> [--output-name FILENAME]
    easym4b.py --help

Examples:
    easym4b.py "$HOME/Downloads/My Book"
    easym4b.py "$HOME/Downloads/My Book" --output-name "MyBook"
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
import tempfile


def is_xcode_installed():
    try:
        # Run command to get active developer directory
        result = subprocess.run(['xcode-select', '-p'],
                                capture_output=True,
                                text=True,
                                check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def check_dependencies(log_file=None):
    """Check if ffmpeg is installed"""
    try:
        subprocess.run(
            ("ffmpeg", "-version"),
            stdout=log_file if log_file else subprocess.DEVNULL,
            stderr=log_file if log_file else subprocess.DEVNULL,
        )
    except FileNotFoundError:
        print(
            "Error: FFmpeg not found. Please install it from https://www.ffmpeg.org/download.html"
        )
        sys.exit(1)


def validate_input_directory(directory):
    """Validate that the input directory has required files"""
    input_path = Path(directory)

    if not input_path.exists():
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)

    # Check for metadata.json
    metadata_file = input_path / "metadata" / "metadata.json"
    if not metadata_file.exists():
        print(f"Error: metadata/metadata.json not found in {directory}")
        sys.exit(1)

    # Check for MP3 files
    mp3_files = list(input_path.glob("Part *.mp3"))
    if not mp3_files:
        print(f"Error: No MP3 files (Part *.mp3) found in {directory}")
        sys.exit(1)

    print(f"✓ Found {len(mp3_files)} MP3 files")
    print(f"✓ Found metadata.json")

    return input_path


def get_audiobook_title(metadata_file):
    """Extract title from metadata.json"""
    with open(metadata_file, "r") as f:
        metadata = json.load(f)
    return metadata.get("title", "Audiobook")


def extract_chapters(metadata_file, script_dir):
    """Extract chapter metadata using buildChapters.py"""
    print("Extracting chapter metadata...")

    build_chapters_script = script_dir / "buildChapters.py"

    with open(metadata_file, "r") as f:
        metadata_json = f.read()

    result = subprocess.run(
        ["python3", str(build_chapters_script), "--ffmpeg"],
        input=metadata_json,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error extracting chapters: {result.stderr}")
        sys.exit(1)

    return result.stdout


def create_concat_file(input_path):
    """Create FFmpeg concat file for combining MP3s"""
    print("Creating concat file for MP3 parts...")

    mp3_files = sorted(input_path.glob("Part *.mp3"))

    concat_content = "\n".join(f"file '{f.name}'" for f in mp3_files)

    return concat_content


def combine_mp3_files(input_path, concat_file_path, log_file=None):
    """Combine multiple MP3 files into one"""
    print("Combining MP3 files...")

    combined_file = input_path / "combined.mp3"

    # Write concat file
    with open(concat_file_path, "w") as f:
        f.write(create_concat_file(input_path))

    # Run FFmpeg
    result = subprocess.run(
        [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file_path),
            "-c",
            "copy",
            str(combined_file),
        ],
        stdout=log_file if log_file else subprocess.DEVNULL,
        stderr=log_file if log_file else subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error combining MP3 files: {result.stderr}")
        sys.exit(1)

    print(f"✓ Combined MP3 created: {combined_file.name}")
    return combined_file


def convert_to_m4b(combined_mp3, metadata_file, output_file, log_file=None):
    """Convert combined MP3 to M4B with chapters"""
    print("Converting to M4B format with chapters...")

    # Create chapters metadata file
    chapters_metadata_file = combined_mp3.parent / "chapters.ffmetadata"

    # Extract chapters
    build_chapters_script = Path(__file__).parent / "buildChapters.py"

    with open(metadata_file, "r") as f:
        metadata_json = f.read()

    result = subprocess.run(
        ["python3", str(build_chapters_script), "--ffmpeg"],
        input=metadata_json,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error extracting chapters: {result.stderr}")
        sys.exit(1)

    with open(chapters_metadata_file, "w") as f:
        f.write(result.stdout)

    # Check for cover art
    cover_file = combined_mp3.parent / "metadata" / "cover.jpg"

    # Build FFmpeg command
    ffmpeg_cmd = [
        "ffmpeg",
        "-i",
        str(combined_mp3),
        "-i",
        str(chapters_metadata_file),
    ]

    #Select Audio Codec
    if sys.platform.startswith('darwin') and is_xcode_installed():
        CODEC = "aac_at"  # Use Apple AAC codec on macOS, requires Xcode Audio Toolbox(default on Xcode installations)
    else:
        CODEC = "aac"     # Use standard AAC codec on other platforms
    # TODO: Support flag to choose Fraunhofer FDK AAC aka: libfdk_aac. Look into supporting VBR if using Fraunhofer.
    # TODO: Support flag for bitrate selection. For now 64k CBR is fine for audiobooks.

    # Add cover art if it exists
    if cover_file.exists():
        print("✓ Found cover art")
        ffmpeg_cmd.extend(["-i", str(cover_file)])
        # Map audio, metadata, chapters, and cover
        ffmpeg_cmd.extend([
            "-c:a",
            CODEC,
            "-b:a",
            "64k",
            "-c:v",
            "copy",
            "-disposition:v:0",
            "attached_pic",
            "-map",
            "0:a",
            "-map",
            "2:v",
            "-map_metadata",
            "1",
            "-map_chapters",
            "1",
        ])
    else:
        print("⚠ Cover art not found, skipping")
        # Map audio, metadata, and chapters only
        ffmpeg_cmd.extend([
            "-c:a",
            CODEC,
            "-b:a",
            "64k",
            "-map_metadata",
            "1",
            "-map_chapters",
            "1",
        ])

    ffmpeg_cmd.append(str(output_file))

    # Convert to M4B with chapters
    result = subprocess.run(
        ffmpeg_cmd,
        stdout=log_file if log_file else subprocess.DEVNULL,
        stderr=log_file if log_file else subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        print(f"Error converting to M4B: {result.stderr}")
        sys.exit(1)

    print(f"✓ M4B created: {output_file.name}")


def cleanup(input_path):
    """Clean up temporary files"""
    print("Cleaning up temporary files...")

    files_to_remove = ["combined.mp3", "concat.txt", "chapters.ffmetadata"]

    for filename in files_to_remove:
        file_path = input_path / filename
        if file_path.exists():
            file_path.unlink()
            print(f"✓ Removed {filename}")


def get_file_size(file_path):
    """Get human-readable file size"""
    size = file_path.stat().st_size
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def main():
    parser = argparse.ArgumentParser(
        description="Convert Libby audiobook downloads to M4B format with chapters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  easym4b.py "$HOME/Downloads/My Book"
  easym4b.py "$HOME/Downloads/My Book" --output-name "MyBook"
        """,
    )

    parser.add_argument(
        "input_directory", help="Path to directory containing Libby audiobook files"
    )
    parser.add_argument(
        "--output-name",
        help="Output filename (without extension). Defaults to audiobook title from metadata",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary files (combined.mp3, concat.txt, chapters.ffmetadata)",
    )

    args = parser.parse_args()

    print("LibbyRip - Libby to M4B Converter")
    print("=" * 50)

    # Check dependencies
    check_dependencies()

    # Validate input directory
    # TODO: Add support for passing zip files directly, extracting them to temp dirs, validating contents and cleaning up after.
    input_path = validate_input_directory(args.input_directory)

    # Get script directory
    script_dir = Path(__file__).parent

    # Get metadata file
    metadata_file = input_path / "metadata" / "metadata.json"

    # Determine output filename
    if args.output_name:
        output_filename = args.output_name
    else:
        output_filename = get_audiobook_title(metadata_file)

    output_file = input_path / f"{output_filename}.m4b"

    # Check if output file already exists
    if output_file.exists():
        response = (
            input(f"\n{output_file.name} already exists. Overwrite? (y/n): ")
            .strip()
            .lower()
        )
        if response != "y":
            print("Cancelled")
            sys.exit(0)

    try:
        # Create log file
        log_file_path = input_path / "conversion.log"

        # Run the conversion pipeline
        print(f"\nInput directory: {input_path}")
        print(f"Output file: {output_file.name}")
        print(f"Log file: {log_file_path.name}\n")

        with open(log_file_path, "w") as log_file:
            # Step 1: Combine MP3 files
            concat_file = input_path / "concat.txt"
            combined_mp3 = combine_mp3_files(input_path, concat_file, log_file)

            # Step 2: Convert to M4B with chapters
            convert_to_m4b(combined_mp3, metadata_file, output_file, log_file)

            # Show results
            print(f"\n✓ Success!")
            print(f"Output file: {output_file}")
            print(f"File size: {get_file_size(output_file)}")

            # Cleanup
            if not args.keep_temp:
                cleanup(input_path)
            else:
                print("\n(Keeping temporary files)")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
