#!/usr/bin/env python3
"""
HEIC -> JPG batch converter.

Before running, install dependencies:
    pip install pillow pillow-heif

Usage:
    python convert.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR / "input_images"
OUTPUT_DIR = SCRIPT_DIR / "output_images"
JPEG_QUALITY = 95


def ensure_directories(input_dir: Path, output_dir: Path) -> None:
    """Create the input/output folders if they don't already exist."""
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)


def find_heic_files(input_dir: Path) -> list[Path]:
    """Return all .heic/.HEIC files in input_dir, case-insensitively, no duplicates."""
    seen = set()
    files = []
    for path in input_dir.iterdir():
        if path.is_file() and path.suffix.lower() == ".heic":
            if path.resolve() not in seen:
                seen.add(path.resolve())
                files.append(path)
    return sorted(files)


def convert_heic_to_jpg(src: Path, output_dir: Path, quality: int = JPEG_QUALITY) -> Path:
    """Convert a single HEIC file to JPG in output_dir. Raises on failure."""
    dest = output_dir / (src.stem + ".jpg")
    with Image.open(src) as img:
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(dest, "JPEG", quality=quality)
    return dest


def run_conversion(input_dir: Path, output_dir: Path) -> tuple[list[str], list[tuple[str, str]]]:
    """
    Convert all HEIC files in input_dir to output_dir.
    Returns (converted_filenames, errors) where errors is a list of (filename, reason).
    """
    ensure_directories(input_dir, output_dir)
    heic_files = find_heic_files(input_dir)

    converted: list[str] = []
    errors: list[tuple[str, str]] = []

    for src in heic_files:
        try:
            convert_heic_to_jpg(src, output_dir)
            converted.append(src.name)
        except Exception as exc:  # noqa: BLE001 - intentionally broad to keep the batch running
            errors.append((src.name, str(exc)))

    return converted, errors


def print_summary(converted: list[str], errors: list[tuple[str, str]]) -> None:
    print("=" * 50)
    print("HEIC -> JPG Conversion Summary")
    print("=" * 50)
    print(f"Successfully converted: {len(converted)}")
    if converted:
        print("\nConverted files:")
        for name in converted:
            print(f"  • {name}")

    if errors:
        print(f"\nSkipped (errors): {len(errors)}")
        for name, reason in errors:
            print(f"  • {name} -> {reason}")

    if not converted and not errors:
        print("\nNo .heic files found in input_images/.")
    print("=" * 50)


def main() -> None:
    ensure_directories(INPUT_DIR, OUTPUT_DIR)
    converted, errors = run_conversion(INPUT_DIR, OUTPUT_DIR)
    print_summary(converted, errors)


# ---------------------------------------------------------------------------
# Self-test / verification block
# ---------------------------------------------------------------------------

def _make_fake_heic(path: Path) -> None:
    """
    Write a file with a .heic extension that contains no valid image data
    of any kind, so PIL's format sniffing fails and it's treated as corrupt.
    This lets the self-test exercise the error-handling path without needing
    a real HEIC encoder available in the test environment.
    """
    path.write_bytes(b"this is definitely not image data\x00\x01\x02" * 4)


def _make_real_heic(path: Path) -> bool:
    """Try to create a genuine HEIC file for a positive-path test. Returns True on success."""
    try:
        img = Image.new("RGB", (16, 16), color=(0, 128, 255))
        heif_file = pillow_heif.from_pillow(img)
        heif_file.save(str(path), quality=90)
        return True
    except Exception:
        return False


def self_test() -> None:
    print("\nRunning self-test...\n")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_input = tmp_path / "input_images"
        test_output = tmp_path / "output_images"

        # 1. Directory creation logic
        assert not test_input.exists(), "precondition failed: input dir should not exist yet"
        assert not test_output.exists(), "precondition failed: output dir should not exist yet"
        ensure_directories(test_input, test_output)
        assert test_input.is_dir(), "FAIL: input_images was not created"
        assert test_output.is_dir(), "FAIL: output_images was not created"
        print("[OK] Directory creation logic")

        # 1b. Idempotency - calling again should not raise
        ensure_directories(test_input, test_output)
        print("[OK] Directory creation is idempotent")

        # 2. Empty-folder scan
        converted, errors = run_conversion(test_input, test_output)
        assert converted == [] and errors == [], "FAIL: empty folder should yield no results"
        print("[OK] Empty input folder handled cleanly")

        # 3. Corrupt / invalid HEIC handling
        bad_file = test_input / "corrupt.heic"
        _make_fake_heic(bad_file)
        # also a file with uppercase extension but garbage bytes
        bad_file_upper = test_input / "broken.HEIC"
        bad_file_upper.write_bytes(b"not a real heic file")

        found = find_heic_files(test_input)
        found_names = {p.name for p in found}
        assert found_names == {"corrupt.heic", "broken.HEIC"}, (
            f"FAIL: case-insensitive scan mismatch, got {found_names}"
        )
        print("[OK] File-scanning loop finds .heic and .HEIC files")

        converted, errors = run_conversion(test_input, test_output)
        assert converted == [], f"FAIL: expected no successful conversions, got {converted}"
        error_names = {name for name, _ in errors}
        assert error_names == {"corrupt.heic", "broken.HEIC"}, (
            f"FAIL: expected both bad files reported as errors, got {error_names}"
        )
        print("[OK] Corrupt files are skipped and reported without crashing")

        # 4. Real conversion path (skipped gracefully if pillow-heif can't encode here)
        good_file = test_input / "good.heic"
        can_encode = _make_real_heic(good_file)
        if can_encode:
            converted, errors = run_conversion(test_input, test_output)
            assert "good.heic" in converted, f"FAIL: good.heic should convert, got {converted}"
            out_jpg = test_output / "good.jpg"
            assert out_jpg.is_file(), "FAIL: output .jpg was not created"
            with Image.open(out_jpg) as im:
                assert im.format == "JPEG", "FAIL: output file is not a valid JPEG"
            error_names = {name for name, _ in errors}
            assert error_names == {"corrupt.heic", "broken.HEIC"}, (
                "FAIL: good file should not appear in errors"
            )
            print("[OK] Valid HEIC successfully converted to JPG")
        else:
            print("[SKIP] Real HEIC encode/decode round-trip (encoder unavailable in this environment)")

        # 5. Terminal summary formatting (smoke test - just ensure it doesn't raise)
        print_summary(["a.heic", "b.HEIC"], [("c.heic", "simulated failure")])
        print_summary([], [])
        print("[OK] print_summary runs without error for populated and empty cases")

    print("\nSelf-test PASSED.\n")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        self_test()
    else:
        main()
        # Run the self-test automatically after a normal run so correctness
        # is verified every execution, without touching real input/output data.
        self_test()
