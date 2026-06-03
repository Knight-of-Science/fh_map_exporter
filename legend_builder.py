"""Build water-depth legend PNGs from config palettes.

Usage:
    python legend_builder.py
"""

from pathlib import Path
from typing import Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from utils.config import (
    BASE_LAYER_TERRAIN_RECOLOR_WATER_AS_WATER,
    FINAL_DIR,
    ID_RECOLOR,
    LEGEND_BORDER_COLOR,
    LEGEND_DEPTH_TEXT_FONT_SIZE,
    LEGEND_DISCLAIMER_STRING,
    LEGEND_FILL_COLOR,
    LEGEND_LINE_SPACING,
    LEGEND_SIMPLE_TITLE_STRING,
    LEGEND_SQUARES_SIZE,
    LEGEND_TEXT_COLOR,
    LEGEND_TITLE_STRING,
    LEGEND_TITLE_FONT_SIZE,
    WATER_DEPTH_COLORS,
    WATER_DEPTH_COLORS_SIMPLE,
    WATER_DEPTH_LEGEND,
    WATER_DEPTH_LEGEND_SIMPLE,
)


ASSEMBLY_DIR = "assembly"
LEGEND_NOT_SHOWN_X_COLOR = "#CC2222"


def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    s = hex_str.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"expected #RRGGBB color, got {hex_str!r}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _blend_rgb_average(*colors: Tuple[int, int, int]) -> Tuple[int, int, int]:
    n = max(len(colors), 1)
    return tuple(
        int(round(sum(color[i] for color in colors) / n))
        for i in range(3)
    )


def _base_water_rgb() -> Tuple[int, int, int]:
    water = _hex_to_rgb(ID_RECOLOR.get("water", "#FFFFFF"))
    if not BASE_LAYER_TERRAIN_RECOLOR_WATER_AS_WATER:
        return water
    terrain = _hex_to_rgb(ID_RECOLOR.get("terrain", "#FFFFFF"))
    return _blend_rgb_average(terrain, water)


def _step5_water_multiply_rgb(palette_hex: str) -> Tuple[int, int, int]:
    """Match base_layer's full-alpha water multiply for a flat swatch.

    Map-specific shades, highs/lows, contours, and AO are intentionally not
    included because they vary by location rather than palette key.
    """
    base = _base_water_rgb()
    water = _hex_to_rgb(palette_hex)
    return tuple(
        int(round(base[i] * (water[i] / 255.0)))
        for i in range(3)
    )


def _load_font(size: int) -> ImageFont.ImageFont:
    for font_name in (
        "consola.ttf",
        "Consolas.ttf",
        "DejaVuSansMono.ttf",
        "cour.ttf",
        "arial.ttf",
        "segoeui.ttf",
        "DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def build_legend(
    palette: dict[str, str],
    legend_rows: Sequence[Tuple[str, str]],
    out_path: Path,
    title: str,
) -> None:
    border_rgb = _hex_to_rgb(LEGEND_BORDER_COLOR)
    fill_rgb = _hex_to_rgb(LEGEND_FILL_COLOR)
    text_rgb = _hex_to_rgb(LEGEND_TEXT_COLOR)

    square = int(LEGEND_SQUARES_SIZE)
    line_gap = int(LEGEND_LINE_SPACING)
    pad_x = max(24, square)
    pad_y = max(20, square)
    square_text_gap = max(12, square // 2)
    title_gap = max(14, line_gap + 4)
    border_w = 2

    title_font = _load_font(int(LEGEND_TITLE_FONT_SIZE))
    line_font = _load_font(int(LEGEND_DEPTH_TEXT_FONT_SIZE))

    scratch = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(scratch)
    title = str(title)
    title_w, title_h = _text_size(draw, title, title_font)
    text_sizes = [_text_size(draw, text, line_font) for _, text in legend_rows]
    disclaimer = str(LEGEND_DISCLAIMER_STRING)
    disclaimer_size = (
        _text_size(draw, disclaimer, line_font)
        if disclaimer
        else (0, 0)
    )
    text_w = max((w for w, _ in text_sizes), default=0)
    text_h = max((h for _, h in text_sizes), default=square)
    row_h = max(square, text_h)

    content_w = max(
        title_w,
        square + square_text_gap + text_w,
        disclaimer_size[0],
    )
    rows_h = (
        len(legend_rows) * row_h
        + max(len(legend_rows) - 1, 0) * line_gap
    )
    disclaimer_gap = title_gap if disclaimer else 0
    width = content_w + pad_x * 2
    height = (
        pad_y * 2
        + title_h
        + title_gap
        + rows_h
        + disclaimer_gap
        + disclaimer_size[1]
    )

    img = Image.new("RGB", (width, height), fill_rgb)
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        (0, 0, width - 1, height - 1),
        outline=border_rgb,
        width=border_w,
    )

    title_x = (width - title_w) // 2
    y = pad_y
    draw.text((title_x, y), title, fill=text_rgb, font=title_font)
    y += title_h + title_gap

    for key, text in legend_rows:
        color_hex = palette.get(key)
        if color_hex is None:
            raise KeyError(f"{key!r} is missing from palette for {out_path}")
        swatch_rgb = _step5_water_multiply_rgb(color_hex)
        square_y = y + (row_h - square) // 2
        draw.rectangle(
            (pad_x, square_y, pad_x + square - 1, square_y + square - 1),
            fill=swatch_rgb,
            outline=border_rgb,
            width=border_w,
        )
        if "--" not in text and ">" not in text and "<" not in text:
            x0 = pad_x + 3
            y0 = square_y + 3
            x1 = pad_x + square - 4
            y1 = square_y + square - 4
            x_rgb = _hex_to_rgb(LEGEND_NOT_SHOWN_X_COLOR)
            draw.line((x0, y0, x1, y1), fill=x_rgb, width=3)
            draw.line((x0, y1, x1, y0), fill=x_rgb, width=3)
        text_y = y + (row_h - text_h) // 2
        draw.text(
            (pad_x + square + square_text_gap, text_y),
            text,
            fill=text_rgb,
            font=line_font,
        )
        y += row_h + line_gap

    if disclaimer:
        y += disclaimer_gap - line_gap
        draw.text((pad_x, y), disclaimer, fill=text_rgb, font=line_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    print(f"saved {out_path}")


def main() -> int:
    out_dir = FINAL_DIR / ASSEMBLY_DIR
    build_legend(
        WATER_DEPTH_COLORS,
        WATER_DEPTH_LEGEND,
        out_dir / "legend.png",
        LEGEND_TITLE_STRING,
    )
    build_legend(
        WATER_DEPTH_COLORS_SIMPLE,
        WATER_DEPTH_LEGEND_SIMPLE,
        out_dir / "legend_simple.png",
        LEGEND_SIMPLE_TITLE_STRING,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
