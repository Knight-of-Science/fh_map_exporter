"""Stitch step-4 bakes into world PNGs and assemble final composites.

Writes to ``export/_final/``: ``technical/`` (ao, heightmap_simple, contour),
``assembly/`` (base_layer, beaches, roads, fly_alert, contours, rdz, ranges),
optional legacy bridges_aim), and verbatim ``id/``, ``split_layers/``,
``svg_layers``.

Usage:
    python 5_finalize_exports.py
"""

import colorsys
import json
import random
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

import cv2
import numpy as np

from utils.config import (
    AO_DIR,
    BASE_LAYER_APPLY_AO,
    BASE_LAYER_CONTOUR_ALPHA_MULT,
    BASE_LAYER_DEBUG_CONTOURS,
    BASE_LAYER_HIDE_UNDERWATER_ROCKS,
    BASE_LAYER_SIMPLE_ENABLED,
    BASE_LAYER_DISABLE_TERRAIN_FILL_IN_WATER,
    BASE_LAYER_TERRAIN_RECOLOR_WATER_AS_WATER,
    BASE_LAYER_UNDERWATER_AO_ALPHA_MULT,
    BASE_LAYER_UNDERWATER_AO_ALPHA_MULTIPLIER,
    BASE_LAYER_UNDERWATER_AO_PARTIAL_COVERAGE,
    BEACHES_DIR,
    CENTRES_FILE,
    CONTOUR_INCLUDE_UNDERWATER_ROCKS,
    CONTOUR_OFFSET_M,
    CONTOUR_STEP_M,
    DEEP_WATER_DEPTH,
    DEPTH_COLOR_BLEND_MAX_OPACITY,
    DEPTH_COLOR_BLEND_TARGET_COLOR,
    DEPTH_COLOR_SCALING_ENABLED,
    DIVE_ALERT_COLOR,
    DISABLE_NON_WATER_ROCK_LAYERS,
    ENABLE_LEGACY_BRIDGE_AIM,
    FINAL_DIR,
    C_TITAN_DRAFT,
    C_TRIDENT_DRAFT,
    FLY_ALERT_PATTERN_FILE,
    HM_LANDSCAPE_DIR,
    HM_WATER_DIR,
    ID_DIR,
    ID_RECOLOR,
    INTEL_DEPTH,
    LAYER_COLORS,
    LAYER_ENABLED,
    LAYERS_DIR,
    LEGACY_BRIDGE_AIM_WATER_ERODE_PX,
    MEDIUM_WATER_DEPTH,
    MASK_FILE,
    PIXEL_SIZE_M,
    RDZ_PATTERN_FILE,
    RECOLOR_WATER_FLAG,
    ROADS_DIR,
    SHADES_BLUR_KSIZE,
    SHADES_BLUR_SIGMA,
    SHALLOW_DEPTH,
    SPLIT_LAYERS,
    SPLIT_LAYERS_DIR,
    SVG_LAYERS,
    SVG_LAYERS_DIR,
    TURBO_MODE_DOWNSAMPLE,
    UNDERWATER_CONTOUR_NORMAL_EXCLUSION_DISTANCE,
    WATER_DEPTH_COVERAGE_BLUR_KSIZE,
    WATER_DEPTH_COVERAGE_BLUR_SIGMA,
    WATER_DEPTH_COLORS,
    WATER_DEPTH_COLORS_SIMPLE,
    WATER_DEPTH_INTERPOLATE_COLORS,
    WATER_TREAT_DEEP_WATER_AS_WATER,
    WATER_COLOR_BY_GRADIENT,
    WATER_GRADIENT_BLACK_SLOPE,
    WATER_GRADIENT_SWEEP_PX,
    VIC_DEPTH,
    W_BLACKSTEELE_DRAFT,
    W_NAKKI_DRAFT,
    WRITE_ADDITIONAL_ASSEMBLY_LAYERS,
    WRITE_RDZ_DARK_ASSEMBLY_LAYER,
    HM_SPLIT_M,
    FLY_ALERT_MIN_M,
    FLY_ALERT_MAX_M,
)


# Output subdirectories inside FINAL_DIR.
TECHNICAL_DIR = "technical"
ASSEMBLY_DIR = "assembly"

# Gaussian blur applied to the contour overlay before it lands in assembly/.
CONTOURS_BLUR_KSIZE = 3

class _StepLogger:
    """Running "[i/N] ..." step counter with uniform alignment."""

    def __init__(self) -> None:
        self.total = 0
        self.i = 0

    def set_total(self, total: int) -> None:
        self.total = max(total, 1)

    @property
    def _w(self) -> int:
        return len(str(self.total))

    def step(self, msg: str) -> None:
        self.i += 1
        print(f"[{self.i:>{self._w}}/{self.total}] {msg}")

    def saved(self, path: Path) -> None:
        """Report a save as a step. Path is shown relative to FINAL_DIR."""
        try:
            short = path.relative_to(FINAL_DIR).as_posix()
        except ValueError:
            short = path.name
        self.step(f"saved  {short}")

    def info(self, msg: str) -> None:
        """Non-counted informational line, indented to match step output."""
        pad = " " * (self._w * 2 + 4)
        print(f"{pad}{msg}")


LOG = _StepLogger()


def load_centres() -> Dict[str, Tuple[int, int]]:
    with open(CENTRES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k: (int(v[0]), int(v[1])) for k, v in raw.items()}


def load_mask() -> np.ndarray:
    img = cv2.imread(str(MASK_FILE), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"mask not found: {MASK_FILE}")
    if TURBO_MODE_DOWNSAMPLE:
        img = _downsample_image(img, interpolation=cv2.INTER_NEAREST)
    return (img > 0).astype(np.uint8)


def _downsample_image(
    img: np.ndarray,
    interpolation: int = cv2.INTER_AREA,
) -> np.ndarray:
    h, w = img.shape[:2]
    return cv2.resize(
        img,
        (max(w // 2, 1), max(h // 2, 1)),
        interpolation=interpolation,
    )


def _scale_centres(
    centres: Dict[str, Tuple[int, int]],
) -> Dict[str, Tuple[int, int]]:
    if not TURBO_MODE_DOWNSAMPLE:
        return centres
    return {
        name: (int(round(cx * 0.5)), int(round(cy * 0.5)))
        for name, (cx, cy) in centres.items()
    }


def _tile_extents(mask: np.ndarray) -> Tuple[int, int]:
    return mask.shape[0] // 2, mask.shape[1] // 2


def canvas_size(
    centres: Dict[str, Tuple[int, int]],
    mask: np.ndarray,
) -> Tuple[int, int]:
    half_y, half_x = _tile_extents(mask)
    max_y = max_x = 0
    for cx, cy in centres.values():
        max_y = max(max_y, cy + half_y)
        max_x = max(max_x, cx + half_x)
    return max_y, max_x


def _build_tile_map(src_dir: Path) -> Dict[str, Path]:
    if not src_dir.is_dir():
        return {}
    return {p.stem.lower(): p for p in src_dir.glob("*.png")}


def _apply_hex_mask(tile: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if tile.ndim == 2:
        return tile * mask.astype(tile.dtype)
    return tile * mask.astype(tile.dtype)[:, :, None]


def _hex_to_bgr(hex_str: str) -> Tuple[int, int, int]:
    s = hex_str.lstrip("#")
    r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    return (b, g, r)


def _max_coverage(*coverages: np.ndarray | None) -> np.ndarray | None:
    present = [cov for cov in coverages if cov is not None]
    if not present:
        return None
    out = present[0].copy()
    for cov in present[1:]:
        np.maximum(out, cov, out=out)
    return out


def _random_bright_bgr(used: set, rng: random.Random) -> Tuple[int, int, int]:
    for _ in range(256):
        h = rng.random()
        s = rng.uniform(0.75, 1.0)
        v = rng.uniform(0.85, 1.0)
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        bgr = (int(round(b * 255)), int(round(g * 255)), int(round(r * 255)))
        if bgr not in used and bgr != (0, 0, 0):
            return bgr
    return (255, 255, 255)


def _assign_layer_color(
    name: str,
    palette: Dict[str, str],
    used: set,
    rng: random.Random,
) -> Tuple[int, int, int]:
    hex_str = palette.get(name) or palette.get(name.lower())
    if hex_str is not None:
        bgr = _hex_to_bgr(hex_str)
    else:
        bgr = _random_bright_bgr(used, rng)
    used.add(bgr)
    return bgr


def _compute_world_alpha(
    centres: Dict[str, Tuple[int, int]],
    mask: np.ndarray,
    height: int,
    width: int,
) -> np.ndarray:
    alpha = np.zeros((height, width), dtype=np.uint8)
    mask_u8 = (mask.astype(np.uint8) * 255)
    half_y, half_x = _tile_extents(mask)
    for cx, cy in centres.values():
        y1, y2 = cy - half_y, cy + half_y
        x1, x2 = cx - half_x, cx + half_x
        dst = alpha[y1:y2, x1:x2]
        np.maximum(dst, mask_u8, out=dst)
    return alpha


def _write_with_alpha(
    canvas: np.ndarray,
    alpha: np.ndarray,
    out_path: Path,
) -> None:
    if canvas.ndim == 2:
        bgra = np.zeros((*canvas.shape, 4), dtype=np.uint8)
        bgra[..., 0] = canvas
        bgra[..., 1] = canvas
        bgra[..., 2] = canvas
        bgra[..., 3] = alpha
    elif canvas.shape[2] == 3:
        bgra = np.dstack([canvas, alpha])
    else:
        bgra = canvas.copy()
        bgra[..., 3] = np.minimum(bgra[..., 3], alpha)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), bgra)


def _write_rgba(rgba: np.ndarray, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), rgba)


