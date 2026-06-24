from PIL import Image

from schengen_visa_photo_skill.sheet import build_print_sheet, plan_sheet


def test_japan_square_fits_six_per_4x6() -> None:
    layout = plan_sheet((531, 531), paper="4x6", dpi=300)
    assert layout.paper_px == (1200, 1800)
    assert (layout.columns, layout.rows) == (2, 3)
    assert layout.copies == 6


def test_schengen_portrait_fills_eight_per_4x6() -> None:
    # 35x45mm photos pack tighter on the long edge, so the layout picks the
    # paper orientation that yields the most copies (4x2 landscape = 8).
    layout = plan_sheet((413, 531), paper="4x6", dpi=300)
    assert layout.copies == 8
    assert (layout.columns, layout.rows) == (4, 2)


def test_build_sheet_matches_paper_and_tiles_native_pixels() -> None:
    photo = Image.new("RGB", (531, 531), (10, 20, 30))
    sheet, layout = build_print_sheet(photo, paper="4x6", dpi=300)
    assert sheet.size == layout.paper_px == (1200, 1800)
    # A copy is pasted at native size (no scaling), so the exact photo color is
    # present away from the gray cut borders.
    assert sheet.getpixel((sheet.width // 4, sheet.height // 6)) == (10, 20, 30)
