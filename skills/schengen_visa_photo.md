---
name: schengen-visa-photo
description: Prepare Schengen (ICAO) visa photos with a landmark-based CLI, pixel requirement report, and human review diagnostics.
---

# Schengen Visa Photo Skill

## Goal

Convert a portrait image into a Schengen visa photo candidate and produce evidence that the crop satisfies measurable ICAO / Schengen requirements.

## Boundaries

- This skill prepares candidate photos; it does not guarantee consular, embassy, or VFS acceptance.
- It does not change the applicant's face, expression, hair, clothing, or background beyond crop/scale/padding. It does not recolor or replace the background.
- It assumes real applicant photos stay outside the repository. Use ignored local directories such as `photos/` or `outputs/`.
- It works best from a plain, evenly lit light-grey or white background because head boundaries are estimated from the foreground silhouette.

## CLI Contract

Install dependencies from the repo root (Python 3.11+):

```bash
uv venv .venv --python 3.11
uv pip install -e '.[dev]'
```

Run the CLI:

```bash
.venv/bin/schengen-visa-photo input.jpg \
  --output outputs/input_schengen_visa.jpg \
  --report outputs/input_report.json \
  --diagnostic outputs/input_diagnostic.jpg
```

The first live run downloads the MediaPipe FaceLandmarker model into ignored `models/` unless `--model-path` points to an existing `.task` model.

Use `execute` mode for automation that should fail on non-compliant outputs. Use `diagnostic` mode for review loops; it writes the same artifacts and exits successfully even when active checks fail, so an AI agent can inspect the JSON and diagnostic image before rerunning with targeted adjustments.

```bash
.venv/bin/schengen-visa-photo input.jpg \
  --mode diagnostic \
  --output outputs/input_schengen_visa.jpg \
  --report outputs/input_report.json \
  --diagnostic outputs/input_diagnostic.jpg
```

Select the target standard with `--country {schengen,japan}` (default `schengen`). `schengen` produces a `413x531` (35x45mm) image and enforces the ICAO eye-line band; `japan` produces a `531x531` (45x45mm square) image sized to the MOFA 34±2mm head height and 4±2mm top clearance, with no enforced eye-line (reported only).

The CLI exposes controlled crop adjustments for agent reruns:

- `--target-head-height-px`: choose a different head-height target before validation.
- `--target-top-margin-px`: choose a different top-margin target before validation.
- `--scale-multiplier`: zoom in or out relative to the planned crop.
- `--nudge-x-px` and `--nudge-y-px`: move the subject in output pixel coordinates.
- `--no-prioritize-eye-position`: disable the ICAO eye-band priority adjustment for comparison or debugging.
- `--sheet PATH` (with `--sheet-paper`, default `4x6`): also write a print sheet that tiles copies of the validated photo onto photo paper with cut guides, for lab/drugstore (CVS) printing. Native-pixel tiling keeps print size exact; orientation auto-fits the most copies (Japan 45×45mm → 6 per 4×6, Schengen 35×45mm → 8 per 4×6).

## Acceptance Criteria

A completed run should produce:

- A JPEG output with dimensions `413x531` pixels (35x45mm at 300 DPI).
- A JSON report with active checks for output size, head height, head/face width, top margin, chin-to-bottom, eye-line position, inter-eye distance, and JPEG size.
- A diagnostic image when `--diagnostic` is passed.
- The diagnostic image should show measurement labels for output size, head height, head width, top margin, chin-to-bottom, eye-to-bottom, inter-eye distance, JPEG size, and a line legend including the ICAO eye band.
- A human review note when any automated check passes but visual inspection remains necessary, especially hair/crown position, neutral expression, open unobstructed eyes, and background quality.

## Requirement References

- EU visa policy (European Commission): https://home-affairs.ec.europa.eu/policies/schengen-borders-and-visa/visa-policy_en
- ICAO Doc 9303 (machine-readable travel documents, photo token standard): https://www.icao.int/publications/pages/publication.aspx?docnum=9303
- Schengen photo specification summary: https://schengenvisainfo.com/photo/

## Known Caveats

- Face landmarks estimate facial features, not exact hair volume. The CLI prefers the plain-background silhouette for top-of-head and uses the face oval for width; it falls back to landmark-based top estimation only when silhouette extraction fails.
- The dominant ICAO rule is head height (chin to crown = 70-80% of image height); the crop scale is driven by head height and never traded against width. A naturally very wide or very narrow face may flag the width check while head height stays compliant.
- If the planned top margin would push the eye line outside the ICAO 50-70%-from-bottom band, the CLI prioritizes the eye band and records the adjustment in the report notes.
- Children's faces, tilted heads, hair covering the eyes, glasses glare, and non-plain backgrounds are common rejection risks.
- Each country's online appointment portal (e.g. VFS, TLScontact, BLS) may apply its own photo validator and file-size limits, so keep source and processed outputs available for retry.

## AI Adjustment Guidance

Treat the JSON report as the source of truth for deciding the next CLI call. Prefer small, explainable adjustments. If `head_height_ok` fails high, reduce `--target-head-height-px` or `--scale-multiplier`; if it fails low, increase them. If `head_width_ok` fails but `head_height_ok` passes, do not change scale to fix width — note it for human review, because head height is the binding ICAO rule. If `top_margin_ok` and `eye_position_ok` conflict, preserve `eye_position_ok` because the eye-line band is the biometric priority. If only centering is visually off, use `--nudge-x-px` or `--nudge-y-px` rather than changing scale.
