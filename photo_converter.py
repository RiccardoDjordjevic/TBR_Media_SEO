#!/usr/bin/env python3
"""
Batch image -> WEBP converter with SEO renaming + metadata export.

Features:
    - Downsizes images to MAX_W x MAX_H (EXIF orientation applied first)
    - Heuristic photo vs. graphic classification with different WEBP quality
    - Drops alpha when safe; forces lossy for PNG sources
    - Only keeps the WEBP if it is smaller than the source file
    - Deterministic SEO-friendly filenames derived from the source path
    - Writes metadata.csv / metadata.json alongside the converted images
    - Optional HEIC/HEIF support when pillow-heif is installed

Usage:
    python photo_converter.py [INPUT_DIR] [--output OUTPUT_DIR] [--force]

    INPUT_DIR      Folder containing images to convert (default: ./to_convert_photo)
    --output DIR   Where to write WEBP files + metadata (default: ./output_webp)
    --force        Keep the WEBP output even when it is not smaller than the input
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageOps

# Optional HEIC/HEIF support
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

# --------- CONFIG ---------
DEFAULT_OUTPUT_DIR = Path("./output_webp")

MAX_W, MAX_H = 1920, 1920
PHOTO_QUALITY = 80
GRAPHIC_QUALITY = 92
WEBP_METHOD = 6

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".heic", ".heif"}

SCENES = [
    "white road", "cypress lane", "Chianti hills", "vineyard climb", "medieval gate",
    "Etruscan ridge", "Tuscan gravel", "Crete Senesi", "Val d'Orcia view", "olive grove",
]
BENEFITS = [
    "self-guided cycling", "gravel bikepacking", "route-tested by locals",
    "quiet backroads", "luggage-free options", "authentic food stops",
]
VERBS = ["ride", "discover", "explore", "wander", "climb", "roll"]
PROOFS = [
    "150–450 km curated routes", "downloadable GPX with POIs", "24/7 on-ride support",
    "family-run partners", "crowd-free segments",
]
BRAND = "Tuscany Bike Route"


# --------- HELPERS ---------
_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(s: str) -> str:
    """Lowercase and replace non-alphanumeric runs with single hyphens."""
    s = s.lower()
    s = _slug_re.sub("-", s).strip("-")
    return re.sub(r"-{2,}", "-", s)


def deterministic_choice(pool, seed_bytes, n=1):
    """Pick n items from pool in a way that is reproducible for the same seed."""
    rnd = random.Random(int.from_bytes(seed_bytes, "little"))
    picks = pool[:]
    rnd.shuffle(picks)
    return picks[:n]


def has_alpha(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA") or ("transparency" in im.info)


def classify_graphic(im: Image.Image) -> bool:
    """Heuristic: graphics/flat art return True; photos return False."""
    if has_alpha(im):
        return True
    thumb = im.convert("RGB").copy()
    thumb.thumbnail((256, 256))
    colors = thumb.getcolors(maxcolors=256 * 256)
    if colors:
        unique = len(colors)
        total = sum(c for c, _ in colors)
        return (unique / max(1, total)) < 0.15
    return False


def resize_fit(im: Image.Image, max_w: int = MAX_W, max_h: int = MAX_H) -> Image.Image:
    """Apply EXIF orientation, then downscale (never upscale) to fit max_w x max_h."""
    im = ImageOps.exif_transpose(im)
    w, h = im.size
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        im = im.resize(new_size, Image.Resampling.LANCZOS)
    return im


def make_seo_text(src_path: Path, im: Image.Image) -> Tuple[str, str, str]:
    """Build a deterministic SEO filename base, alt text, and description."""
    key = str(src_path) + str(im.size) + (im.mode or "")
    h = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    scene = deterministic_choice(SCENES, h, 1)[0]
    benefit = deterministic_choice(BENEFITS, h[::-1], 1)[0]
    verb = deterministic_choice(VERBS, h[::2], 1)[0]
    proof = deterministic_choice(PROOFS, h[1::2], 1)[0]

    seo_base = slugify(f"tbr {benefit} {scene} tuscany {verb}")
    uniq = hashlib.blake2b(h, digest_size=3).hexdigest()
    seo_base = f"{seo_base}-{uniq}"

    alt_text = f"{BRAND}: {verb} the {scene} of Tuscany on {benefit}."
    description = f"{BRAND} — {benefit} across Tuscany’s {scene}. Routes are {proof}. Book your ride."

    return seo_base, alt_text, description


def save_webp_safely(im: Image.Image, dst: Path, save_params: dict, src_size: int,
                     force: bool = False) -> bool:
    """Save as WEBP via a temp file; keep only if smaller than src_size (or force)."""
    tmp = dst.with_name(dst.stem + "._tmp.webp")
    try:
        im.save(tmp, "WEBP", **save_params)
        if force or tmp.stat().st_size < src_size:
            tmp.replace(dst)
            return True
        tmp.unlink(missing_ok=True)
        return False
    except Exception:
        tmp.unlink(missing_ok=True)
        return False


# --------- PIPELINE ---------
def convert_image(src: Path, output_dir: Path, force: bool = False) -> dict | None:
    """Convert one image to WEBP. Returns a metadata record, or None if skipped."""
    try:
        with Image.open(src) as im:
            if getattr(im, "is_animated", False):
                im.seek(0)

            im = resize_fit(im, MAX_W, MAX_H)
            is_graphic = classify_graphic(im)
            is_png = src.suffix.lower() == ".png"

            # Build save params
            save_params = dict(method=WEBP_METHOD)
            if is_graphic:
                # Prefer lossy for graphics/PNGs to ensure smaller bytes
                if not has_alpha(im):
                    im = im.convert("RGB")
                save_params.update(lossless=False, quality=GRAPHIC_QUALITY)
            else:
                if has_alpha(im):
                    im = im.convert("RGB")
                save_params.update(quality=PHOTO_QUALITY)

            # Extra rule: force lossy for PNG sources
            if is_png:
                if not has_alpha(im):
                    im = im.convert("RGB")
                save_params.update(lossless=False)

            seo_base, alt_text, description = make_seo_text(src, im)
            dst = output_dir / f"{seo_base}.webp"

            # Only keep if smaller than input (unless --force)
            saved = save_webp_safely(im, dst, save_params, src.stat().st_size, force=force)
            if not saved:
                return None

            return {
                "source_path": str(src),
                "output_path": str(dst),
                "file_name": dst.name,
                "alt": alt_text,
                "description": description,
                "width": im.width,
                "height": im.height,
                "graphic_mode": bool(is_graphic),
                "webp_quality": save_params.get("quality"),
                "webp_lossless": bool(save_params.get("lossless", False)),
            }
    except Exception as e:
        print(f"Skipping {src}: {e}", file=sys.stderr)
        return None


def run(input_dir: Path, output_dir: Path, force: bool = False) -> list[dict]:
    """Convert every supported image under input_dir into output_dir."""
    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        print("Create it and drop images in, or pass the path as the first argument.",
              file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for src in sorted(input_dir.rglob("*")):
        if not src.is_file() or src.suffix.lower() not in EXTS:
            continue
        record = convert_image(src, output_dir, force=force)
        if record is not None:
            records.append(record)

    # Write metadata only if any files were saved
    if records:
        meta_csv = output_dir / "metadata.csv"
        with meta_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

        meta_json = output_dir / "metadata.json"
        with meta_json.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch convert images to SEO-named WEBP.")
    parser.add_argument("input_dir", nargs="?", default="./to_convert_photo",
                        help="Folder containing images to convert (default: ./to_convert_photo)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR),
                        help="Output folder (default: ./output_webp)")
    parser.add_argument("--force", action="store_true",
                        help="Keep WEBP output even if not smaller than the input")
    args = parser.parse_args()

    records = run(Path(args.input_dir), Path(args.output), force=args.force)
    print(f"Done. Converted and kept: {len(records)}. Output: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
