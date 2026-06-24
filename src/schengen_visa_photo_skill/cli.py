from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .landmarks import DEFAULT_MODEL_URL
from .processor import CropOptions, process_photo
from .requirements import SPECS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a Schengen or Japan visa photo crop and verification report.")
    parser.add_argument("input", type=Path, help="Input portrait image")
    parser.add_argument("--country", choices=sorted(SPECS), default="schengen", help="Target standard: schengen (35x45mm) or japan (45x45mm square)")
    parser.add_argument("--mode", choices=["execute", "diagnostic"], default="execute", help="execute returns non-zero on failed checks; diagnostic always exits 0 after writing artifacts")
    parser.add_argument("--output", type=Path, required=True, help="Output JPEG path")
    parser.add_argument("--report", type=Path, help="Optional JSON report path")
    parser.add_argument("--diagnostic", type=Path, help="Optional diagnostic overlay image path")
    parser.add_argument("--model-path", type=Path, default=Path("models/face_landmarker.task"), help="MediaPipe FaceLandmarker .task path")
    parser.add_argument("--model-url", default=DEFAULT_MODEL_URL, help="Model URL used if --model-path does not exist")
    parser.add_argument("--target-head-height-px", type=int, help="Override target head height before validation")
    parser.add_argument("--target-top-margin-px", type=int, help="Override target top margin before validation")
    parser.add_argument("--scale-multiplier", type=float, default=1.0, help="Multiply planned scale; >1 zooms in, <1 zooms out")
    parser.add_argument("--nudge-x-px", type=float, default=0.0, help="Positive values move the subject right in output pixels")
    parser.add_argument("--nudge-y-px", type=float, default=0.0, help="Positive values move the subject down in output pixels")
    parser.add_argument("--no-prioritize-eye-position", action="store_true", help="Disable the ICAO eye-band priority adjustment")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = process_photo(
        args.input,
        args.output,
        report_path=args.report,
        diagnostic_path=args.diagnostic,
        model_path=args.model_path,
        model_url=args.model_url,
        spec=SPECS[args.country],
        crop_options=CropOptions(
            target_head_height_px=args.target_head_height_px,
            target_top_margin_px=args.target_top_margin_px,
            scale_multiplier=args.scale_multiplier,
            nudge_x_px=args.nudge_x_px,
            nudge_y_px=args.nudge_y_px,
            prioritize_eye_position=not args.no_prioritize_eye_position,
        ),
    )
    print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    if args.mode == "diagnostic":
        return 0
    return 0 if report.passed() else 2


if __name__ == "__main__":
    raise SystemExit(main())
