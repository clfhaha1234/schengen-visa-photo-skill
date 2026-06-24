from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from .landmarks import (
    DEFAULT_MODEL_URL,
    detect_face_landmarks,
    estimate_background_color,
    estimate_face_geometry,
    estimate_head_geometry_from_plain_background,
)
from .requirements import DEFAULT_SPEC, PhotoSpec


@dataclass(frozen=True)
class CropPlan:
    crop_box_source: tuple[float, float, float, float]
    scale: float
    estimated_head_width_px: int
    estimated_head_height_px: int
    estimated_top_margin_px: int
    estimated_chin_to_bottom_px: int
    priority_notes: list[str]


@dataclass(frozen=True)
class CropOptions:
    target_head_height_px: int | None = None
    target_top_margin_px: int | None = None
    scale_multiplier: float = 1.0
    nudge_x_px: float = 0.0
    nudge_y_px: float = 0.0
    prioritize_eye_position: bool = True


@dataclass(frozen=True)
class ProcessReport:
    input: str
    output: str
    source_size: tuple[int, int]
    output_size: tuple[int, int]
    detected_landmarks: int
    geometry_source: str
    crop_box_source: tuple[float, float, float, float]
    scale: float
    estimated_head_width_px: int
    estimated_head_height_px: int
    estimated_top_margin_px: int
    estimated_chin_to_bottom_px: int
    estimated_eye_center_y_px: int | None
    estimated_eye_from_bottom_px: int | None
    estimated_inter_eye_px: int | None
    requirements_px: dict[str, object]
    checks: dict[str, bool]
    jpeg_size_bytes: int
    quality: int
    notes: list[str]

    def passed(self) -> bool:
        return all(self.checks.values())


def load_image(path: Path) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def plan_crop_from_geometry(
    *,
    center_x: float,
    crown_y: float,
    head_height: float,
    head_width: float,
    spec: PhotoSpec = DEFAULT_SPEC,
    eye_y: float | None = None,
    options: CropOptions = CropOptions(),
) -> CropPlan:
    # Head height is the dominant ICAO rule (70-80% of image height), so the
    # crop scale is set purely from head height. Width follows from the natural
    # head proportions and is validated separately, never traded against height.
    target_head_height_px = options.target_head_height_px or spec.target_head_height_px
    target_top_margin_px = options.target_top_margin_px or spec.target_top_margin_px
    scale = (target_head_height_px / head_height) * options.scale_multiplier
    crop_width = spec.output_width_px / scale
    crop_height = spec.output_height_px / scale
    crop_left = center_x - (spec.output_width_px / 2 - options.nudge_x_px) / scale
    crop_top = crown_y - (target_top_margin_px - options.nudge_y_px) / scale
    priority_notes: list[str] = []

    if options.prioritize_eye_position and spec.enforce_eye_band and eye_y is not None:
        eye_lo, eye_hi = spec.eye_from_bottom_px
        eye_from_bottom = spec.output_height_px - round((eye_y - crop_top) * scale)
        if eye_from_bottom < eye_lo or eye_from_bottom > eye_hi:
            # ICAO requires the eye line to sit in the upper-middle band of the
            # photo. When the planned top margin would place the eyes outside
            # that band, the eye position wins: shift the crop vertically to the
            # nearest band edge. This may change the top margin, which is the
            # secondary constraint.
            target_edge = eye_lo if eye_from_bottom < eye_lo else eye_hi
            required_eye_y_out = spec.output_height_px - target_edge
            crop_top = eye_y - required_eye_y_out / scale
            direction = "up" if eye_from_bottom < eye_lo else "down"
            priority_notes.append(
                f"Shifted crop {direction} to keep the eye line within the ICAO "
                f"{int(spec.eye_from_bottom_ratio[0] * 100)}-{int(spec.eye_from_bottom_ratio[1] * 100)}% band; "
                "top margin is secondary to eye position."
            )
    crop_box = (crop_left, crop_top, crop_left + crop_width, crop_top + crop_height)
    estimated_top_margin_px = round((crown_y - crop_top) * scale)
    estimated_head_height_px = round(head_height * scale)
    return CropPlan(
        crop_box_source=tuple(round(v, 2) for v in crop_box),
        scale=scale,
        estimated_head_width_px=round(head_width * scale),
        estimated_head_height_px=estimated_head_height_px,
        estimated_top_margin_px=estimated_top_margin_px,
        estimated_chin_to_bottom_px=spec.output_height_px - estimated_top_margin_px - estimated_head_height_px,
        priority_notes=priority_notes,
    )


