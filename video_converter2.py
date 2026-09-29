#!/usr/bin/env python3
"""
Batch MOV -> MP4 converter using FFmpeg.

Re-encodes every .mov file in the input folder to .mp4 (H.264 + AAC) while
preserving colour: bt709 primaries/transfer/matrix are set explicitly and
metadata is copied from the source.

Requires: ffmpeg available on PATH.

Usage:
    python video_converter2.py [INPUT_DIR] [-o OUTPUT_DIR]

    INPUT_DIR     Folder containing .mov files (default: ./to_convert_video)
    -o OUTPUT_DIR Where to write .mp4 files (default: <INPUT_DIR>/converted)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_EXTENSIONS = {".mov"}


def build_command(input_path: Path, output_path: Path) -> list[str]:
    """FFmpeg command that preserves colour space and metadata."""
    return [
        "ffmpeg",
        "-y",                              # overwrite output files
        "-i", str(input_path),
        "-c:v", "libx264",                 # encode video with H.264
        "-preset", "slow",
        "-crf", "18",                      # high quality
        "-pix_fmt", "yuv420p",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-colorspace", "bt709",
        "-c:a", "aac",                     # re-encode audio
        "-b:a", "192k",
        "-map_metadata", "0",              # copy global metadata
        "-movflags", "+faststart",         # web-friendly playback
        str(output_path),
    ]


def convert_one(input_path: Path, output_path: Path) -> bool:
    """Convert a single file; returns True on success."""
    print(f"Converting: {input_path.name} → {output_path.name}")
    result = subprocess.run(build_command(input_path, output_path),
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FAILED: {input_path.name}\n{result.stderr.strip().splitlines()[-1] if result.stderr else ''}",
              file=sys.stderr)
        return False
    return True


def run(input_folder: Path, output_folder: Path | None = None) -> tuple[int, int]:
    """Convert all supported videos. Returns (converted_count, failed_count)."""
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg is not installed or not on PATH.", file=sys.stderr)
        sys.exit(1)

    if not input_folder.is_dir():
        print(f"Input directory not found: {input_folder}", file=sys.stderr)
        print("Create it and drop .mov files in, or pass the path as the first argument.",
              file=sys.stderr)
        sys.exit(1)

    output_folder = output_folder or (input_folder / "converted")
    output_folder.mkdir(parents=True, exist_ok=True)

    converted = failed = 0
    for entry in sorted(input_folder.iterdir()):
        if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS:
            out_path = output_folder / (entry.stem + ".mp4")
            if convert_one(entry, out_path):
                converted += 1
            else:
                failed += 1

    print(f"Done. Converted: {converted}, Failed: {failed}. Output: {output_folder.resolve()}")
    return converted, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch convert MOV files to MP4 with FFmpeg.")
    parser.add_argument("input_dir", nargs="?", default="./to_convert_video",
                        help="Folder containing .mov files (default: ./to_convert_video)")
    parser.add_argument("-o", "--output", default=None,
                        help="Output folder (default: <INPUT_DIR>/converted)")
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    run(Path(args.input_dir), output)


if __name__ == "__main__":
    main()
