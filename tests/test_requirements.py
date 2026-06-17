from schengen_visa_photo_skill.requirements import DEFAULT_SPEC


def test_default_pixel_requirements() -> None:
    assert DEFAULT_SPEC.output_width_px == 413
    assert DEFAULT_SPEC.output_height_px == 531
    # Head height = 70-80% of image height.
    assert DEFAULT_SPEC.head_height_px == (372, 425)
    assert DEFAULT_SPEC.head_width_px == (189, 295)
    assert DEFAULT_SPEC.top_margin_px == (24, 71)
    assert DEFAULT_SPEC.chin_to_bottom_min_px == 47
    # Eye line = 50-70% from the bottom edge.
    assert DEFAULT_SPEC.eye_from_bottom_px == (266, 372)


def test_targets_sit_inside_their_bands() -> None:
    lo, hi = DEFAULT_SPEC.head_height_px
    assert lo <= DEFAULT_SPEC.target_head_height_px <= hi
    lo, hi = DEFAULT_SPEC.top_margin_px
    assert lo <= DEFAULT_SPEC.target_top_margin_px <= hi


def test_pixels_per_mm_match_300_dpi() -> None:
    # 35x45mm at 300 DPI maps to ~11.8 px/mm on both axes.
    assert round(DEFAULT_SPEC.px_per_mm_x, 1) == 11.8
    assert round(DEFAULT_SPEC.px_per_mm_y, 1) == 11.8
