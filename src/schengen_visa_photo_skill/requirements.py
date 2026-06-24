from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhotoSpec:
    """A geometry-driven ID/visa photo standard.

    The default values describe the Schengen / ICAO Doc 9303 standard: a
    35mm x 45mm print rendered as the widely accepted 413x531px image
    (300 DPI). The dominant biometric rule is head height: the face from chin
    to crown must occupy a fixed fraction of the image height. Eye position and
    a small head clearance follow from it.

    The same dataclass parameterizes other national standards (e.g. Japan's
    square 45x45mm photo) by overriding the dimensions, physical size, and
    head-height band; all derived pixel thresholds recompute from those fields,
    so no per-country geometry logic is needed elsewhere.
    """

    name: str = "Schengen"
    output_width_px: int = 413
    output_height_px: int = 531
    physical_width_mm: float = 35.0
    physical_height_mm: float = 45.0
    # Head height (chin to crown) as a fraction of total image height. This is
    # the primary ICAO rule and drives the crop scale.
    head_height_ratio: tuple[float, float] = (0.70, 0.80)
    # Head/face width band. Soft compared to head height; the crop scale is set
    # by head height, so width is reported and validated against a generous band.
    head_width_mm: tuple[float, float] = (16.0, 25.0)
    # Small clearance from the top of the head to the top edge of the photo.
    top_margin_mm: tuple[float, float] = (2.0, 6.0)
    # The chin must not touch the bottom edge.
    chin_to_bottom_min_mm: float = 4.0
    # Eye line position measured from the bottom edge, as a fraction of height.
    # ICAO places the eyes in the upper-middle band of the image.
    eye_from_bottom_ratio: tuple[float, float] = (0.50, 0.70)
    # Whether the eye-line band is an enforced requirement. ICAO/Schengen
    # mandate it, so the crop is shifted to honor it and it gates pass/fail.
    # Standards that specify only head size and top clearance (e.g. Japan) set
    # this False: the eye line is then reported for information but never
    # overrides the authoritative top-margin placement.
    enforce_eye_band: bool = True
    # Minimum distance between the eye centers for adequate facial resolution.
    inter_eye_min_px: int = 60
    # Schengen portals vary widely; keep a lenient JPEG size band.
    jpeg_size_bytes: tuple[int, int] = (10_000, 1_200_000)

    @property
    def px_per_mm_x(self) -> float:
        return self.output_width_px / self.physical_width_mm

    @property
    def px_per_mm_y(self) -> float:
        return self.output_height_px / self.physical_height_mm

    def x_mm_to_px_range(self, mm_range: tuple[float, float]) -> tuple[int, int]:
        return (round(mm_range[0] * self.px_per_mm_x), round(mm_range[1] * self.px_per_mm_x))

    def y_mm_to_px_range(self, mm_range: tuple[float, float]) -> tuple[int, int]:
        return (round(mm_range[0] * self.px_per_mm_y), round(mm_range[1] * self.px_per_mm_y))

    def y_ratio_to_px_range(self, ratio_range: tuple[float, float]) -> tuple[int, int]:
        return (round(ratio_range[0] * self.output_height_px), round(ratio_range[1] * self.output_height_px))

    @property
    def head_width_px(self) -> tuple[int, int]:
        return self.x_mm_to_px_range(self.head_width_mm)

    @property
    def head_height_px(self) -> tuple[int, int]:
        return self.y_ratio_to_px_range(self.head_height_ratio)

    @property
    def top_margin_px(self) -> tuple[int, int]:
        return self.y_mm_to_px_range(self.top_margin_mm)

    @property
    def chin_to_bottom_min_px(self) -> int:
        return round(self.chin_to_bottom_min_mm * self.px_per_mm_y)

    @property
    def eye_from_bottom_px(self) -> tuple[int, int]:
        return self.y_ratio_to_px_range(self.eye_from_bottom_ratio)

    @property
    def target_head_height_px(self) -> int:
        lo, hi = self.head_height_px
        return round((lo + hi) / 2)

    @property
    def target_head_width_px(self) -> int:
        lo, hi = self.head_width_px
        return round((lo + hi) / 2)

    @property
    def target_top_margin_px(self) -> int:
        lo, hi = self.top_margin_px
        return round((lo + hi) / 2)

    def as_report_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "output_width_px": self.output_width_px,
            "output_height_px": self.output_height_px,
            "head_width_px": list(self.head_width_px),
            "head_height_px": list(self.head_height_px),
            "head_height_ratio": list(self.head_height_ratio),
            "top_margin_px": list(self.top_margin_px),
            "chin_to_bottom_min_px": self.chin_to_bottom_min_px,
            "eye_from_bottom_px": list(self.eye_from_bottom_px),
            "enforce_eye_band": self.enforce_eye_band,
            "inter_eye_min_px": self.inter_eye_min_px,
            "jpeg_size_bytes": list(self.jpeg_size_bytes),
        }


SCHENGEN_SPEC = PhotoSpec()

# Japan (MOFA) visa/passport photo standard. The official figure specifies a
# square 45mm x 45mm photo with a 34±2mm crown-to-chin head height and a 4±2mm
# clearance above the head; the face is horizontally centered. There is no
# separate face-width or eye-line rule, so those bands are inherited as soft /
# secondary checks (the eye line lands naturally inside the band at this head
# height and top margin). The digital target keeps the same 300 DPI / ~11.8
# px-per-mm scale as Schengen, so 45mm maps to 531px on both axes and every
# mm-based and px-based threshold carries over unchanged.
JAPAN_SPEC = PhotoSpec(
    name="Japan",
    output_width_px=531,
    output_height_px=531,
    physical_width_mm=45.0,
    physical_height_mm=45.0,
    head_height_ratio=(32.0 / 45.0, 36.0 / 45.0),  # 34±2mm of 45mm
    top_margin_mm=(2.0, 6.0),  # 4±2mm crown-to-top-edge
    enforce_eye_band=False,  # Japan specifies no eye-line position
)

SPECS: dict[str, PhotoSpec] = {
    "schengen": SCHENGEN_SPEC,
    "japan": JAPAN_SPEC,
}

# Backwards-compatible default used by existing callers and tests.
DEFAULT_SPEC = SCHENGEN_SPEC
