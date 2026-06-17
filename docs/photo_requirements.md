# Schengen Visa Photo Requirements

## Official Links

- EU visa policy (European Commission): https://home-affairs.ec.europa.eu/policies/schengen-borders-and-visa/visa-policy_en
- ICAO Doc 9303 (photo token standard underlying the rules): https://www.icao.int/publications/pages/publication.aspx?docnum=9303
- Schengen photo specification summary: https://schengenvisainfo.com/photo/

## Active Standard Used By The CLI

The CLI treats the following as the operative standard for generated digital upload images. The print standard and the digital-upload standard overlap but are tracked explicitly because online portals work in pixels.

## Paper / Physical Photo Standard

- Printed photo size: `35mm x 45mm`.
- Head height from chin to crown/top of head: `70%-80%` of the photo height (`~31.5mm-36mm`).
- A small clearance between the top of the head and the top edge.
- Background: plain light grey or white, evenly lit, no border, no shadow.
- Expression: neutral, eyes open and clearly visible, mouth closed.
- Head centered and facing the camera.
- No hat/headwear except for religious reasons, and the face must remain fully visible.
- Glasses must not be tinted, reflective, thick-rimmed, or cover the eyes. Avoiding glasses is safer.
- Photo taken within the last 6 months.

## Digital Upload Standard

For online application photos, the CLI targets the standard digital rendering of the print size:

- Output image: `413px x 531px` JPEG (35x45mm at 300 DPI; ~11.8 px/mm on both axes).
- RGB color image.
- Head height: `372px-425px` (70-80% of 531px).
- Head/face width band: `189px-295px` (soft check; reported but not used to drive scale).
- Top margin (top of head to top edge): `24px-71px` (~2-6mm).
- Chin to bottom edge: at least `47px` (~4mm); the chin must not touch the edge.
- Eye line distance from the bottom edge: `266px-372px` (50-70% of height).
- Inter-eye distance: at least `60px`.
- JPEG size: lenient `10KB-1.2MB` band; individual portals (VFS/TLScontact/BLS) may impose stricter limits.

## Priority Rule

Head height is the dominant ICAO rule, so the crop scale is driven solely by head height and is never reduced to satisfy the width band. If the planned top margin would place the eye line outside the `50%-70%`-from-bottom band, the CLI shifts the crop vertically to bring the eyes into the band and records the adjustment in the report notes. In that conflict the eye-line position wins and the top margin is treated as secondary.

## Pixel Conversion Reference

Agencies and consular pages often describe the photo in millimeters, so the CLI reports the conversion:

- Photo width: `35mm -> 413px`.
- Photo height: `45mm -> 531px`.
- Head height: `70%-80% -> 372px-385px ... 425px` at 531px height.
- Top of head to top edge: `2mm-6mm -> 24px-71px` at 531px height.
- Chin to bottom edge: `>=4mm -> >=47px` at 531px height.

## CLI Targets

The CLI targets the midpoint of the head-height band while enforcing the other checks:

- Head height target: about `398px` (≈75%).
- Top margin target: about `48px`.
- Chin-to-bottom must be at least `47px`.
- Eye line must fall between `266px` and `372px` from the bottom.
- Inter-eye distance must be at least `60px`.
- If the top margin and eye-line band conflict, the CLI prioritizes the eye band and records the adjustment in the report notes.

## Diagnostic Overlay

The diagnostic image displays these measurements directly on the image using dimension arrows:

- output size
- head height
- head/face width
- top margin
- chin-to-bottom distance
- eye-to-bottom distance and the ICAO eye band
- inter-eye distance
- JPEG file size

Green means the value passes an active check. Red means the value fails an active check. Neutral/dark labels are measurements without a current pass/fail threshold.

## Visual-Only Checks

The CLI cannot verify these; a human or vision model must confirm them:

- Plain, evenly lit light-grey or white background with no shadows.
- Neutral expression, mouth closed, both eyes open and unobstructed.
- No reflections or glare on glasses; eyes clearly visible.
- No head covering except for religious reasons, face fully visible.
- Natural skin tones and no red-eye; photo is recent.
