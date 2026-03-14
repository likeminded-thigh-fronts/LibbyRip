#!/usr/bin/env python3
"""Convert an MP3 file to M4B format using ffmpeg."""

import os
import subprocess
import sys

try:
    subprocess.run(
        ("ffmpeg", "-version"),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
except FileNotFoundError:
    print(
        "Error: FFmpeg not found, please install it on your system "
        "to continue: https://www.ffmpeg.org/download.html"
    )
    sys.exit(1)

path = input("MP3 path: ")

if not os.path.exists(path):
    print("File not found")
    sys.exit(1)
if not (path.endswith(".mp3") or path.endswith(".MP3")):
    print("File MUST be an mp3 file to continue")
    sys.exit(1)

outPath = path[:-4] + ".m4b"

subprocess.run(
    [
        "ffmpeg", "-i", path,
        "-c:a", "aac", "-b:a", "64k",
        "-vn", "-map_metadata", "0",
        "-map_chapters", "0", "-f", "ipod", outPath,
    ],
    check=False,
)
