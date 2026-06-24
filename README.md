# Schengen Visa Photo Skill

AI-friendly CLI and skill for preparing visa/ID photos from an input portrait. The CLI detects facial landmarks, computes a standards-based crop, exports a JPEG at the target standard's pixel size, and writes a machine-readable verification report explaining which requirements were checked.

Two standards are built in, selected with `--country`:

- `schengen` (default) — Schengen / ICAO Doc 9303, `35x45mm` printed → `413x531` px at 300 DPI.
- `japan` — Japan (MOFA) square photo, `45x45mm` → `531x531` px at 300 DPI.

The Schengen standard is the one used across all Schengen member states for short-stay visa applications. Keep real applicant photos out of this repository.

## What It Does

- Reads one portrait image.
- Uses MediaPipe FaceLandmarker to estimate facial landmarks.
- Estimates the head silhouette from a plain (light-grey or white) background.
- Crops and scales the image to the Schengen digital target size of `413x531` pixels.
- Checks derived pixel requirements for output dimensions, head height (70-80% of image height), head/face width, top margin, chin-to-bottom distance, eye-line position (50-70% from bottom), inter-eye distance, and JPEG file size.
- Writes a JSON report and optional diagnostic overlay for AI/human review.

## Requirements (Schengen / ICAO)

| Property | Standard |
| --- | --- |
| Print size | 35 mm × 45 mm |
| Digital size | 413 × 531 px (300 DPI) |
| Head height (chin to crown) | 70–80% of image height (≈31.5–36 mm) |
| Eye line from bottom | 50–70% of image height |
| Background | plain light grey or white, evenly lit, no shadows |
| Expression | neutral, mouth closed, eyes open and visible |
| Head covering | none, except for religious reasons |
| Glasses | non-tinted, non-reflective, eyes clearly visible (avoid if possible) |

Background, expression, lighting, and glasses are **visual** checks the operator must confirm; the CLI measures the geometric and file properties.

## Requirements (Japan / MOFA)

| Property | Standard |
| --- | --- |
| Print size | 45 mm × 45 mm (square) |
| Digital size | 531 × 531 px (300 DPI) |
| Head height (chin to crown) | 34 ± 2 mm (≈71–80% of height) |
| Top of head to top edge | 4 ± 2 mm |
| Background | plain, light, evenly lit, no shadows |

Japan specifies head size and top clearance but **no eye-line position**, so the CLI reports the eye line for information only and never lets it override the authoritative top margin (`enforce_eye_band=False`). The same visual checks (background, neutral expression, no head covering) apply.

## Install

```bash
uv venv .venv --python 3.11
uv pip install -e '.[dev]'
```

## Use

```bash
# Schengen (default)
.venv/bin/schengen-visa-photo input.jpg --output outputs/input_schengen_visa.jpg --report outputs/input_report.json --diagnostic outputs/input_diagnostic.jpg

# Japan 45x45mm square
.venv/bin/schengen-visa-photo input.jpg --country japan --output outputs/input_japan_visa.jpg --report outputs/input_japan_report.json --diagnostic outputs/input_japan_diagnostic.jpg
```

Select the target standard with `--country {schengen,japan}` (default `schengen`).

The first live run downloads the MediaPipe face landmark model into `models/face_landmarker.task` unless `--model-path` points to an existing model file.

For review loops, use diagnostic mode. It writes the same artifacts but exits successfully even when active checks fail, so an AI or human reviewer can inspect the JSON and diagnostic image before rerunning with targeted adjustments.

```bash
.venv/bin/schengen-visa-photo input.jpg --mode diagnostic --output outputs/input_schengen_visa.jpg --report outputs/input_report.json --diagnostic outputs/input_diagnostic.jpg
```

Useful adjustment flags include `--target-head-height-px`, `--target-top-margin-px`, `--scale-multiplier`, `--nudge-x-px`, and `--nudge-y-px`.

## Output

The JSON report includes:

- output dimensions
- estimated head width and head height in pixels
- estimated top margin and chin-to-bottom in pixels
- estimated eye-line position and inter-eye distance
- source crop box
- per-requirement pass/fail checks
- caveats that require visual inspection

## Reading The Diagnostic Image

The diagnostic overlay uses engineering-style dimension arrows. Green labels pass active head/size checks; red labels fail active checks. The colored guide lines are: green for top-of-head or face-width dimensions, blue for chin/head-height dimensions, orange for the eye line, tan for the ICAO eye band, and red for horizontal center.

Active checks include output size, head height, head/face width, top margin, chin-to-bottom, eye-line position, inter-eye distance, and JPEG file size.

## Skill Installation For Agents

Give an agent this repository and ask it to install the root skill at `skills/schengen_visa_photo.md` into the target workspace's skill discovery chain. The installer should start from the target workspace's `AGENTS.md` or `CLAUDE.md`, update any `rules/skills/INDEX.md` or equivalent if present, and keep private applicant photos outside this repository.

## Privacy

Real applicant photos contain sensitive personal data. Keep them outside the repository, or in ignored local directories such as `photos/` or `outputs/`.

## Disclaimer

This tool prepares candidate photos and verifies measurable geometry. It does not guarantee acceptance by any consulate, embassy, or visa service provider (VFS, TLScontact, BLS, etc.). Always confirm the specific country's current requirements.