def source_point_to_output(point: tuple[float, float], crop_box: tuple[float, float, float, float], scale: float) -> tuple[float, float]:
    left, top, _, _ = crop_box
    return ((point[0] - left) * scale, (point[1] - top) * scale)


def estimate_eye_metrics(landmarks: np.ndarray, crop_box: tuple[float, float, float, float], scale: float, spec: PhotoSpec) -> tuple[int | None, int | None, int | None]:
    # Prefer iris landmarks when present. MediaPipe FaceLandmarker with refine
    # landmarks exposes 468-472 and 473-477 for left/right iris regions.
    if len(landmarks) >= 478:
        left_eye = landmarks[468:473]
        right_eye = landmarks[473:478]
    else:
        left_eye = landmarks[[33, 133]]
        right_eye = landmarks[[362, 263]]
    eye_center_src = np.mean(np.vstack([left_eye, right_eye]), axis=0)
    left_center_src = np.mean(left_eye, axis=0)
    right_center_src = np.mean(right_eye, axis=0)
    _, eye_y = source_point_to_output((float(eye_center_src[0]), float(eye_center_src[1])), crop_box, scale)
    left_out = source_point_to_output((float(left_center_src[0]), float(left_center_src[1])), crop_box, scale)
    right_out = source_point_to_output((float(right_center_src[0]), float(right_center_src[1])), crop_box, scale)
    eye_y_i = round(eye_y)
    inter_eye = round(abs(right_out[0] - left_out[0]))
    return eye_y_i, spec.output_height_px - eye_y_i, inter_eye


def crop_with_background_padding(image: Image.Image, box: tuple[float, float, float, float], fill: tuple[int, int, int]) -> Image.Image:
    left, top, right, bottom = box
    width = int(round(right - left))
    height = int(round(bottom - top))
    canvas = Image.new("RGB", (width, height), fill)

    src_left = max(0, int(np.floor(left)))
    src_top = max(0, int(np.floor(top)))
    src_right = min(image.width, int(np.ceil(right)))
    src_bottom = min(image.height, int(np.ceil(bottom)))
    if src_right <= src_left or src_bottom <= src_top:
        raise RuntimeError("Crop box does not overlap source image")

    pasted = image.crop((src_left, src_top, src_right, src_bottom))
    dst_x = src_left - int(np.floor(left))
    dst_y = src_top - int(np.floor(top))
    canvas.paste(pasted, (dst_x, dst_y))
    return canvas


def save_jpeg_size_limited(image: Image.Image, output: Path, size_range: tuple[int, int]) -> tuple[int, int]:
    last: tuple[int, bytes, int] | None = None
    for quality in range(95, 49, -5):
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, optimize=True)
        size = buf.tell()
        last = (quality, buf.getvalue(), size)
        if size_range[0] <= size <= size_range[1]:
            break
    if last is None:
        raise RuntimeError("Failed to encode JPEG")
    quality, data, size = last
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return quality, size


def check_plan(plan: CropPlan, jpeg_size: int, spec: PhotoSpec = DEFAULT_SPEC) -> dict[str, bool]:
    head_width_min, head_width_max = spec.head_width_px
    head_height_min, head_height_max = spec.head_height_px
    top_min, top_max = spec.top_margin_px
    size_min, size_max = spec.jpeg_size_bytes
    return {
        "output_size_ok": True,
        "head_height_ok": head_height_min <= plan.estimated_head_height_px <= head_height_max,
        "head_width_ok": head_width_min <= plan.estimated_head_width_px <= head_width_max,
        "top_margin_ok": top_min <= plan.estimated_top_margin_px <= top_max,
        "chin_to_bottom_ok": plan.estimated_chin_to_bottom_px >= spec.chin_to_bottom_min_px,
        "jpeg_size_ok": size_min <= jpeg_size <= size_max,
    }


