from schengen_visa_photo_skill.processor import CropOptions, check_plan, plan_crop_from_geometry
from schengen_visa_photo_skill.requirements import DEFAULT_SPEC
from schengen_visa_photo_skill.landmarks import FaceGeometry


def test_crop_plan_targets_midpoints() -> None:
    plan = plan_crop_from_geometry(
        center_x=1000,
        crown_y=500,
        head_height=1000,
        head_width=650,
        spec=DEFAULT_SPEC,
    )
    assert plan.estimated_head_height_px == DEFAULT_SPEC.target_head_height_px
    assert plan.estimated_top_margin_px == DEFAULT_SPEC.target_top_margin_px
    assert plan.crop_box_source[0] < 1000 < plan.crop_box_source[2]


def test_check_plan_passes_nominal_geometry() -> None:
    plan = plan_crop_from_geometry(
        center_x=1000,
        crown_y=500,
        head_height=1000,
        head_width=650,
        spec=DEFAULT_SPEC,
    )
    checks = check_plan(plan, jpeg_size=80_000, spec=DEFAULT_SPEC)
    assert all(checks.values())


def test_scale_is_driven_by_head_height_only() -> None:
    # Width is never traded against head height: a very wide head keeps the same
    # head-height-driven scale, and only the width check reflects the difference.
    narrow = plan_crop_from_geometry(center_x=1000, crown_y=500, head_height=1000, head_width=650, spec=DEFAULT_SPEC)
    wide = plan_crop_from_geometry(center_x=1000, crown_y=500, head_height=1000, head_width=900, spec=DEFAULT_SPEC)
    assert narrow.scale == wide.scale
    assert wide.estimated_head_width_px > narrow.estimated_head_width_px


def test_crop_plan_prioritizes_eye_band_when_eyes_too_low() -> None:
    plan = plan_crop_from_geometry(
        center_x=1000,
        crown_y=500,
        head_height=1000,
        head_width=650,
        eye_y=1300,
        spec=DEFAULT_SPEC,
    )
    assert plan.estimated_top_margin_px < DEFAULT_SPEC.target_top_margin_px
    assert plan.priority_notes


def test_crop_plan_accepts_agent_adjustments() -> None:
    base = plan_crop_from_geometry(
        center_x=1000,
        crown_y=500,
        head_height=1000,
        head_width=650,
        spec=DEFAULT_SPEC,
    )
    adjusted = plan_crop_from_geometry(
        center_x=1000,
        crown_y=500,
        head_height=1000,
        head_width=650,
        spec=DEFAULT_SPEC,
        options=CropOptions(scale_multiplier=0.95, nudge_y_px=10),
    )
    assert adjusted.scale < base.scale
    assert adjusted.estimated_top_margin_px != base.estimated_top_margin_px


def test_face_geometry_can_report_silhouette_source() -> None:
    geom = FaceGeometry(chin_y=300, crown_y=50, head_height=250, head_width=180, center_x=200, source="plain_background_silhouette")
    assert geom.source == "plain_background_silhouette"
