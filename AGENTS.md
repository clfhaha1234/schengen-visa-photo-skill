# Schengen Visa Photo Skill

Keep examples synthetic or otherwise non-sensitive. Do not commit real applicant photos, private names, private paths, API keys, or local workspace details.

## Project Structure

- `src/schengen_visa_photo_skill/` - reusable Python package and CLI implementation.
- `skills/schengen_visa_photo.md` - root skill document for AI agents.
- `docs/` - requirements and reference notes.
- `tests/` - offline tests that do not require real faces or private images.

## Working Rules

- Use the project `.venv` (Python 3.11+). Dependencies are managed by `uv`.
- Keep the CLI usable without private state. If a model file is needed, it may be downloaded into ignored `models/`.
- Head height (70-80% of image height) is the binding ICAO rule and drives the crop scale; never trade it against the width band.
- Tests must pass with `.venv/bin/python -m pytest -v` before considering the repo ready.