def draw_plain_text(arr: np.ndarray, text: str, origin: tuple[int, int], *, ok: bool | None = None, scale: float = 0.45) -> None:
    if ok is None:
        color = (30, 30, 30)
    else:
        color = (0, 130, 0) if ok else (200, 0, 0)
    cv2.putText(arr, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def draw_double_arrow(arr: np.ndarray, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int]) -> None:
    cv2.arrowedLine(arr, start, end, color, 1, tipLength=0.04)
    cv2.arrowedLine(arr, end, start, color, 1, tipLength=0.04)


def write_diagnostic(
    image: Image.Image,
    plan: CropPlan,
    output: Path,
    *,
    checks: dict[str, bool],
    jpeg_size: int,
    eye_center_y: int | None,
    eye_from_bottom: int | None,
    inter_eye: int | None,
    spec: PhotoSpec = DEFAULT_SPEC,
) -> None:
    photo = np.asarray(image).copy()
    top = plan.estimated_top_margin_px
    chin = plan.estimated_top_margin_px + plan.estimated_head_height_px
    eye_y = eye_center_y
    center_x = spec.output_width_px // 2
    green = (0, 160, 0)
    blue = (0, 80, 220)
    orange = (200, 110, 0)
    red = (220, 0, 0)

    # Reference guide lines.
    cv2.line(photo, (0, top), (spec.output_width_px, top), green, 1)
    cv2.line(photo, (0, chin), (spec.output_width_px, chin), blue, 1)
    if eye_y is not None:
        cv2.line(photo, (0, eye_y), (spec.output_width_px, eye_y), orange, 1)
    cv2.line(photo, (center_x, 0), (center_x, spec.output_height_px), red, 1)

    # Eye band guide lines (ICAO 50-70% from bottom).
    eye_lo, eye_hi = spec.eye_from_bottom_px
    band_top_y = spec.output_height_px - eye_hi
    band_bottom_y = spec.output_height_px - eye_lo
    cv2.line(photo, (0, band_top_y), (spec.output_width_px, band_top_y), (210, 170, 90), 1)
    cv2.line(photo, (0, band_bottom_y), (spec.output_width_px, band_bottom_y), (210, 170, 90), 1)

    # Engineering-style dimension arrows.
    head_width_range = f"{spec.head_width_px[0]}-{spec.head_width_px[1]}"
    head_height_range = f"{spec.head_height_px[0]}-{spec.head_height_px[1]}"
    top_range = f"{spec.top_margin_px[0]}-{spec.top_margin_px[1]}"
    eye_range = f"{eye_lo}-{eye_hi}"
    size_range = f"{spec.jpeg_size_bytes[0] // 1000}-{spec.jpeg_size_bytes[1] // 1000}KB"

    # Face/head width dimension.
    width_y = max(top + 90, min(chin - 80, top + plan.estimated_head_height_px // 2))
    half_width = plan.estimated_head_width_px // 2
    draw_double_arrow(photo, (center_x - half_width, width_y), (center_x + half_width, width_y), green)
    cv2.line(photo, (center_x - half_width, width_y - 8), (center_x - half_width, width_y + 8), green, 1)
    cv2.line(photo, (center_x + half_width, width_y - 8), (center_x + half_width, width_y + 8), green, 1)

    # Head height dimension.
    height_x = spec.output_width_px - 34
    draw_double_arrow(photo, (height_x, top), (height_x, chin), blue)
    cv2.line(photo, (height_x - 8, top), (height_x + 8, top), blue, 1)
    cv2.line(photo, (height_x - 8, chin), (height_x + 8, chin), blue, 1)

    # Top margin dimension.
    margin_x = 26
    draw_double_arrow(photo, (margin_x, 0), (margin_x, top), green)

    # Chin-to-bottom dimension.
    chin_bottom_x = 54
    draw_double_arrow(photo, (chin_bottom_x, chin), (chin_bottom_x, spec.output_height_px - 1), blue)
    cv2.line(photo, (chin_bottom_x - 8, chin), (chin_bottom_x + 8, chin), blue, 1)
    cv2.line(photo, (chin_bottom_x - 8, spec.output_height_px - 1), (chin_bottom_x + 8, spec.output_height_px - 1), blue, 1)

    # Eye-to-bottom dimension.
    if eye_y is not None and eye_from_bottom is not None:
        eye_x = spec.output_width_px - 66
        draw_double_arrow(photo, (eye_x, eye_y), (eye_x, spec.output_height_px - 1), orange)
        cv2.line(photo, (eye_x - 8, eye_y), (eye_x + 8, eye_y), orange, 1)
        cv2.line(photo, (eye_x - 8, spec.output_height_px - 1), (eye_x + 8, spec.output_height_px - 1), orange, 1)

    # Inter-eye dimension. Approximate around center because the output crop is
    # horizontally centered on the face.
    if eye_y is not None and inter_eye is not None:
        half_eye = inter_eye // 2
        eye_dim_y = max(18, eye_y - 22)
        draw_double_arrow(photo, (center_x - half_eye, eye_dim_y), (center_x + half_eye, eye_dim_y), orange)

    panel_width = 360
    gap = 18
    canvas = np.full((spec.output_height_px, spec.output_width_px + gap + panel_width, 3), 255, dtype=np.uint8)
    canvas[:, : spec.output_width_px] = photo
    cv2.line(canvas, (spec.output_width_px + gap // 2, 0), (spec.output_width_px + gap // 2, spec.output_height_px), (220, 220, 220), 1)
    x0 = spec.output_width_px + gap
    draw_plain_text(canvas, f"{spec.name} visa photo diagnostics", (x0, 28), scale=0.46)
    rows = [
        ("canvas", f"{spec.output_width_px}x{spec.output_height_px}px", "exact", checks.get("output_size_ok")),
        ("head height", f"{plan.estimated_head_height_px}px", f"req {head_height_range} (70-80%)", checks.get("head_height_ok")),
        ("head width", f"{plan.estimated_head_width_px}px", f"req {head_width_range}", checks.get("head_width_ok")),
        ("top margin", f"{plan.estimated_top_margin_px}px", f"req {top_range}", checks.get("top_margin_ok")),
        ("chin-bottom", f"{plan.estimated_chin_to_bottom_px}px", f"req >={spec.chin_to_bottom_min_px}", checks.get("chin_to_bottom_ok")),
        ("eye-bottom", f"{eye_from_bottom}px" if eye_from_bottom is not None else "n/a", f"req {eye_range}", checks.get("eye_position_ok")),
        ("inter-eye", f"{inter_eye}px" if inter_eye is not None else "n/a", f"req >={spec.inter_eye_min_px}", checks.get("inter_eye_ok")),
        ("jpeg", f"{jpeg_size // 1000}KB", f"req {size_range}", checks.get("jpeg_size_ok")),
    ]
    y = 62
    for label, value, req, ok in rows:
        draw_plain_text(canvas, label, (x0, y), ok=None, scale=0.42)
        draw_plain_text(canvas, value, (x0 + 112, y), ok=ok, scale=0.42)
        draw_plain_text(canvas, req, (x0, y + 18), ok=None, scale=0.34)
        y += 52
    draw_plain_text(canvas, "Lines: green top/width, blue chin/height,", (x0, spec.output_height_px - 42), scale=0.34)
    draw_plain_text(canvas, "orange eyes, tan eye-band, red center.", (x0, spec.output_height_px - 24), scale=0.34)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas).save(output, quality=90)


def process_photo(
    input_path: Path,
    output_path: Path,
    *,
    report_path: Path | None = None,
    diagnostic_path: Path | None = None,
    model_path: Path = Path("models/face_landmarker.task"),
    model_url: str = DEFAULT_MODEL_URL,
    spec: PhotoSpec = DEFAULT_SPEC,
    crop_options: CropOptions = CropOptions(),
) -> ProcessReport:
    image = load_image(input_path)
    landmarks = detect_face_landmarks(image, model_path=model_path, model_url=model_url)
    try:
        geom = estimate_head_geometry_from_plain_background(image, landmarks)
    except RuntimeError:
        geom = estimate_face_geometry(landmarks)
    raw_eye_center_y, _, _ = estimate_eye_metrics(landmarks, (0.0, 0.0, float(image.width), float(image.height)), 1.0, spec)
    plan = plan_crop_from_geometry(
        center_x=geom.center_x,
        crown_y=geom.crown_y,
        head_height=geom.head_height,
        head_width=geom.head_width,
        spec=spec,
        eye_y=float(raw_eye_center_y) if raw_eye_center_y is not None else None,
        options=crop_options,
    )
    # Pad with the estimated background color so any out-of-frame area blends in.
    fill = tuple(int(c) for c in estimate_background_color(np.asarray(image).astype(np.int16)))
    cropped = crop_with_background_padding(image, plan.crop_box_source, fill)
    final = cropped.resize((spec.output_width_px, spec.output_height_px), Image.Resampling.LANCZOS)
    quality, jpeg_size = save_jpeg_size_limited(final, output_path, spec.jpeg_size_bytes)
    checks = check_plan(plan, jpeg_size, spec)
    eye_center_y, eye_from_bottom, inter_eye = estimate_eye_metrics(landmarks, plan.crop_box_source, plan.scale, spec)
    eye_lo, eye_hi = spec.eye_from_bottom_px
    eye_in_band = eye_from_bottom is not None and eye_lo <= eye_from_bottom <= eye_hi
    # When the standard does not specify an eye line (e.g. Japan), the measured
    # position is reported but never gates pass/fail or overrides the top margin.
    checks["eye_position_ok"] = eye_in_band if spec.enforce_eye_band else True
    checks["inter_eye_ok"] = inter_eye is not None and inter_eye >= spec.inter_eye_min_px
    report = ProcessReport(
        input=str(input_path),
        output=str(output_path),
        source_size=image.size,
        output_size=final.size,
        detected_landmarks=len(landmarks),
        geometry_source=geom.source,
        crop_box_source=plan.crop_box_source,
        scale=round(plan.scale, 6),
        estimated_head_width_px=plan.estimated_head_width_px,
        estimated_head_height_px=plan.estimated_head_height_px,
        estimated_top_margin_px=plan.estimated_top_margin_px,
        estimated_chin_to_bottom_px=plan.estimated_chin_to_bottom_px,
        estimated_eye_center_y_px=eye_center_y,
        estimated_eye_from_bottom_px=eye_from_bottom,
        estimated_inter_eye_px=inter_eye,
        requirements_px=spec.as_report_dict(),
        checks=checks,
        jpeg_size_bytes=jpeg_size,
        quality=quality,
        notes=[
            "Head geometry is estimated from the plain-background foreground silhouette when possible; visually inspect hair/crown clearance.",
            "The CLI does not replace or recolor the background; the source should already be a plain light-grey or white background per Schengen/ICAO rules.",
            "Neutral expression, mouth closed, eyes open and unobstructed, and no head covering (except for religious reasons) must be verified visually.",
            "Compliance remains subject to consulate, VFS/embassy, and online-system review.",
            *(
                []
                if spec.enforce_eye_band
                else [
                    f"{spec.name} specifies head size and top clearance but no eye-line "
                    "position; eye_from_bottom is reported for information only and the "
                    "authoritative top-margin placement is preserved."
                ]
            ),
            *plan.priority_notes,
        ],
    )
    if diagnostic_path:
        write_diagnostic(
            final,
            plan,
            diagnostic_path,
            checks=checks,
            jpeg_size=jpeg_size,
            eye_center_y=eye_center_y,
            eye_from_bottom=eye_from_bottom,
            inter_eye=inter_eye,
            spec=spec,
        )
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n")
    return report
