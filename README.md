# Tuscany Bike Route — Media & SEO Toolkit

A small collection of standalone Python scripts for the **Tuscany Bike Route** project:
SEO keyword analysis plus batch media conversion utilities (HEIC→JPG, images→WEBP, MOV→MP4).

## Requirements

- Python 3.9+
- [FFmpeg](https://ffmpeg.org) on your `PATH` (only needed for `video_converter2.py`)

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

| Package | Used by |
|---|---|
| `pandas`, `matplotlib`, `seaborn` | `main.py` |
| `pillow` | all image scripts |
| `pillow-heif` | HEIC/HEIF support (`convert.py`, optional in `photo_converter.py`) |

## Scripts

### 1. `main.py` — SEO Keyword Analysis Pipeline

**Function:** Reads a keyword-export CSV (Semrush-style columns: *Keyword*, *Group*,
*Search Volume*, *Competition*, *CPC/USD*, *Estimated traffic amount*, search-intent flags),
then:

1. Cleans the data (coerces numeric columns, converts intent flags to 0/1).
2. Scores every keyword with a weighted formula (search volume 30 %, inverted competition
   −20 %, CPC 15 %, estimated traffic 25 %, commercial/transactional intent 10 %),
   normalised to a 0–100 `relevance_score` and bucketed into Low / Medium / High / Very High.
3. Groups keywords by topic (`Group` column) and aggregates per-topic stats.
4. Produces a 4-panel visualisation (top keywords, score distribution, volume-vs-competition
   scatter, category counts).
5. Exports results and writes a plain-text strategic recommendations report.

**Usage:**

```bash
python main.py                 # uses keywords01.csv in the current directory
python main.py other_export.csv
```

**Outputs** (written to `./keyword_analysis_results/`):

- `tuscany_bike_route_keyword_scores.csv` — scored keywords, sorted by relevance
- `tuscany_bike_route_topic_analysis.csv` — per-group aggregates
- `tuscany_bike_route_recommendations.txt` — top keywords, low-competition opportunities, strategy notes
- `tuscany_bike_route_keyword_analysis.png` — the 4-panel chart

The scoring weights are a dict in `calculate_keyword_score()` — tune them there.

### 2. `convert.py` — HEIC → JPG Batch Converter

**Function:** Converts every `.heic`/`.HEIC` file in `./input_images/` to JPEG at quality 95
in `./output_images/`. Both folders are created automatically. Corrupt files are skipped and
reported in a final summary instead of crashing the batch. The script also runs a built-in
self-test after each normal run (directory creation, case-insensitive scanning, corrupt-file
handling, and a real HEIC round-trip when the encoder is available).

**Usage:**

```bash
python convert.py              # convert ./input_images/*.heic, then self-test
python convert.py --self-test  # only run the self-test (no touching of real folders)
```

Requires `pillow` and `pillow-heif`.

### 3. `photo_converter.py` — Batch Image → WEBP with SEO Renaming

**Function:** Recursively converts supported images (`.jpg .jpeg .png .webp .tif .tiff .bmp
.gif`, plus `.heic/.heif` if `pillow-heif` is installed) to optimised WEBP:

- Applies EXIF orientation and downscales (never upscales) to fit 1920×1920.
- Heuristically classifies each image as *photo* (quality 80) or *flat graphic* (lossy,
  quality 92); alpha is dropped when safe; PNG sources are forced lossy.
- Keeps an output **only if it is smaller than the source** (use `--force` to keep anyway).
- Gives each file a deterministic SEO slug filename derived from a hash of its path, and
  generates matching `alt` text and `description` strings.
- Writes `metadata.csv` and `metadata.json` mapping outputs to their SEO metadata.

**Usage:**

```bash
python photo_converter.py                       # reads ./to_convert_photo -> ./output_webp
python photo_converter.py /path/to/photos --output /path/to/webp
python photo_converter.py photos --force        # keep WEBP even if not smaller
```

### 4. `video_converter2.py` — Batch MOV → MP4 (colour-preserving)

**Function:** Converts every `.mov` in the input folder to `.mp4` via FFmpeg using
H.264 (`libx264`, preset `slow`, CRF 18) + AAC 192 kbps audio. Colour is preserved by
explicitly tagging bt.709 primaries/transfer/matrix, global metadata is copied
(`-map_metadata 0`), and `+faststart` makes files web-friendly. Per-file failures are
reported without aborting the batch. Requires `ffmpeg` on `PATH`.

**Usage:**

```bash
python video_converter2.py                      # reads ./to_convert_video -> ./to_convert_video/converted
python video_converter2.py /path/to/movs -o /path/to/mp4s
```

## Data

- `keywords01.csv` — sample keyword export used by `main.py` (Tuscany trail / bike route keywords).

## Typical workflow

1. Drop iPhone photos into `input_images/` → `python convert.py` (HEIC → JPG).
2. Put site images into `to_convert_photo/` → `python photo_converter.py` (WEBP + SEO metadata).
3. Put screen-recorded/camera `.mov` clips into `to_convert_video/` → `python video_converter2.py`.
4. Update the keyword export and rerun `python main.py` before each content-planning session.
