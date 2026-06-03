"""Probe water depth from step-4 heightmap bakes.

Depth is measured as:

    heightmap_water - heightmap_landscape

Both heightmaps use the exporter encoding ``height_m = (raw - 32768) / 100``.
The input x/y coordinates are final-canvas coordinates, matching
``export/_final/assembly/base_layer.png``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from utils.config import CENTRES_FILE, HM_LANDSCAPE_DIR, HM_WATER_DIR, TILE_HALF
from utils.png import read_png16_gray


def _load_centres() -> dict[str, tuple[int, int]]:
    with open(CENTRES_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {name.lower(): (int(xy[0]), int(xy[1])) for name, xy in raw.items()}


def _window(center: int, size: int) -> slice:
    half = size // 2
    return slice(center - half, center + half + 1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure river/lake depth from final-canvas coordinates.",
    )
    parser.add_argument("x", type=int, help="Final/base_layer x coordinate")
    parser.add_argument("y", type=int, help="Final/base_layer y coordinate")
    parser.add_argument(
        "--region",
        default="AshFieldsHex",
        help="Region tile to sample, default: AshFieldsHex",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=5,
        help="Odd square sample size in pixels, default: 5",
    )
    parser.add_argument(
        "--dump-grid",
        action="store_true",
        help="Print the sampled depth grid in meters",
    )
    args = parser.parse_args()

    if args.size <= 0 or args.size % 2 == 0:
        parser.error("--size must be a positive odd integer")

    centres = _load_centres()
    region_key = args.region.lower()
    if region_key not in centres:
        parser.error(f"unknown region: {args.region}")

    cx, cy = centres[region_key]
    local_x = args.x - (cx - TILE_HALF)
    local_y = args.y - (cy - TILE_HALF)

    land_path = HM_LANDSCAPE_DIR / f"{args.region}.png"
    water_path = HM_WATER_DIR / f"{args.region}.png"
    if not land_path.is_file():
        raise FileNotFoundError(land_path)
    if not water_path.is_file():
        raise FileNotFoundError(water_path)

    land_w, land_h, raw_land = read_png16_gray(str(land_path))
    water_w, water_h, raw_water = read_png16_gray(str(water_path))
    if (land_w, land_h) != (water_w, water_h):
        raise ValueError(
            f"heightmap size mismatch: landscape={land_w}x{land_h}, "
            f"water={water_w}x{water_h}"
        )

    y_slice = _window(local_y, args.size)
    x_slice = _window(local_x, args.size)
    if (
        x_slice.start < 0
        or y_slice.start < 0
        or x_slice.stop > land_w
        or y_slice.stop > land_h
    ):
        raise ValueError(
            f"{args.size}px window around local ({local_x}, {local_y}) "
            f"falls outside {args.region} ({land_w}x{land_h})"
        )

    land = (raw_land[y_slice, x_slice].astype(np.float32) - 32768.0) / 100.0
    water = (raw_water[y_slice, x_slice].astype(np.float32) - 32768.0) / 100.0
    depth = water - land
    valid = (
        (raw_land[y_slice, x_slice] != 0)
        & (raw_water[y_slice, x_slice] != 0)
        & (depth > 0.0)
    )

    print(f"region: {args.region}")
    print(f"world xy: ({args.x}, {args.y})")
    print(f"tile xy:  ({local_x}, {local_y})")
    print(f"window:   {args.size}x{args.size}")
    print(f"valid:    {int(valid.sum())}/{args.size * args.size} px")
    if valid.any():
        print(f"average depth: {float(depth[valid].mean()):.4f} m")
        print(f"min/max depth: {float(depth[valid].min()):.4f} / {float(depth[valid].max()):.4f} m")
    else:
        print("average depth: no valid submerged pixels")

    if args.dump_grid:
        print("depth grid (m):")
        print(np.array2string(depth, precision=2, suppress_small=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