def stitch(
    tile_map: Dict[str, Path],
    centres: Dict[str, Tuple[int, int]],
    mask: np.ndarray,
    height: int,
    width: int,
    *,
    channels: int,
    dtype: np.dtype,
    read_flag: int,
) -> np.ndarray:
    """Paste every tile onto a world canvas; overlap resolved with np.maximum."""
    shape = (height, width) if channels == 1 else (height, width, channels)
    canvas = np.zeros(shape, dtype=dtype)
    total = len(centres)
    placed = 0
    half_y, half_x = _tile_extents(mask)

    for i, (name, (cx, cy)) in enumerate(centres.items(), 1):
        print(f"  {i}/{total}", end="\r")
        tile_path = tile_map.get(name.lower())
        if tile_path is None:
            continue

        tile = cv2.imread(str(tile_path), read_flag)
        if tile is None:
            print(f"\n  [WARN] unreadable tile: {tile_path}")
            continue
        if TURBO_MODE_DOWNSAMPLE:
            tile = _downsample_image(tile)

        if channels == 1 and tile.ndim == 3:
            tile = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
        elif channels == 3 and tile.ndim == 2:
            tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
        elif channels == 4 and tile.ndim == 2:
            tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGRA)
        elif channels == 4 and tile.ndim == 3 and tile.shape[2] == 3:
            tile = cv2.cvtColor(tile, cv2.COLOR_BGR2BGRA)

        if tile.dtype != dtype:
            tile = tile.astype(dtype)

        if tile.shape[:2] != mask.shape:
            tile = cv2.resize(
                tile,
                (mask.shape[1], mask.shape[0]),
                interpolation=cv2.INTER_AREA,
            )

        tile = _apply_hex_mask(tile, mask)

        y1, y2 = cy - half_y, cy + half_y
        x1, x2 = cx - half_x, cx + half_x
        dst = canvas[y1:y2, x1:x2]
        np.maximum(dst, tile, out=dst)
        placed += 1

    print(f"  {total}/{total}  ({placed} tiles placed)")
    return canvas


# ------------------------------------------------------------------------------
#  Heightmap-derived products (landscape + water)
# ------------------------------------------------------------------------------

def stitch_heightmap_landscape(
    centres: Dict[str, Tuple[int, int]],
    mask: np.ndarray,
    height: int,
    width: int,
) -> np.ndarray | None:
    if not HM_LANDSCAPE_DIR.is_dir():
        print(f"  [WARN] {HM_LANDSCAPE_DIR} not found; "
              f"skipping landscape heightmap products")
        return None
    print(f"\n=== stitching heightmap_landscape ===")
    hm_map = _build_tile_map(HM_LANDSCAPE_DIR)
    return stitch(
        hm_map, centres, mask, height, width,
        channels=1, dtype=np.uint16, read_flag=cv2.IMREAD_UNCHANGED,
    )


