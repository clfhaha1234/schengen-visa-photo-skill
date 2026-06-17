from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhotoSpec:
    """Schengen / ICAO Doc 9303 visa photo standard.

    The print standard is 35mm x 45mm. The digital target is the widely
    accepted 413x531px image (35x45mm at 300 DPI). The dominant biometric
    rule is head height: the face from chin to crown must occupy 70-80% of
    the image height. Eye position and a small head clearance follow from it.
    """

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
            "output_width_px": self.output_width_px,
            "output_height_px": self.output_height_px,
            "head_width_px": list(self.head_width_px),
            "head_height_px": list(self.head_height_px),
            "head_height_ratio": list(self.head_height_ratio),
            "top_margin_px": list(self.top_margin_px),
            "chin_to_bottom_min_px": self.chin_to_bottom_min_px,
            "eye_from_bottom_px": list(self.eye_from_bottom_px),
            "inter_eye_min_px": self.inter_eye_min_px,
            "jpeg_size_bytes": list(self.jpeg_size_bytes),
        }


DEFAULT_SPEC = PhotoSpec()
