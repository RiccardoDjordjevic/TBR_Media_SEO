"""
Batch image → WEBP converter with SEO renaming + metadata.
- Downsizing to MAX_W×MAX_H
- Lossy for graphics to ensure shrink
- Drops alpha when safe
- Skip save if output ≥ input
"""

import os, re, csv, json, hashlib, random
from pathlib import Path
from typing import Tuple
from PIL import Image, ImageOps

# Optional HEIC/HEIF support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

# --------- CONFIG ---------
INPUT_DIR = Path("/Users/riccardodjordjevic/Downloads/TBR/to_convert_photo")
OUTPUT_DIR = Path("./output_webp")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_W, MAX_H = 1920, 1920
PHOTO_QUALITY = 80
GRAPHIC_QUALITY = 92
WEBP_METHOD = 6

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".heic", ".heif"}

SCENES = [
    "white road", "cypress lane", "Chianti hills", "vineyard climb", "medieval gate",
    "Etruscan ridge", "Tuscan gravel", "Crete Senesi", "Val d'Orcia view", "olive grove"
]
BENEFITS = [
    "self-guided cycling", "gravel bikepacking", "route-tested by locals",
    "quiet backroads", "luggage-free options", "authentic food stops"
]
VERBS = ["ride", "discover", "explore", "wander", "climb", "roll"]
PROOFS = [
    "150–450 km curated routes", "downloadable GPX with POIs", "24/7 on-ride support",
    "family-run partners", "crowd-free segments"
]
BRAND = "Tuscany Bike Route"

# --------- HELPERS ---------
_slug_re = re.compile(r"[^a-z0-9]+")
def slugify(s: str) -> str:
    s = s.lower()
    s = _slug_re.sub("-", s).strip("-")
    return re.sub(r"-{2,}", "-", s)

def deterministic_choice(pool, seed_bytes, n=1):
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
    colors = thumb.getcolors(maxcolors=256*256)
    if colors:
        unique = len(colors)
        total = sum(c for c, _ in colors)
        return (unique / max(1, total)) < 0.15
    return False

def resize_fit(im: Image.Image, max_w=MAX_W, max_h=MAX_H) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    w, h = im.size
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        im = im.resize(new_size, Image.Resampling.LANCZOS)
    return im

def make_seo_text(src_path: Path, im: Image.Image) -> Tuple[str, str, str]:
    h = hashlib.blake2b((str(src_path) + str(im.size) + (im.mode or "")).encode("utf-8"), digest_size=8).digest()
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

def save_webp_safely(im: Image.Image, dst: Path, save_params: dict, src_size: int) -> bool:
    tmp = dst.with_name(dst.stem + "._tmp.webp")
    im.save(tmp, "WEBP", **save_params)
    try:
        if tmp.stat().st_size < src_size:
            tmp.replace(dst)
            return True
        else:
            tmp.unlink(missing_ok=True)
            return False
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            return False

# --------- PIPELINE ---------
records = []
count = 0

for src in INPUT_DIR.rglob("*"):
    if not src.is_file():
        continue
    if src.suffix.lower() not in EXTS:
        continue

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
            dst = OUTPUT_DIR / f"{seo_base}.webp"

            # Only keep if smaller than input
            saved = save_webp_safely(im, dst, save_params, src.stat().st_size)
            if not saved:
                # Skip metadata if we did not get a smaller file
                continue

            records.append({
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
            })
            count += 1

    except Exception as e:
        print(f"Skipping {src}: {e}")

# Write metadata only if any saved
if records:
    meta_csv = OUTPUT_DIR / "metadata.csv"
    with meta_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)

    meta_json = OUTPUT_DIR / "metadata.json"
    with meta_json.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

print(f"Done. Converted and kept: {count}. Output: {OUTPUT_DIR.resolve()}")