def compute_highs_lows(
    raw_landscape: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return (highs, lows) as uint8 grayscale arrays (no disk writes)."""
    void = raw_landscape == 0
    meters = (raw_landscape.astype(np.float32) - 32768.0) / 100.0
    delta = meters - HM_SPLIT_M
    highs = np.clip(np.round(delta * 2.0), 0, 255).astype(np.uint8)
    lows = np.clip(np.round(-delta * 2.0), 0, 255).astype(np.uint8)
    highs[void] = 0
    lows[void] = 0
    return highs, lows


def build_fly_alert(
    raw_landscape: np.ndarray,
    height: int,
    width: int,
    rocks_cov: np.ndarray | None,
    out_path: Path,
) -> None:
    print("  building fly_alert...")
    void = raw_landscape == 0
    meters = (raw_landscape.astype(np.float32) - 32768.0) / 100.0
    denom = max(FLY_ALERT_MAX_M - FLY_ALERT_MIN_M, 1e-6)
    fly_ratio = (meters - FLY_ALERT_MIN_M) / denom
    fly_alert = np.clip(np.round(fly_ratio * 255.0), 0, 255).astype(np.uint8)
    fly_alert[void] = 0
    if rocks_cov is not None:
        fly_alert = (
            (fly_alert.astype(np.uint16) * rocks_cov.astype(np.uint16) + 127)
            // 255
        ).astype(np.uint8)
    pattern = cv2.imread(str(FLY_ALERT_PATTERN_FILE), cv2.IMREAD_UNCHANGED)
    if pattern is None:
        print(f"  [WARN] {FLY_ALERT_PATTERN_FILE} not found; "
              f"falling back to solid white fly_alert")
        fly_rgba = np.zeros((height, width, 4), dtype=np.uint8)
        fly_rgba[..., 0:3] = 255
        fly_rgba[..., 3] = fly_alert
    else:
        if TURBO_MODE_DOWNSAMPLE:
            pattern = _downsample_image(pattern)
        if pattern.ndim == 2:
            pattern = cv2.cvtColor(pattern, cv2.COLOR_GRAY2BGRA)
        elif pattern.shape[2] == 3:
            pattern = cv2.cvtColor(pattern, cv2.COLOR_BGR2BGRA)
        ph, pw = pattern.shape[:2]
        if (ph, pw) != (height, width):
            reps_y = (height + ph - 1) // ph
            reps_x = (width + pw - 1) // pw
            pattern = np.tile(pattern, (reps_y, reps_x, 1))[:height, :width]
        fly_rgba = pattern.copy()
        coef = fly_alert.astype(np.uint16)
        fly_rgba[..., 3] = (
            (fly_rgba[..., 3].astype(np.uint16) * coef + 127) // 255
        ).astype(np.uint8)
    _write_rgba(fly_rgba, out_path)
    LOG.saved(out_path)


def build_contour(
    raw_landscape: np.ndarray,
    contour_mask: np.ndarray | None,
    water_cov: np.ndarray | None,
    height: int,
    width: int,
) -> np.ndarray:
    """Return the contour RGBA array (black lines with alpha)."""
    print("  building contour...")
    void = raw_landscape == 0
    step_raw = max(int(round(float(CONTOUR_STEP_M) * 100.0)), 1)
    offset_raw = int(round(float(CONTOUR_OFFSET_M) * 100.0 + 32768.0))
    step = np.floor_divide(
        raw_landscape.astype(np.int32) - offset_raw,
        step_raw,
    ).astype(np.int32)
    normal_contour = np.zeros(step.shape, dtype=bool)
    normal_contour[1:, :]  |= (step[1:, :]  - step[:-1, :]) == 1
    normal_contour[:-1, :] |= (step[:-1, :] - step[1:,  :]) == 1
    normal_contour[:, 1:]  |= (step[:, 1:]  - step[:, :-1]) == 1
    normal_contour[:, :-1] |= (step[:, :-1] - step[:, 1:])  == 1
    extra_levels_m = (
        SHALLOW_DEPTH,
        VIC_DEPTH,
        C_TRIDENT_DRAFT,
        W_NAKKI_DRAFT,
        W_BLACKSTEELE_DRAFT,
        C_TITAN_DRAFT,
        INTEL_DEPTH,
        MEDIUM_WATER_DEPTH,
        DEEP_WATER_DEPTH,
    )
    raw_i32 = raw_landscape.astype(np.int32)
    water_hit = water_cov > 0 if water_cov is not None else np.zeros(
        step.shape, dtype=bool,
    )
    extra_contour = np.zeros(step.shape, dtype=bool)
    exclude_normal = np.zeros(step.shape, dtype=bool)
    exclusion_raw = max(
        int(round(float(UNDERWATER_CONTOUR_NORMAL_EXCLUSION_DISTANCE) * 100.0)),
        0,
    )
    for level_m in extra_levels_m:
        threshold = int(round(32768.0 - float(level_m) * 100.0))
        above = raw_i32 >= threshold
        extra_contour[1:, :]  |= above[1:, :]  != above[:-1, :]
        extra_contour[:-1, :] |= above[:-1, :] != above[1:,  :]
        extra_contour[:, 1:]  |= above[:, 1:]  != above[:, :-1]
        extra_contour[:, :-1] |= above[:, :-1] != above[:, 1:]
        if exclusion_raw > 0:
            exclude_normal |= (
                (np.abs(raw_i32 - threshold) <= exclusion_raw)
                & water_hit
            )
    extra_contour &= water_hit
    normal_contour &= ~exclude_normal
    contour = normal_contour | extra_contour
    contour &= ~void
    if contour_mask is not None:
        contour &= contour_mask
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 3] = np.where(contour, 255, 0).astype(np.uint8)
    return rgba


def build_contour_mask(
    terrain_cov: np.ndarray | None,
    rocks_cov: np.ndarray | None,
    water_cov: np.ndarray | None,
    raw_landscape: np.ndarray,
    raw_water: np.ndarray | None,
) -> np.ndarray | None:
    """Old contour mask (terrain) plus underwater rocks.

    Rocks count only where water exists and the landscape hit is below
    the water surface, so above-ground rocks do not introduce contours.
    """
    out: np.ndarray | None = None
    if terrain_cov is not None:
        out = terrain_cov > 0

    if (
        CONTOUR_INCLUDE_UNDERWATER_ROCKS
        and rocks_cov is not None
        and water_cov is not None
        and raw_water is not None
    ):
        underwater_rocks = (
            (rocks_cov > 0)
            & (water_cov > 0)
            & (raw_landscape != 0)
            & (raw_water != 0)
            & (raw_water > raw_landscape)
        )
        out = underwater_rocks if out is None else (out | underwater_rocks)

    return out


def stitch_heightmap_water(
    centres: Dict[str, Tuple[int, int]],
    mask: np.ndarray,
    height: int,
    width: int,
) -> np.ndarray | None:
    if not HM_WATER_DIR.is_dir():
        print(f"  [WARN] {HM_WATER_DIR} not found; skipping heightmap_simple")
        return None
    print(f"\n=== stitching heightmap_water ===")
    hm_map = _build_tile_map(HM_WATER_DIR)
    return stitch(
        hm_map, centres, mask, height, width,
        channels=1, dtype=np.uint16, read_flag=cv2.IMREAD_UNCHANGED,
    )


def build_heightmap_simple(
    raw_water: np.ndarray,
    world_alpha: np.ndarray,
    out_path: Path,
) -> None:
    print("  building heightmap_simple...")
    void = raw_water == 0
    meters = (raw_water.astype(np.float32) - 32768.0) / 100.0
    simple = np.clip(np.round(60.0 + meters * 2.0), 0, 255).astype(np.uint8)
    simple[void] = 0
    _write_with_alpha(simple, world_alpha, out_path)
    LOG.saved(out_path)


def _compute_water_depth_m(
    raw_landscape: np.ndarray,
    raw_water: np.ndarray,
    water_cov: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (depth_m, valid) where depth is measured from water surface
    down to the first landscape hit. ``raw_landscape`` already includes
    terrain plus whitelisted underwater geometry such as rocks."""
    valid = (raw_landscape != 0) & (raw_water != 0) & (water_cov > 0)
    land_m = (raw_landscape.astype(np.float32) - 32768.0) / 100.0
    water_m = (raw_water.astype(np.float32) - 32768.0) / 100.0
    depth = water_m - land_m
    valid &= depth > 0.0
    return depth, valid


def underwater_rocks_mask(
    rocks_cov: np.ndarray | None,
    water_cov: np.ndarray | None,
    raw_landscape: np.ndarray | None,
    raw_water: np.ndarray | None,
) -> np.ndarray | None:
    if (
        rocks_cov is None
        or water_cov is None
        or raw_landscape is None
        or raw_water is None
    ):
        return None
    return (
        (rocks_cov > 0)
        & (water_cov > 0)
        & (raw_landscape != 0)
        & (raw_water != 0)
        & (raw_water > raw_landscape)
    )


def attenuate_underwater_ao(
    ao: np.ndarray | None,
    water_cov: np.ndarray | None,
) -> np.ndarray | None:
    if ao is None or water_cov is None or not BASE_LAYER_UNDERWATER_AO_ALPHA_MULT:
        return ao

    mult = float(BASE_LAYER_UNDERWATER_AO_ALPHA_MULTIPLIER)
    if mult >= 1.0:
        return ao

    mult = max(mult, 0.0)
    out = ao.astype(np.float32)
    target = 255.0 - ((255.0 - out) * mult)
    if BASE_LAYER_UNDERWATER_AO_PARTIAL_COVERAGE:
        water_alpha = water_cov.astype(np.float32) / 255.0
        if water_alpha.any():
            out = out * (1.0 - water_alpha) + target * water_alpha
    else:
        underwater = water_cov > 0
        if underwater.any():
            out[underwater] = target[underwater]
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def build_dive_alert(
    raw_landscape: np.ndarray,
    raw_water: np.ndarray,
    water_cov: np.ndarray,
    world_alpha: np.ndarray,
    rocks_cov: np.ndarray | None,
    out_path: Path,
) -> None:
    """RGBA overlay coloured DIVE_ALERT_COLOR wherever submerged rocks
    sit below a water surface. Alpha fades linearly from 255 at the
    water surface (depth 0) to 0 at DEEP_WATER_DEPTH, then is gated by
    (rocks_cov * water_cov)."""
    print("  building dive_alert...")
    height, width = raw_landscape.shape

    valid = (raw_landscape != 0) & (raw_water != 0)
    if not valid.any():
        print("  [info] no submerged pixels; dive_alert skipped")
        return

    land_m = (raw_landscape.astype(np.float32) - 32768.0) / 100.0
    water_m = (raw_water.astype(np.float32) - 32768.0) / 100.0
    depth = water_m - land_m

    denom = max(float(DEEP_WATER_DEPTH), 1e-6)
    ratio = np.clip(1.0 - depth / denom, 0.0, 1.0)
    if rocks_cov is None:
        print("  [WARN] rocks coverage missing; dive_alert skipped")
        return
    gate_u16 = (
        (rocks_cov.astype(np.uint16) * water_cov.astype(np.uint16) + 127)
        // 255
    )
    alpha_f = ratio * (gate_u16.astype(np.float32) / 255.0)
    alpha = np.clip(np.round(alpha_f * 255.0), 0, 255).astype(np.uint8)
    alpha[~valid] = 0
    alpha[depth <= 0] = 0
    alpha = np.minimum(alpha, world_alpha)

    dive_bgr = _hex_to_bgr(DIVE_ALERT_COLOR)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    hit = alpha > 0
    rgba[hit, 0] = dive_bgr[0]
    rgba[hit, 1] = dive_bgr[1]
    rgba[hit, 2] = dive_bgr[2]
    rgba[..., 3] = alpha

    _write_rgba(rgba, out_path)
    LOG.saved(out_path)


# ------------------------------------------------------------------------------
#  Terrain/water recolor + shades (in-memory; feed base_layer)
# ------------------------------------------------------------------------------

def build_terrain_recolor(
    id_coverage: Dict[str, np.ndarray],
    world_alpha: np.ndarray,
    height: int,
    width: int,
    fill_source_mask: np.ndarray | None = None,
    fill_block_mask: np.ndarray | None = None,
) -> np.ndarray | None:
    """Weighted-blend BGR image (no alpha); uncovered in-bounds pixels
    are filled via nearest-claimed propagation. Returns None when no
    non-water ID category has coverage."""
    colored = np.zeros((height, width, 3), dtype=np.float32)
    weight = np.zeros((height, width), dtype=np.float32)
    for cat, hex_color in ID_RECOLOR.items():
        if cat in ("water", "deep_water"):
            if not BASE_LAYER_TERRAIN_RECOLOR_WATER_AS_WATER:
                continue
            if cat == "water":
                hex_color = ID_RECOLOR.get("water", hex_color)
        cov = id_coverage.get(cat)
        if cov is None:
            continue
        color = np.array(_hex_to_bgr(hex_color), dtype=np.float32)
        cov_f = cov.astype(np.float32)
        colored += cov_f[..., None] * color
        weight += cov_f

    out_bgr = np.zeros((height, width, 3), dtype=np.uint8)
    hit = weight > 0
    if not hit.any():
        return None
    out_bgr[hit] = np.clip(
        colored[hit] / weight[hit, None], 0, 255
    ).astype(np.uint8)
    in_bounds = world_alpha > 0
    need_fill = in_bounds & ~hit
    if fill_block_mask is not None:
        need_fill &= ~fill_block_mask
    if need_fill.any():
        fill_hit = hit
        if fill_source_mask is not None:
            fill_hit = hit & fill_source_mask
        if not fill_hit.any():
            terrain_bgr = _hex_to_bgr(ID_RECOLOR.get("terrain", "#000000"))
            out_bgr[need_fill] = terrain_bgr
            return out_bgr
        src_zero = (~fill_hit).astype(np.uint8)
        _, labels = cv2.distanceTransformWithLabels(
            src_zero, cv2.DIST_L2, 3,
            labelType=cv2.DIST_LABEL_PIXEL,
        )
        ys, xs = np.where(fill_hit)
        src_y = np.empty(ys.size + 1, dtype=np.int32)
        src_x = np.empty(xs.size + 1, dtype=np.int32)
        src_y[0] = 0; src_x[0] = 0
        src_y[1:] = ys; src_x[1:] = xs
        lab = np.clip(labels[need_fill].astype(np.int64), 1, ys.size)
        out_bgr[need_fill] = out_bgr[src_y[lab], src_x[lab]]
    return out_bgr


def _water_depth_stops(
    water_hex: str,
    palette: Dict[str, str],
) -> list[tuple[float, str, str]]:
    if "C_TRIDENT_DRAFT" in palette:
        stop_specs = [
            (0.0, "SHALLOW_DEPTH"),
            (float(SHALLOW_DEPTH), "SHALLOW_DEPTH"),
            (float(VIC_DEPTH), "VIC_DEPTH"),
            (float(C_TRIDENT_DRAFT), "C_TRIDENT_DRAFT"),
            (float(W_NAKKI_DRAFT), "W_NAKKI_DRAFT"),
            (float(W_BLACKSTEELE_DRAFT), "W_BLACKSTEELE_DRAFT"),
            (float(C_TITAN_DRAFT), "C_TITAN_DRAFT"),
            (float(INTEL_DEPTH), "INTEL_DEPTH"),
            (float(MEDIUM_WATER_DEPTH), "MEDIUM_WATER_DEPTH"),
            (float(DEEP_WATER_DEPTH), "SOMEWHAT_DEEP_WATER_DEPTH"),
        ]
    else:
        stop_specs = [
            (0.0, "SHALLOW_DEPTH"),
            (float(SHALLOW_DEPTH), "SHALLOW_DEPTH"),
            (float(VIC_DEPTH), "VIC_DEPTH"),
            (float(C_TITAN_DRAFT), "C_TITAN_DRAFT"),
            (float(INTEL_DEPTH), "INTEL_DEPTH"),
            (float(MEDIUM_WATER_DEPTH), "MEDIUM_WATER_DEPTH"),
            (float(DEEP_WATER_DEPTH), "SOMEWHAT_DEEP_WATER_DEPTH"),
        ]
    stops = [
        (depth, name, palette.get(name, water_hex))
        for depth, name in stop_specs
    ]
    return sorted(stops, key=lambda item: item[0])


def _blur_water_coverage(coverage: np.ndarray) -> np.ndarray:
    k = int(WATER_DEPTH_COVERAGE_BLUR_KSIZE)
    if k <= 1:
        return coverage
    if k % 2 == 0:
        k += 1
    return cv2.GaussianBlur(
        coverage, (k, k), float(WATER_DEPTH_COVERAGE_BLUR_SIGMA),
    )


def build_water_recolor(
    water_cov: np.ndarray | None,
    deep_water_cov: np.ndarray | None,
    world_alpha: np.ndarray,
    height: int,
    width: int,
    depth_m: np.ndarray | None = None,
    depth_valid: np.ndarray | None = None,
    raw_landscape: np.ndarray | None = None,
    palette: Dict[str, str] | None = None,
) -> np.ndarray | None:
    """RGBA water tint with alpha = water_cov ∧ world_alpha.

    When step-5 heightmaps are available, color is interpolated by water
    depth. Otherwise this falls back to the old solid ID_RECOLOR['water'].
    """
    palette = WATER_DEPTH_COLORS if palette is None else palette
    water_hex = palette.get(
        "SHALLOW_DEPTH",
        ID_RECOLOR.get("water"),
    )
    if water_cov is None or water_hex is None:
        return None
    bgr = _hex_to_bgr(water_hex)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    hit = water_cov > 0
    rgba[hit, 0] = bgr[0]
    rgba[hit, 1] = bgr[1]
    rgba[hit, 2] = bgr[2]
    if WATER_COLOR_BY_GRADIENT and raw_landscape is not None:
        slope_hit = hit & (raw_landscape != 0)
        if depth_valid is not None:
            slope_hit &= depth_valid
        if slope_hit.any():
            land_m = (raw_landscape.astype(np.float32) - 32768.0) / 100.0
            land_m[~slope_hit] = 0.0
            gx = cv2.Sobel(
                land_m, cv2.CV_32F, 1, 0,
                ksize=3, scale=1.0 / (8.0 * float(PIXEL_SIZE_M)),
                borderType=cv2.BORDER_REPLICATE,
            )
            gy = cv2.Sobel(
                land_m, cv2.CV_32F, 0, 1,
                ksize=3, scale=1.0 / (8.0 * float(PIXEL_SIZE_M)),
                borderType=cv2.BORDER_REPLICATE,
            )
            grad = cv2.magnitude(gx, gy)
            black_at = max(float(WATER_GRADIENT_BLACK_SLOPE), 1e-6)

            full_kernel = np.ones((3, 3), dtype=np.uint8)
            full_hit = cv2.erode(
                slope_hit.astype(np.uint8), full_kernel,
                iterations=1,
            ) > 0
            grad[~full_hit] = black_at

            sweep_px = max(int(WATER_GRADIENT_SWEEP_PX), 1)
            if sweep_px > 1:
                if sweep_px % 2 == 0:
                    sweep_px += 1
                kernel = np.ones((sweep_px, sweep_px), dtype=np.uint8)
                grad = cv2.dilate(grad, kernel, iterations=1)

            gray = np.clip(
                np.round(255.0 * (1.0 - grad / black_at)),
                0, 255,
            ).astype(np.uint8)
            rgba[slope_hit, 0] = gray[slope_hit]
            rgba[slope_hit, 1] = gray[slope_hit]
            rgba[slope_hit, 2] = gray[slope_hit]
    elif depth_m is not None and depth_valid is not None:
        depth_hit = hit & depth_valid
        has_deep_water = (
            deep_water_cov is not None
            and ((deep_water_cov > 0) & hit).any()
        )
        if depth_hit.any() or has_deep_water:
            stops = _water_depth_stops(water_hex, palette)
            stop_depths = np.array(
                [d for d, _, _ in stops], dtype=np.float32,
            )
            depth = np.maximum(depth_m.astype(np.float32), stop_depths[0])

            water_cov_f = water_cov.astype(np.float32)
            deep_alpha = np.zeros((height, width), dtype=np.float32)
            if deep_water_cov is not None:
                deep_alpha = deep_water_cov.astype(np.float32) / 255.0
            non_deep_weight = 1.0 - np.clip(deep_alpha, 0.0, 1.0)

            colored = np.zeros((height, width, 3), dtype=np.float32)
            weight = np.zeros((height, width), dtype=np.float32)

            def add_coverage(cov: np.ndarray, hex_color: str) -> None:
                cov *= non_deep_weight
                cov = _blur_water_coverage(cov)
                cov *= hit.astype(np.float32)
                if not cov.any():
                    return
                color = np.array(_hex_to_bgr(hex_color), dtype=np.float32)
                colored[:] += cov[..., None] * color
                weight[:] += cov

            for i in range(len(stops) - 1):
                d0, d1 = stop_depths[i], stop_depths[i + 1]
                _, _, c0_hex = stops[i]
                _, _, c1_hex = stops[i + 1]
                band = depth_hit & (depth > d0) & (depth <= d1)
                if i == 0:
                    band = depth_hit & (depth >= d0) & (depth <= d1)
                if not band.any():
                    continue
                if WATER_DEPTH_INTERPOLATE_COLORS:
                    denom = max(float(d1 - d0), 1e-6)
                    t = np.zeros((height, width), dtype=np.float32)
                    t[band] = (depth[band] - d0) / denom

                    cov0 = np.zeros((height, width), dtype=np.float32)
                    cov1 = np.zeros((height, width), dtype=np.float32)
                    cov0[band] = water_cov_f[band] * (1.0 - t[band])
                    cov1[band] = water_cov_f[band] * t[band]
                    add_coverage(cov0, c0_hex)
                    add_coverage(cov1, c1_hex)
                else:
                    cov = np.zeros((height, width), dtype=np.float32)
                    cov[band] = water_cov_f[band]
                    add_coverage(cov, c1_hex)

            extreme_mask = depth_hit & (depth > stop_depths[-1])
            extreme_cov = np.zeros((height, width), dtype=np.float32)
            extreme_cov[extreme_mask] = water_cov_f[extreme_mask]
            extreme_cov *= non_deep_weight
            if deep_water_cov is not None:
                np.maximum(extreme_cov, deep_water_cov.astype(np.float32),
                           out=extreme_cov)
            extreme_cov = _blur_water_coverage(extreme_cov)
            extreme_cov *= hit.astype(np.float32)
            if extreme_cov.any():
                extreme_color = np.array(
                    _hex_to_bgr(
                        palette.get("EXTREMELY_DEEP", water_hex),
                    ),
                    dtype=np.float32,
                )
                colored += extreme_cov[..., None] * extreme_color
                weight += extreme_cov

            weighted = hit & (weight > 0)
            if weighted.any():
                out = colored[weighted] / weight[weighted, None]
                rgba[weighted, 0:3] = np.clip(out, 0, 255).astype(np.uint8)
            if DEPTH_COLOR_SCALING_ENABLED:
                depth_scale = np.zeros((height, width), dtype=np.float32)
                depth_scale[depth_hit] = np.clip(
                    depth_m[depth_hit].astype(np.float32)
                    / max(float(DEEP_WATER_DEPTH), 1e-6),
                    0.0,
                    1.0,
                )
                if deep_water_cov is not None:
                    depth_scale[(deep_water_cov > 0) & hit] = 1.0
                opacity = np.clip(
                    depth_scale * float(DEPTH_COLOR_BLEND_MAX_OPACITY),
                    0.0,
                    1.0,
                )
                blend_hit = hit & (opacity > 0)
                if blend_hit.any():
                    target = np.array(
                        _hex_to_bgr(DEPTH_COLOR_BLEND_TARGET_COLOR),
                        dtype=np.float32,
                    )
                    src = rgba[..., 0:3].astype(np.float32)
                    a = opacity[blend_hit, None]
                    src[blend_hit] = (
                        src[blend_hit] * (1.0 - a) + target * a
                    )
                    rgba[..., 0:3] = np.clip(src, 0, 255).astype(np.uint8)
    rgba[..., 3] = np.minimum(water_cov, world_alpha)
    return rgba


def build_shades(
    centres: Dict[str, Tuple[int, int]],
    mask: np.ndarray,
    height: int,
    width: int,
    shade_alpha: np.ndarray | None,
) -> Tuple[np.ndarray, np.ndarray] | None:
    """Stitch every LAYERS_DIR/<layer>/ folder and composite via
    alpha-betting into an RGB canvas. Returns (shades_bgr, shades_alpha)
    or None when LAYERS_DIR is missing / empty."""
    if not LAYERS_DIR.is_dir():
        print(f"\n[WARN] {LAYERS_DIR} not found; no per-layer stitching done")
        return None
    layer_dirs = sorted(d for d in LAYERS_DIR.iterdir() if d.is_dir())
    if not layer_dirs:
        return None

    claim_mask = (shade_alpha > 0) if shade_alpha is not None else None
    shades = np.zeros((height, width, 3), dtype=np.uint8)
    winner_alpha = np.zeros((height, width), dtype=np.uint8)

    used_colors: set = {_hex_to_bgr(c) for c in LAYER_COLORS.values()}
    rng = random.Random(0xF0)

    for layer_dir in layer_dirs:
        layer = layer_dir.name
        if LAYER_ENABLED.get(layer, LAYER_ENABLED.get(layer.lower(), True)) is False:
            print(f"\n=== stitching layer: {layer} ===")
            print("  [skip] disabled in LAYER_ENABLED")
            continue
        print(f"\n=== stitching layer: {layer} ===")
        tile_map = _build_tile_map(layer_dir)
        canvas = stitch(
            tile_map, centres, mask, height, width,
            channels=1, dtype=np.uint8, read_flag=cv2.IMREAD_GRAYSCALE,
        )
        if claim_mask is not None:
            canvas = canvas * claim_mask.astype(np.uint8)
        color = _assign_layer_color(layer, LAYER_COLORS, used_colors, rng)
        print(f"  color: BGR{color}")
        win = canvas > winner_alpha
        if win.any():
            shades[win] = color
            winner_alpha[win] = canvas[win]

    claimed = winner_alpha > 0
    if claimed.any():
        need_fill = ~claimed
        n_need = int(need_fill.sum())
        if n_need > 0:
            src_zero = (~claimed).astype(np.uint8)
            _, labels = cv2.distanceTransformWithLabels(
                src_zero, cv2.DIST_L2, 3,
                labelType=cv2.DIST_LABEL_PIXEL,
            )
            ys, xs = np.where(claimed)
            src_y = np.empty(ys.size + 1, dtype=np.int32)
            src_x = np.empty(xs.size + 1, dtype=np.int32)
            src_y[0] = 0; src_x[0] = 0
            src_y[1:] = ys; src_x[1:] = xs
            lab = np.clip(labels[need_fill].astype(np.int64), 1, ys.size)
            shades[need_fill] = shades[src_y[lab], src_x[lab]]
            print(f"  filled {n_need} unassigned pixel(s) "
                  f"with nearest shade colour (blur bleed guard)")

    if SHADES_BLUR_KSIZE and SHADES_BLUR_KSIZE > 1:
        k = int(SHADES_BLUR_KSIZE)
        if k % 2 == 0:
            k += 1
        shades = cv2.GaussianBlur(shades, (k, k), float(SHADES_BLUR_SIGMA))

    if shade_alpha is not None:
        out_alpha = shade_alpha
    else:
        out_alpha = np.where(winner_alpha > 0, 255, 0).astype(np.uint8)
    return shades, out_alpha


# ------------------------------------------------------------------------------
#  Assembly composites (the new outputs)
# ------------------------------------------------------------------------------

def _alpha_over(
    base_rgb_f: np.ndarray,
    top_rgb_u8: np.ndarray,
    top_alpha_u8: np.ndarray,
) -> np.ndarray:
    """Return base_rgb_f with top composited over it via "normal" blending.
    base_rgb_f is float32 (0..255); top inputs are uint8. Works in place
    would be nice but we return a new array."""
    a = (top_alpha_u8.astype(np.float32) / 255.0)[..., None]
    return base_rgb_f * (1.0 - a) + top_rgb_u8.astype(np.float32) * a


def build_base_layer(
    terrain_recolor: np.ndarray | None,
    shades: Tuple[np.ndarray, np.ndarray] | None,
    highs: np.ndarray | None,
    lows: np.ndarray | None,
    water_recolor: np.ndarray | None,
    ao: np.ndarray | None,
    contour_rgba: np.ndarray | None,
    ground: np.ndarray,
    world_alpha: np.ndarray,
    out_path: Path,
) -> None:
    """Compose base_layer.png:

        terrain_recolor (base)
      + shades                  (normal alpha over)
      + highs  * ground         (add)
      + lows   * ground         (difference)
      + water_recolor           (multiply with alpha)
      + ao                      (multiply)
      + contour_rgba            (normal alpha over, debug)
    """
    if terrain_recolor is None:
        print("  [WARN] terrain_recolor unavailable; skipping base_layer")
        return

    height, width = world_alpha.shape
    base = terrain_recolor.astype(np.float32)

    if shades is not None:
        shades_rgb, shades_alpha = shades
        base = _alpha_over(base, shades_rgb, shades_alpha)

    ground_f = ground[..., None]  # (H, W, 1), 0..1

    if highs is not None:
        add = highs.astype(np.float32)[..., None] * ground_f
        base = np.clip(base + add, 0, 255)

    if lows is not None:
        diff_layer = lows.astype(np.float32)[..., None] * ground_f
        base = np.abs(base - diff_layer)

    if water_recolor is not None:
        wa = (water_recolor[..., 3].astype(np.float32) / 255.0)[..., None]
        wrgb = water_recolor[..., 0:3].astype(np.float32) / 255.0
        # multiply-with-alpha: out = out * (wrgb * wa + (1 - wa))
        base = base * (wrgb * wa + (1.0 - wa))

    if ao is not None:
        ao_f = (ao.astype(np.float32) / 255.0)[..., None]
        base = base * ao_f

    if contour_rgba is not None:
        contour_alpha = np.minimum(contour_rgba[..., 3], world_alpha)
        base = _alpha_over(base, contour_rgba[..., 0:3], contour_alpha)

    base = np.clip(base, 0, 255).astype(np.uint8)
    rgba = np.dstack([base, world_alpha])
    _write_rgba(rgba, out_path)
    LOG.saved(out_path)


def _load_svg_layer(name: str) -> np.ndarray | None:
    """Load export/_final/svg_layers/<name>.png (BGRA). Returns None when
    the stitched file hasn't been produced yet."""
    path = FINAL_DIR / "svg_layers" / f"{name}.png"
    if not path.is_file():
        return None
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img


def _composite_over(dst_rgba: np.ndarray, top_rgba: np.ndarray) -> np.ndarray:
    """Standard Porter-Duff source-over in float32; returns uint8 RGBA."""
    da = dst_rgba[..., 3].astype(np.float32) / 255.0
    ta = top_rgba[..., 3].astype(np.float32) / 255.0
    drgb = dst_rgba[..., 0:3].astype(np.float32)
    trgb = top_rgba[..., 0:3].astype(np.float32)
    out_a = ta + da * (1.0 - ta)
    safe = np.maximum(out_a, 1e-6)[..., None]
    out_rgb = (trgb * ta[..., None] + drgb * da[..., None] * (1.0 - ta[..., None])) / safe
    out = np.zeros_like(dst_rgba)
    out[..., 0:3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(np.round(out_a * 255.0), 0, 255).astype(np.uint8)
    return out


def _mul_alpha(rgba: np.ndarray, coef01: np.ndarray) -> np.ndarray:
    """Return a copy of ``rgba`` with its alpha multiplied by ``coef01``
    (float32 in 0..1)."""
    out = rgba.copy()
    out[..., 3] = np.clip(
        np.round(out[..., 3].astype(np.float32) * coef01), 0, 255,
    ).astype(np.uint8)
    return out


def build_rdz(
    height: int,
    width: int,
    out_path: Path,
    *,
    grayscale: bool = False,
) -> None:
    """rdz_pattern with svg_layers/rdz_grace punching holes in its alpha."""
    pattern = cv2.imread(str(RDZ_PATTERN_FILE), cv2.IMREAD_UNCHANGED)
    if pattern is None:
        print(f"  [WARN] {RDZ_PATTERN_FILE} not found; skipping rdz")
        return
    if TURBO_MODE_DOWNSAMPLE:
        pattern = _downsample_image(pattern)
    if pattern.ndim == 2:
        pattern = cv2.cvtColor(pattern, cv2.COLOR_GRAY2BGRA)
    elif pattern.shape[2] == 3:
        pattern = cv2.cvtColor(pattern, cv2.COLOR_BGR2BGRA)
    ph, pw = pattern.shape[:2]
    if (ph, pw) != (height, width):
        reps_y = (height + ph - 1) // ph
        reps_x = (width + pw - 1) // pw
        pattern = np.tile(pattern, (reps_y, reps_x, 1))[:height, :width]

    if grayscale:
        gray = cv2.cvtColor(pattern[..., 0:3], cv2.COLOR_BGR2GRAY)
        pattern[..., 0:3] = gray[..., None]

    grace = _load_svg_layer("rdz_grace")
    if grace is not None:
        keep = 1.0 - (grace[..., 3].astype(np.float32) / 255.0)
        pattern = _mul_alpha(pattern, keep)

    _write_rgba(pattern, out_path)
    LOG.saved(out_path)


def build_ranges(
    height: int,
    width: int,
    ground01: np.ndarray,
    water01: np.ndarray,
    out_path: Path,
) -> None:
    """svg_layers: tap*ground + intel + ai*ground + mh + cg*water + aag, alpha-over."""
    layers_gates = [
        ("ranges_tap",   ground01),
        ("ranges_intel", None),
        ("ranges_ai",    ground01),
        ("ranges_mh",    None),
        ("ranges_cg",    water01),
        ("ranges_aag",   None),
    ]
    result = np.zeros((height, width, 4), dtype=np.uint8)
    any_hit = False
    for name, gate in layers_gates:
        img = _load_svg_layer(name)
        if img is None:
            LOG.info(f"[skip] ranges: svg_layers/{name}.png missing")
            continue
        if gate is not None:
            img = _mul_alpha(img, gate)
        result = _composite_over(result, img)
        any_hit = True
    if not any_hit:
        print("  [WARN] no range svg_layers available; skipping ranges")
        return
    _write_rgba(result, out_path)
    LOG.saved(out_path)


def build_legacy_bridges_aim(
    water_cov: np.ndarray | None,
    out_path: Path,
) -> None:
    """Legacy svg_layers/bridges_aim gated by eroded water coverage."""
    src = _load_svg_layer("bridges_aim")
    if src is None:
        print("  [WARN] svg_layers/bridges_aim.png missing; "
              "skipping legacy bridges_aim")
        return
    if water_cov is None:
        print("  [WARN] water coverage unavailable; "
              "skipping legacy bridges_aim")
        return
    k = 2 * LEGACY_BRIDGE_AIM_WATER_ERODE_PX + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    eroded = cv2.erode(water_cov, kernel)
    gate = eroded.astype(np.float32) / 255.0
    out = _mul_alpha(src, gate)
    _write_rgba(out, out_path)
    LOG.saved(out_path)


def build_contours_assembly(
    contour_rgba: np.ndarray,
    ground01: np.ndarray,
    water01: np.ndarray,
    out_path: Path,
) -> None:
    """3x3 gaussian of the contour overlay with alpha multiplied by
    (0.5 * water + ground). Produces the blurred copy consumed by the
    map compositor."""
    rgba = make_contours_assembly(contour_rgba, ground01, water01)
    _write_rgba(rgba, out_path)
    LOG.saved(out_path)


def make_contours_assembly(
    contour_rgba: np.ndarray,
    ground01: np.ndarray,
    water01: np.ndarray,
) -> np.ndarray:
    """Return the same blurred/gated contour RGBA written to assembly."""
    k = CONTOURS_BLUR_KSIZE
    if k % 2 == 0:
        k += 1
    blurred_alpha = cv2.GaussianBlur(contour_rgba[..., 3], (k, k), 0)
    coef = np.clip(0.5 * water01 + ground01, 0.0, 1.0)
    out_alpha = np.clip(
        np.round(blurred_alpha.astype(np.float32) * coef), 0, 255,
    ).astype(np.uint8)
    rgba = np.zeros_like(contour_rgba)
    rgba[..., 3] = out_alpha
    return rgba


# ------------------------------------------------------------------------------
#  Main
# ------------------------------------------------------------------------------

def main() -> int:
    t0 = time.time()

    try:
        centres = load_centres()
        mask = load_mask()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    centres = _scale_centres(centres)
    height, width = canvas_size(centres, mask)
    print(f"=== Finalizing exports ({width}x{height} px, {len(centres)} regions) ===")
    if TURBO_MODE_DOWNSAMPLE:
        print("=== TURBO_MODE_DOWNSAMPLE: 50% image loads and output size ===")

    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    # Best-effort pre-count for "[i/N]" prefixes.
    est = 0
    if AO_DIR.is_dir():            est += 1  # technical/ao
    if ROADS_DIR.is_dir():         est += 1  # assembly/roads
    if BEACHES_DIR.is_dir():       est += 1  # assembly/beaches
    if SPLIT_LAYERS_DIR.is_dir():
        for _layer in SPLIT_LAYERS:
            if (SPLIT_LAYERS_DIR / _layer).is_dir(): est += 1
    if SVG_LAYERS_DIR.is_dir():
        for _layer in SVG_LAYERS:
            if (SVG_LAYERS_DIR / _layer).is_dir(): est += 1
    if ID_DIR.is_dir():
        est += sum(1 for d in ID_DIR.iterdir() if d.is_dir())
    if HM_LANDSCAPE_DIR.is_dir():
        est += 2  # fly_alert, technical/contour
        if WRITE_ADDITIONAL_ASSEMBLY_LAYERS:
            est += 1  # assembly/contours
    if HM_WATER_DIR.is_dir():      est += 1  # heightmap_simple
    est += 1  # base_layer
    if BASE_LAYER_SIMPLE_ENABLED:
        est += 1  # base_layer_simple
    if WRITE_ADDITIONAL_ASSEMBLY_LAYERS:
        est += 2  # rdz, ranges (may skip)
        if ENABLE_LEGACY_BRIDGE_AIM:
            est += 1  # assembly/bridges_aim
        if WRITE_RDZ_DARK_ASSEMBLY_LAYER:
            est += 1
    LOG.set_total(est)

    world_alpha = _compute_world_alpha(centres, mask, height, width)

    def _stitch_then_alpha(
        label: str,
        src_dir: Path,
        *,
        channels: int,
        read_flag: int,
        out_rel: str,
    ) -> np.ndarray | None:
        if not src_dir.is_dir():
            LOG.info(f"[skip] {label}: source dir not found ({src_dir.name})")
            return None
        print(f"\n=== stitching {label} ===")
        tile_map = _build_tile_map(src_dir)
        canvas = stitch(tile_map, centres, mask, height, width,
                        channels=channels, dtype=np.uint8,
                        read_flag=read_flag)
        out_path = FINAL_DIR / out_rel
        _write_with_alpha(canvas, world_alpha, out_path)
        LOG.saved(out_path)
        return canvas

    # -- technical/ao (also reused for base_layer multiply) --
    ao_canvas = _stitch_then_alpha(
        "ao", AO_DIR, channels=1, read_flag=cv2.IMREAD_GRAYSCALE,
        out_rel=f"{TECHNICAL_DIR}/ao.png",
    )

    # -- assembly/roads & assembly/beaches --
    _stitch_then_alpha(
        "roads", ROADS_DIR,
        channels=4, read_flag=cv2.IMREAD_UNCHANGED,
        out_rel=f"{ASSEMBLY_DIR}/roads.png",
    )
    _stitch_then_alpha(
        "beaches", BEACHES_DIR,
        channels=4, read_flag=cv2.IMREAD_UNCHANGED,
        out_rel=f"{ASSEMBLY_DIR}/beaches.png",
    )

    # -- split_layers/<layer>.png (unchanged location) --
    if SPLIT_LAYERS_DIR.is_dir():
        for layer in SPLIT_LAYERS:
            src = SPLIT_LAYERS_DIR / layer
            _stitch_then_alpha(
                f"split_layers/{layer}", src,
                channels=4, read_flag=cv2.IMREAD_UNCHANGED,
                out_rel=f"split_layers/{layer}.png",
            )
    else:
        print(f"\n[WARN] {SPLIT_LAYERS_DIR} not found; "
              f"skipping split_layer stitching")

    # -- svg_layers/<layer>.png (unchanged location; consumed below) --
    if SVG_LAYERS_DIR.is_dir():
        for layer in SVG_LAYERS:
            src = SVG_LAYERS_DIR / layer
            _stitch_then_alpha(
                f"svg_layers/{layer}", src,
                channels=4, read_flag=cv2.IMREAD_UNCHANGED,
                out_rel=f"svg_layers/{layer}.png",
            )
    else:
        print(f"\n[WARN] {SVG_LAYERS_DIR} not found; "
              f"skipping svg_layer stitching")

    # -- id/<cat>.png (unchanged location) --
    id_coverage: Dict[str, np.ndarray] = {}
    if not ID_DIR.is_dir():
        print(f"\n[WARN] {ID_DIR} not found; per-category ID coverage skipped")
    else:
        cat_dirs = sorted(d for d in ID_DIR.iterdir() if d.is_dir())
        for cat_dir in cat_dirs:
            cat = cat_dir.name
            print(f"\n=== stitching id/{cat} ===")
            tile_map = _build_tile_map(cat_dir)
            if not tile_map:
                print(f"  [skip] no tiles in {cat_dir}")
                continue
            canvas = stitch(
                tile_map, centres, mask, height, width,
                channels=1, dtype=np.uint8,
                read_flag=cv2.IMREAD_GRAYSCALE,
            )
            id_coverage[cat] = canvas
            out_path = FINAL_DIR / "id" / f"{cat}.png"
            _write_with_alpha(canvas, world_alpha, out_path)
            LOG.saved(out_path)

    terrain_cov = id_coverage.get("terrain")
    deep_water_cov = id_coverage.get("deep_water")
    depth_color_deep_water_cov = deep_water_cov
    water_cov = _max_coverage(
        id_coverage.get("water"),
        deep_water_cov,
    )
    rocks_cov = id_coverage.get("rocks")

    # -- ground mask = terrain * (not water), 0..1 float --
    if terrain_cov is not None:
        if water_cov is not None:
            non_water = (255 - water_cov).astype(np.uint16)
            ground_u8 = (
                (terrain_cov.astype(np.uint16) * non_water + 127) // 255
            ).astype(np.uint8)
        else:
            ground_u8 = terrain_cov.copy()
        ground_u8 = np.minimum(ground_u8, world_alpha)
    else:
        ground_u8 = np.zeros((height, width), dtype=np.uint8)
    ground01 = ground_u8.astype(np.float32) / 255.0
    water01 = (water_cov.astype(np.float32) / 255.0
               if water_cov is not None
               else np.zeros((height, width), dtype=np.float32))

    # -- heightmap products --
    raw_landscape = stitch_heightmap_landscape(centres, mask, height, width)
    highs = lows = None
    contour_rgba = None
    if raw_landscape is not None:
        print(f"\n=== deriving heightmap_landscape products ===")
        if DISABLE_NON_WATER_ROCK_LAYERS:
            print("  [skip] highs/lows disabled by "
                  "DISABLE_NON_WATER_ROCK_LAYERS")
        else:
            highs, lows = compute_highs_lows(raw_landscape)
        build_fly_alert(
            raw_landscape, height, width, rocks_cov,
            FINAL_DIR / ASSEMBLY_DIR / "fly_alert.png",
        )

    raw_water = stitch_heightmap_water(centres, mask, height, width)
    if raw_water is not None:
        print(f"\n=== deriving heightmap_water products ===")
        build_heightmap_simple(
            raw_water, world_alpha,
            FINAL_DIR / TECHNICAL_DIR / "heightmap_simple.png",
        )

    if raw_landscape is not None:
        contour_mask = build_contour_mask(
            terrain_cov, rocks_cov, water_cov, raw_landscape, raw_water,
        )
        contour_rgba = build_contour(
            raw_landscape, contour_mask, water_cov, height, width,
        )
        contour_out = FINAL_DIR / TECHNICAL_DIR / "contour.png"
        _write_rgba(contour_rgba, contour_out)
        LOG.saved(contour_out)

    water_depth_m = None
    water_depth_valid = None
    if (
        raw_landscape is not None
        and raw_water is not None
        and water_cov is not None
    ):
        water_depth_m, water_depth_valid = _compute_water_depth_m(
            raw_landscape, raw_water, water_cov,
        )
        # dive_alert is intentionally disabled. Leave the function above
        # available for quick re-enable while water-depth masks replace it.
        # build_dive_alert(
        #     raw_landscape, raw_water, water_cov, world_alpha, rocks_cov,
        #     FINAL_DIR / ASSEMBLY_DIR / "dive_alert.png",
        # )
    else:
        print("  [WARN] missing heightmap/water coverage; "
              "base_layer water depth colors unavailable")

    # -- in-memory intermediates for base_layer --
    print(f"\n=== assembling base_layer inputs ===")
    base_id_coverage = id_coverage
    if BASE_LAYER_TERRAIN_RECOLOR_WATER_AS_WATER and deep_water_cov is not None:
        base_id_coverage = dict(base_id_coverage)
        water_like_cov = (
            _max_coverage(id_coverage.get("water"), deep_water_cov)
            if WATER_TREAT_DEEP_WATER_AS_WATER
            else deep_water_cov
        )

        terrain_visible = base_id_coverage.get("terrain")
        if terrain_visible is None:
            terrain_visible = np.zeros_like(water_like_cov)
        else:
            terrain_visible = terrain_visible.copy()
        np.maximum(terrain_visible, water_like_cov, out=terrain_visible)
        base_id_coverage["terrain"] = terrain_visible

        if WATER_TREAT_DEEP_WATER_AS_WATER:
            base_id_coverage["water"] = water_like_cov
            base_id_coverage["deep_water"] = np.zeros_like(deep_water_cov)

    submerged_rocks = None
    if BASE_LAYER_HIDE_UNDERWATER_ROCKS and "rocks" in id_coverage:
        submerged_rocks = underwater_rocks_mask(
            rocks_cov, water_cov, raw_landscape, raw_water,
        )
        if submerged_rocks is not None and submerged_rocks.any():
            base_id_coverage = dict(base_id_coverage)
            rocks_visible = base_id_coverage["rocks"].copy()
            removed_rocks = np.zeros_like(rocks_visible)
            removed_rocks[submerged_rocks] = rocks_visible[submerged_rocks]
            rocks_visible[submerged_rocks] = 0
            base_id_coverage["rocks"] = rocks_visible
            terrain_visible = base_id_coverage.get("terrain")
            if terrain_visible is None:
                terrain_visible = np.zeros_like(rocks_visible)
            else:
                terrain_visible = terrain_visible.copy()
            np.maximum(terrain_visible, removed_rocks, out=terrain_visible)
            base_id_coverage["terrain"] = terrain_visible
            print(f"  converted {int(submerged_rocks.sum()):,} underwater "
                  "rock pixel(s) to terrain coverage for base_layer")

    if BASE_LAYER_TERRAIN_RECOLOR_WATER_AS_WATER:
        water_cov = base_id_coverage.get("water", water_cov)

    terrain_recolor = (
        build_terrain_recolor(
            base_id_coverage, world_alpha, height, width,
            fill_block_mask=(
                water_cov > 0
                if BASE_LAYER_DISABLE_TERRAIN_FILL_IN_WATER
                and water_cov is not None
                else None
            ),
        )
        if base_id_coverage else None
    )
    water_recolor = (
        build_water_recolor(
            water_cov, depth_color_deep_water_cov,
            world_alpha, height, width,
            water_depth_m, water_depth_valid, raw_landscape,
        )
        if RECOLOR_WATER_FLAG else None
    )
    if not RECOLOR_WATER_FLAG:
        print("  [skip] water_recolor disabled by RECOLOR_WATER_FLAG")
    water_recolor_simple = None
    if BASE_LAYER_SIMPLE_ENABLED and RECOLOR_WATER_FLAG:
        water_recolor_simple = build_water_recolor(
            water_cov, depth_color_deep_water_cov,
            world_alpha, height, width,
            water_depth_m, water_depth_valid, raw_landscape,
            WATER_DEPTH_COLORS_SIMPLE,
        )

    # shade_alpha = terrain * (not water) ∧ world_alpha (same as ground_u8)
    if DISABLE_NON_WATER_ROCK_LAYERS:
        shades_pair = None
        print("  [skip] shades disabled by DISABLE_NON_WATER_ROCK_LAYERS")
    else:
        shade_alpha = ground_u8 if terrain_cov is not None else None
        shades_pair = build_shades(centres, mask, height, width, shade_alpha)

    # -- assembly/base_layer.png --
    base_layer_contours = None
    if BASE_LAYER_DEBUG_CONTOURS and contour_rgba is not None:
        base_layer_contours = make_contours_assembly(
            contour_rgba, ground01, water01,
        )
        base_layer_contours[..., 3] = np.clip(
            np.round(
                base_layer_contours[..., 3].astype(np.float32)
                * float(BASE_LAYER_CONTOUR_ALPHA_MULT)
            ),
            0,
            255,
        ).astype(np.uint8)
    base_layer_path = FINAL_DIR / ASSEMBLY_DIR / "base_layer.png"
    base_layer_ao = (
        attenuate_underwater_ao(ao_canvas, water_cov)
        if BASE_LAYER_APPLY_AO else None
    )
    build_base_layer(
        terrain_recolor, shades_pair, highs, lows, water_recolor,
        base_layer_ao,
        base_layer_contours,
        ground01, world_alpha,
        base_layer_path,
    )
    if BASE_LAYER_SIMPLE_ENABLED:
        build_base_layer(
            terrain_recolor, shades_pair, highs, lows, water_recolor_simple,
            base_layer_ao,
            base_layer_contours,
            ground01, world_alpha,
            FINAL_DIR / ASSEMBLY_DIR / "base_layer_simple.png",
        )
    del raw_landscape, raw_water

    if WRITE_ADDITIONAL_ASSEMBLY_LAYERS:
        # -- assembly/contours.png (blurred contour with alpha gating) --
        if contour_rgba is not None:
            build_contours_assembly(
                contour_rgba, ground01, water01,
                FINAL_DIR / ASSEMBLY_DIR / "contours.png",
            )

        # -- assembly/rdz.png --
        build_rdz(height, width, FINAL_DIR / ASSEMBLY_DIR / "rdz.png")
        if WRITE_RDZ_DARK_ASSEMBLY_LAYER:
            build_rdz(
                height, width,
                FINAL_DIR / ASSEMBLY_DIR / "rdz_dark.png",
                grayscale=True,
            )

        # -- assembly/ranges.png --
        build_ranges(
            height, width, ground01, water01,
            FINAL_DIR / ASSEMBLY_DIR / "ranges.png",
        )
        if ENABLE_LEGACY_BRIDGE_AIM:
            build_legacy_bridges_aim(
                water_cov, FINAL_DIR / ASSEMBLY_DIR / "bridges_aim.png",
            )

    else:
        LOG.info("[skip] additional assembly layers disabled")

    print(f"\n=== SUCCESS (in {time.time() - t0:.2f}s) ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
