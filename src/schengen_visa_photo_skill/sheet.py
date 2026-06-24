from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

# Common photo-paper sizes in millimeters, stored portrait (short x long). The
# sheet is laid out in whichever paper orientation packs the most copies.
PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "4x6": (101.6, 152.4),
    "10x15": (101.6, 152.4),
    "5x7": (127.0, 177.8),
    "13x18": (127.0, 177.8),
    "a4": (210.0, 297.0),
}

MM_PER_INCH = 25.4


@dataclass(frozen=True)
class SheetLayout:
    paper: str
    paper_px: tuple[int, int]
    columns: int
    rows: int
    copies: int
    dpi: int


def _grid_for(paper_w: int, paper_h: int, cell_w: int, cell_h: int, gap: int) -> tuple[int, int]:
    # Number of cells that fit along an axis of length `total` is the largest n
    # with n*cell + (n-1)*gap <= total, i.e. floor((total + gap) / (cell + gap)).
    cols = max(0, (paper_w + gap) // (cell_w + gap))
    rows = max(0, (paper_h + gap) // (cell_h + gap))
    return cols, rows


def plan_sheet(
    photo_size: tuple[int, int],
    *,
    paper: str = "4x6",
    dpi: int = 300,
    gap_mm: float = 2.0,
) -> SheetLayout:
    """Choose paper orientation and grid that fit the most copies of the photo."""
    if paper not in PAPER_SIZES_MM:
        raise ValueError(f"Unknown paper size {paper!r}; choices: {sorted(PAPER_SIZES_MM)}")
    short_mm, long_mm = PAPER_SIZES_MM[paper]
    cell_w, cell_h = photo_size
    gap = round(gap_mm / MM_PER_INCH * dpi)

    best: tuple[int, int, int, int, int] | None = None  # copies, cols, rows, paper_w, paper_h
    for pw_mm, ph_mm in ((short_mm, long_mm), (long_mm, short_mm)):
        paper_w = round(pw_mm / MM_PER_INCH * dpi)
        paper_h = round(ph_mm / MM_PER_INCH * dpi)
        cols, rows = _grid_for(paper_w, paper_h, cell_w, cell_h, gap)
        copies = cols * rows
        if best is None or copies > best[0]:
            best = (copies, cols, rows, paper_w, paper_h)

    copies, cols, rows, paper_w, paper_h = best
    if copies < 1:
        raise RuntimeError(
            f"Photo {cell_w}x{cell_h}px does not fit on {paper} paper at {dpi} DPI"
        )
    return SheetLayout(paper=paper, paper_px=(paper_w, paper_h), columns=cols, rows=rows, copies=copies, dpi=dpi)


def build_print_sheet(
    photo: Image.Image,
    *,
    paper: str = "4x6",
    dpi: int = 300,
    gap_mm: float = 2.0,
    draw_cut_lines: bool = True,
    background: tuple[int, int, int] = (255, 255, 255),
) -> tuple[Image.Image, SheetLayout]:
    """Tile copies of `photo` onto a print sheet at native pixels.

    The photo is pasted 1:1 (never resized) so its physical print size stays
    exact at the given DPI. Copies are packed into the largest grid that fits,
    centered on the paper, with a thin gray border around each as a cut guide.
    """
    layout = plan_sheet(photo.size, paper=paper, dpi=dpi, gap_mm=gap_mm)
    paper_w, paper_h = layout.paper_px
    cell_w, cell_h = photo.size
    gap = round(gap_mm / MM_PER_INCH * dpi)

    block_w = layout.columns * cell_w + (layout.columns - 1) * gap
    block_h = layout.rows * cell_h + (layout.rows - 1) * gap
    margin_x = (paper_w - block_w) // 2
    margin_y = (paper_h - block_h) // 2

    sheet = Image.new("RGB", (paper_w, paper_h), background)
    draw = ImageDraw.Draw(sheet)
    rgb_photo = photo.convert("RGB")
    for r in range(layout.rows):
        for c in range(layout.columns):
            x = margin_x + c * (cell_w + gap)
            y = margin_y + r * (cell_h + gap)
            sheet.paste(rgb_photo, (x, y))
            if draw_cut_lines:
                # Border sits just outside the photo so the line itself is cut away.
                draw.rectangle((x - 1, y - 1, x + cell_w, y + cell_h), outline=(170, 170, 170), width=1)
    return sheet, layout
