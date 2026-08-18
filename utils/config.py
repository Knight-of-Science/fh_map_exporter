"""
config.py
========
Shared constants for the Foxhole map exporter pipeline.

All paths are resolved relative to the repository root (the directory that
contains this ``utils`` package), so every ``N_*.py`` script works no matter
what the current working directory is when it runs.
"""

from pathlib import Path
from typing import Dict, List, Tuple


# ------------------------------------------------------------------------------
#  Directories and files
# ------------------------------------------------------------------------------

REPO_ROOT           = Path(__file__).resolve().parent.parent


def short_path(p) -> str:
    """Return ``p`` relative to REPO_ROOT when possible, else just its name.

    Used for log output so messages don't dump 100+ char absolute paths.
    """
    try:
        return Path(p).resolve().relative_to(REPO_ROOT).as_posix()
    except Exception:
        try:
            return Path(p).name
        except Exception:
            return str(p)

UTILS_DIR           = REPO_ROOT / "utils"
CENTRES_FILE        = UTILS_DIR / "region_centers.json"
CATALOGUE_FILE      = UTILS_DIR / "catalogue.json"
MASK_FILE           = UTILS_DIR / "mask.png"
FLY_ALERT_PATTERN_FILE = UTILS_DIR / "fly_alert_pattern.png"
RDZ_PATTERN_FILE    = UTILS_DIR / "rdz_pattern.png"

EXPORT_DIR          = REPO_ROOT / "export"
JSON_DIR            = EXPORT_DIR / "_json"
MESHES_DIR          = EXPORT_DIR / "_meshes"
HEIGHTMAP_DIR       = EXPORT_DIR / "_heightmap"
LAYERS_DIR          = EXPORT_DIR / "_layers"
BLEND_DIR           = EXPORT_DIR / "blend"
SPILL_DIR           = EXPORT_DIR / "blend_spill"

AO_DIR              = EXPORT_DIR / "ao"
HM_LANDSCAPE_DIR    = EXPORT_DIR / "heightmap_landscape"
HM_WATER_DIR        = EXPORT_DIR / "heightmap_water"
ID_DIR              = EXPORT_DIR / "id"
ROADS_DIR           = EXPORT_DIR / "roads"
BEACHES_DIR         = EXPORT_DIR / "beaches"
SPLIT_LAYERS_DIR    = EXPORT_DIR / "split_layers"
SVG_DIR             = UTILS_DIR / "svg"
SVG_LAYERS_DIR      = EXPORT_DIR / "svg_layers"

FINAL_DIR           = EXPORT_DIR / "_final"

# ------------------------------------------------------------------------------
#  Exporter.exe build + invocation
# ------------------------------------------------------------------------------

EXPORTER_EXE        = REPO_ROOT / "Exporter.exe"

EXPORTER_PROJECT_DIR = REPO_ROOT / "Exporter"
EXPORTER_PROJECT     = EXPORTER_PROJECT_DIR / "Exporter.csproj"
EXPORTER_TFM         = "net9.0"
EXPORTER_RID         = "win-x64"
EXPORTER_PUBLISH_DIR = (
    EXPORTER_PROJECT_DIR / "bin" / "Release" / EXPORTER_TFM / EXPORTER_RID / "publish"
)

# ------------------------------------------------------------------------------
#  Parallelism
# ------------------------------------------------------------------------------

# Number of worker subprocesses used by
# 2_blend_all.py, 3_blend_spills.py, and 4_render_spills.py.
# Set to 1 to force serial execution in the parent process (no subprocesses).
NUM_WORKERS = 6
NUM_WORKERS_SPILLS = 3


FOXHOLE_PAK = Path(
    r"H:\SteamLibrary\steamapps\common"
    r"\Foxhole\War\Content\Paks\War-WindowsNoEditor.pak"
)

# ------------------------------------------------------------------------------
#  Knight of Science fork configs, primarily for 5_finalize_exports.py
# ------------------------------------------------------------------------------

# ship drafts in meters
SHALLOW_DEPTH = 1.4
VIC_DEPTH = 2.0
#BMS_BLUEFIN_DRAFT = 3.81
#BMS_LONGHOOK_DRAFT = 4.68
C_TRIDENT_DRAFT = 4.8
#BMS_BOWHEAD_DRAFT = 5.23
#C_CONQUEROR_DRAFT = 5.52
#W_CALLAHAN_MERCY_DRAFT = 6.03
W_NAKKI_DRAFT = 6.27
W_BLACKSTEELE_DRAFT = 6.85
C_TITAN_DRAFT = 7.94
#C_POSEIDON_DRAFT = 8.32
LARGE_SHIP_BEACH_DEPTH = C_TITAN_DRAFT
INTEL_DEPTH = 14.19 #6.75 + 7.44
MEDIUM_WATER_DEPTH = 27.44 #20.0 + 7.44

# DEEP_WATER_DEPTH is already used to cull irrelevant geometry that is too deep during 3_blend_spills.py
DEEP_WATER_DEPTH = 32.44 #25.0 + 7.44

# detailed depth colors variant
WATER_DEPTH_COLORS: Dict[str, str] = {
    "SHALLOW_DEPTH":              "#C0E8C6",
    "VIC_DEPTH":                  "#9BC9AE",
    "C_TRIDENT_DRAFT":            "#6681CC",
    "W_NAKKI_DRAFT":              "#7E93CC",
    "W_BLACKSTEELE_DRAFT":        "#96A5CC",
    "C_TITAN_DRAFT":              "#AFB7CC",
    "INTEL_DEPTH":                "#D3D3CB",
    "MEDIUM_WATER_DEPTH":         "#8F95AA",
    "SOMEWHAT_DEEP_WATER_DEPTH":  "#6B7993",
    "EXTREMELY_DEEP":             "#596B87",
}

# simple depth colors variant
WATER_DEPTH_COLORS_SIMPLE: Dict[str, str] = {
    "SHALLOW_DEPTH":              "#C5CEE5",
    "VIC_DEPTH":                  "#A9BAE5",
    "LARGE_SHIP_BEACH_DEPTH":     "#94A0C1",
    "C_TITAN_DRAFT":              "#94A0C1",
    "INTEL_DEPTH":                "#9390B2",
    "MEDIUM_WATER_DEPTH":         "#8F95AA",
    "SOMEWHAT_DEEP_WATER_DEPTH":  "#6B7993",
    "EXTREMELY_DEEP":             "#596B87",
}

# blur depth bands together
WATER_DEPTH_INTERPOLATE_COLORS = False
WATER_DEPTH_COVERAGE_BLUR_KSIZE = 3 #3
WATER_DEPTH_COVERAGE_BLUR_SIGMA = 0.0

# apply a continous shading based on depth
DEPTH_COLOR_SCALING_ENABLED = False
DEPTH_COLOR_BLEND_TARGET_COLOR = "#102844"
DEPTH_COLOR_BLEND_MAX_OPACITY = 0.5

RECOLOR_WATER_FLAG = True

WATER_TREAT_DEEP_WATER_AS_WATER = True

# debug option to visualize magnitude of gradient of terrain
# gradient calculated by from 5 points in a plus sign.
WATER_COLOR_BY_GRADIENT = False
WATER_GRADIENT_SWEEP_PX = 3
WATER_GRADIENT_BLACK_SLOPE = 1.0

# debug downsample layers after import, reducing processing time.
TURBO_MODE_DOWNSAMPLE = False

# contour modifiers
BASE_LAYER_DEBUG_CONTOURS = True
BASE_LAYER_CONTOUR_ALPHA_MULT = 0.3
CONTOUR_STEP_M = 2.5
CONTOUR_OFFSET_M = -0.18
UNDERWATER_CONTOUR_NORMAL_EXCLUSION_DISTANCE = 0.5
CONTOUR_INCLUDE_UNDERWATER_ROCKS = True

BASE_LAYER_HIDE_UNDERWATER_ROCKS = True
BASE_LAYER_DISABLE_TERRAIN_FILL_IN_WATER = True
BASE_LAYER_TERRAIN_RECOLOR_WATER_AS_WATER = True

BASE_LAYER_APPLY_AO = True
BASE_LAYER_UNDERWATER_AO_ALPHA_MULT = True
BASE_LAYER_UNDERWATER_AO_ALPHA_MULTIPLIER = 0.1
BASE_LAYER_UNDERWATER_AO_PARTIAL_COVERAGE = True


# Per-terrain-weight layer switches consumed by 5_finalize_exports.py.
# Disabled layers are skipped during shade/material stitching.
LAYER_ENABLED: Dict[str, bool] = {
    "TownStone": True,
}

DISABLE_NON_WATER_ROCK_LAYERS = False

WRITE_ADDITIONAL_ASSEMBLY_LAYERS = True
WRITE_RDZ_DARK_ASSEMBLY_LAYER = True

# Saves export/_final/assembly/base_layer_simple.png containingn simple depth colors
BASE_LAYER_SIMPLE_ENABLED = True


WATER_DEPTH_LEGEND: List[Tuple[str, str]] = [
    ("SHALLOW_DEPTH",             " <  1.4m | Shallows, walkable"),
    ("VIC_DEPTH",                 " <  2.0m | Drivable depth, swimming required"),
    ("C_TRIDENT_DRAFT",           "    3.8m | BMS BLUEFIN draft (not shown)"),
    ("C_TRIDENT_DRAFT",           "    4.7m | BMS LONGHOOK draft (not shown)"),
    ("C_TRIDENT_DRAFT",           " <  4.8m | COLLIE TRIDENT 0 ballast draft"),
    ("W_NAKKI_DRAFT",             "    5.2m | BMS BOWHEAD draft (not shown)"),
    ("W_NAKKI_DRAFT",             "    5.5m | COLLIE CONQUEROR draft (not shown)"),
    ("W_NAKKI_DRAFT",             "    6.0m | WARD CALLAHAN + MERCY draft (not shown)"),
    ("W_NAKKI_DRAFT",             " <  6.3m | WARD NAKKI 0 ballast draft"),
    ("W_BLACKSTEELE_DRAFT",       " <  6.9m | WARD FRIGATE draft"),
    ("C_TITAN_DRAFT",             " <  7.9m | COLLIE TITAN draft, all large ship beach warning"),
    ("INTEL_DEPTH",               "    8.3m | COLLIE POSEIDON draft (not shown, see details)"),
    ("INTEL_DEPTH",               " < 14.2m | TRIDENT + NAKKI incapable of hiding from intelligence"),
    ("MEDIUM_WATER_DEPTH",        " < 27.4m | WARDEN NAKKI incapable of crush depth"),
    ("SOMEWHAT_DEEP_WATER_DEPTH", " < 32.4m | COLLIE TRIDENT incapable of crush depth"),
    ("EXTREMELY_DEEP",            " > 32.4m | TRIDENT + NAKKI capable of crush depth"),
]

WATER_DEPTH_LEGEND_SIMPLE: List[Tuple[str, str]] = [
    ("SHALLOW_DEPTH",             " <  1.4m | Shallows, walkable"),
    ("VIC_DEPTH",                 " <  2.0m | Drivable depth, swimming required"),
    ("LARGE_SHIP_BEACH_DEPTH",    "    3.8m | BMS BLUEFIN draft (not shown)"),
    ("LARGE_SHIP_BEACH_DEPTH",    "    4.7m | BMS LONGHOOK draft (not shown)"),
    ("LARGE_SHIP_BEACH_DEPTH",    "    4.8m | COLLIE TRIDENT 0 ballast draft (not shown)"),
    ("LARGE_SHIP_BEACH_DEPTH",    "    5.2m | BMS BOWHEAD draft (not shown)"),
    ("LARGE_SHIP_BEACH_DEPTH",    "    5.5m | COLLIE CONQUEROR draft (not shown)"),
    ("LARGE_SHIP_BEACH_DEPTH",    "    6.0m | WARD CALLAHAN + MERCY draft (not shown)"),
    ("LARGE_SHIP_BEACH_DEPTH",    "    6.3m | WARD NAKKI 0 ballast draft (not shown)"),
    ("LARGE_SHIP_BEACH_DEPTH",    "    6.9m | WARD FRIGATE draft (not shown)"),
    ("LARGE_SHIP_BEACH_DEPTH",    " <  7.9m | COLLIE TITAN draft, all large ship beach warning"),
    ("INTEL_DEPTH",               "    8.3m | COLLIE POSEIDON draft (not shown, see details)"),
    ("INTEL_DEPTH",               " < 14.2m | TRIDENT + NAKKI incapable of hiding from intelligence"),
    ("MEDIUM_WATER_DEPTH",        " < 27.4m | WARDEN NAKKI incapable of crush depth"),
    ("SOMEWHAT_DEEP_WATER_DEPTH", " < 32.4m | COLLIE TRIDENT incapable of crush depth"),
    ("EXTREMELY_DEEP",            " > 32.4m | TRIDENT + NAKKI capable of crush depth"),
]

LEGEND_BORDER_COLOR = "#1D2433"
LEGEND_FILL_COLOR = "#F4F1E8"
LEGEND_TEXT_COLOR = LEGEND_BORDER_COLOR
LEGEND_TITLE_STRING = "DEPTH COLOR LEGEND (DETAILED VARIANT)"
LEGEND_SIMPLE_TITLE_STRING = "DEPTH COLOR LEGEND (SIMPLE VARIANT)"
LEGEND_DISCLAIMER_STRING = (
    "NOTE: Sub dive officer readings will be shallower than above depths."
)
LEGEND_DEPTH_TEXT_FONT_SIZE = 26
LEGEND_TITLE_FONT_SIZE = 34
LEGEND_SQUARES_SIZE = 24
LEGEND_LINE_SPACING = 10


# ------------------------------------------------------------------------------
#  Tile geometry
# ------------------------------------------------------------------------------

TILE_SIZE = 2048               # per-region bake resolution (px)
TILE_HALF = TILE_SIZE // 2     # half-extent used when stitching

PIXEL_SIZE_M = 1890.0 / 1776.0 # Blender metres per pixel

HM_SPLIT_M = 20.0
FLY_ALERT_MIN_M = 95.0
FLY_ALERT_MAX_M = 100.0

# Gaussian blur applied to shades.png in 5_finalize_exports.py as the last
# step before masking with the terrain coverage alpha. Kernel must be odd.
# Set SHADES_BLUR_KSIZE = 0 to disable the blur.
SHADES_BLUR_KSIZE = 3
SHADES_BLUR_SIGMA = 0.0  # 0 => cv2 derives sigma from kernel size

# AO bake slope shading (see utils/bake.py:render_ao).
# sh = 1 + C * (max(0, N.z)^P - 1); weak applies to most meshes,
# strong applies to objects flagged via pass_index == 1.
AO_SLOPE_POWER_WEAK   = 5.0
AO_SLOPE_C_WEAK       = 0.6
AO_SLOPE_POWER_STRONG = 5.0
AO_SLOPE_C_STRONG     = 0.75
AO_SLOPE_POWER_SL     = 5.0
AO_SLOPE_C_SL         = 0.6

# After the AO bake, pixels with shade >= AO_NEAR_WHITE_CUTOFF get
# clipped to 255 so near-white noise doesn't read as faint shading.
AO_NEAR_WHITE_CUTOFF = 252

# Step-4 (4_render_spills.py) tunables.
#
# Reserved category collection names that the renderer treats specially;
# anything else under <region>/<cat>/ in a spill .blend is a regular
# spill category discovered dynamically at render time.
RESERVED_CATS = ["terrain", "water", "deep_water", "splines"]

# Spill categories that participate in the normal ao/hm/id bakes.
# Any spill category NOT listed here is excluded from those bakes (its
# meshes still live in the .blend and may be used by other passes such
# as split layers). "water", "terrain" and "splines" are reserved
# categories with special handling; they are listed for clarity but
# always flow through the pipeline regardless.
TERRAIN_WHITELIST = [
    "water",
    "terrain",
    "rocks",
    "glaciers",
    "landscape_meshes_brown",
    "landscape_meshes_gray",
    "splines",
]

# Spline categories whose meshes act as terrain for heightmap/AO/id bakes.
TERRAIN_SPLINE_CATS = ["t1_road", "t2_road", "t3_road"]
# Spline categories rendered into the 'roads' and 'beaches' layers.
ROADS_CATS   = ["t1_road", "t2_road", "t3_road"]
BEACHES_CATS = ["beach", ]

# Regions whose terrain mesh sinks below spill meshes in places; verts
# below TERRAIN_CULL_MIN_Z (metres) are deleted before baking so rays
# hit the intended surface.
Z_FIX_REGIONS = ["HomeRegionC", "HomeRegionW"]
TERRAIN_CULL_MIN_Z = -0.5

# Supersampling rate per pixel side for the per-category ID coverage bake
# (4_render_spills.py). Each pixel fires ID_SSAA^2 rays; per-category
# outputs store the fraction that hit that category. Using SSAA replaces
# the old morphological close that plugged 1-px gaps between e.g. dock
# planks; with ID_SSAA >= 2 those gaps resolve smoothly instead.
ID_SSAA = 4

# Roads/beaches coverage bake: supersampling rate per pixel side and
# terrain drop (m). Terrain is temporarily lowered by this amount and
# added as an occluder so underground artefact splines buried deeper
# than the drop get culled while surface roads still read through.
SPLINE_LAYER_SSAA = 4
SPLINE_LAYER_TERRAIN_DROP = 4

# Split layers: each key is a layer name; its value maps spill
# categories -> per-category tint hex. Each layer is rendered as a
# standalone RGBA PNG (one per layer per region) under
# SPLIT_LAYERS_DIR/<layer>/<region>.png via a Cycles AO pass with a
# transparent film: only the layer's target meshes are visible (they
# occlude each other, so buildings of different categories still
# shadow correctly), producing smooth AA'd alpha edges and real AO
# that defines wall geometry. RGB is tinted per-object via the
# category color.
#
# Split-layer membership no longer affects ao/hm/id inclusion; that is
# controlled independently by TERRAIN_WHITELIST above. A category can
# therefore appear in both the whitelist and a split layer if desired.

SPLIT_LAYERS: Dict[str, Dict[str, str]] = {
    "houses":    {"houses":          "#232323"},
    "ghouses":   {"ghouses":         "#A6AEBE"},
    "industry":  {"industry":        "#30533A"},
    "obstacles": {"obstacles_large": "#232323",
                  "obstacles_small": "#232323",
                  "walls_large":     "#232323",
                  "walls_small":     "#232323",
                  "sidewalks":       "#78787F",
                  "vehicles":        "#7E78A7"}
}

# ignored foliage_collision, foliage_invis, foliage_no_collision
# roofs_ghouses, roofs_misc, ignore

# Shader-based silhouette edge darkening for split-layer renders. The
# map is rendered very zoomed out (each building is only 5-10 px
# across), so the last covered pixel of every footprint must read as a
# crisp dark rim. We do this inside the Cycles shader via a Bevel node,
# whose returned normal bends away from vertical near silhouette edges
# (roof/wall transitions). edge = (1 - max(0, bevel_N.z))^POWER *
# STRENGTH is then subtracted from the shade, so the darkening is
# baked into the render and picks up Cycles' native anti-aliasing on
# the boundary pixel.
#   _RADIUS_PX: width of the dark ring in pixels
#   _STRENGTH:  darkening at the very edge (0 = none, 1 = black)
#   _POWER:     falloff shape; >1 concentrates darkening near the edge
# Set SPLIT_LAYER_EDGE_SHADER_STRENGTH to 0.0 to disable.
# Note: the bevel-normal approach was tried first; it failed on
# silhouettes that have no 3D cliff (e.g. pyramid/sloped roofs), so we
# switched to a 2D-footprint distance map sampled per shading sample
# via a TexImage+Window node pair. Cycles' pixel AA then stamps the
# rim onto the genuine mesh edge regardless of 3D topology.
SPLIT_LAYER_EDGE_SHADER_RADIUS_PX: float = 3.0
SPLIT_LAYER_EDGE_SHADER_STRENGTH: float = 0.9
SPLIT_LAYER_EDGE_SHADER_POWER: float = 1.3

# Minimum HSV value (brightness) for split-layer renders. Any visible pixel
# (alpha > 0) whose V channel is below this threshold is lifted to this value,
# preventing over-dark outputs while leaving transparent pixels untouched.
MIN_SPLIT_LAYER_VALUE: int = 100

# ------------------------------------------------------------------------------
#  Renders
# ------------------------------------------------------------------------------

# Category names used for ID bakes and palette assignment come from
# utils/catalogue.json. CATEGORY_COLORS below supplies the paint
# color for each category (plus the reserved "terrain" category, which is
# built from the heightmap rather than a mesh list).
#
# Reserved categories with special behavior:
#   - "terrain":   built from the 16-bit heightmap (not a whitelist entry)
#   - "water":     whitelist entry; clones are spawned as "deep_water" at
#                  DEEP_WATER_DEPTH metres below
#   - "deep_water": auto-generated occluder clones of water
#
# Any other whitelist key is treated as a regular spill category.

CATEGORY_COLORS: Dict[str, str] = {
    "water":                   "#0000FF",
    "terrain":                 "#00FF00",
    "rocks":                   "#FF0000",
    "glaciers":                "#FFFFFF",
    "landscape_meshes_brown":  "#FF00FF",
    "landscape_meshes_gray":   "#00FFFF",
    "splines":                 "#A2DD43",

    "ghouses":                 "#FFAC46",
    "roofs_ghouses":           "#855B28",
    "houses":                  "#8D46FF",
    "industry":                "#46FF99",
    "roofs_misc":              "#4C268B",
    "obstacles_large":         "#FF1111",
    "obstacles_small":         "#FFFF11",
    "walls_large":             "#A40C0C",
    "walls_small":             "#939310",
    "sidewalks":               "#0EB3B3",
    "vehicles":                "#1111FF",
    "ignore":                  "#111111"
}

# Spline placement: which mesh names belong to which spline category.
# 3_blend_spills.py places these into the focus region's .blend under
# collection 'splines/<category>/'. 4_render_spills.py uses the
# t1_road / t2_road / t3_road / beach categories specially (see below).

SPLINE_CATEGORIES: Dict[str, list] = {
    "t1_road": [
        "Meshes__Environment__Roads__RoadT1Dirt01",
        "Meshes__Environment__Roads__RoadT1Dirt01Snow",
    ],
    "t2_road": [
        "Meshes__Environment__Roads__RoadT2PackedDirt01",
        "Meshes__Environment__Roads__RoadT2PackedDirt01Snow",
    ],
    "t3_road": [
        "Meshes__Environment__Roads__RoadT3Gravel01",
        "Meshes__Environment__Roads__RoadT3Gravel01Snow",
        "Meshes__Environment__Roads__RoadGreatMarch01",
        "Meshes__Environment__Roads__RoadGreatMarch01Snow",
    ],
    "beach": [
        "Engine__Content__EditorLandscapeResources__SplineEditorMesh",
    ],
}

# Per-spline-category colors used by the 'roads' / 'beaches' renders in
# 4_render_spills.py. Entries without a color here fall back to the
# generic 'splines' color.

#rustard road colors
SPLINE_COLORS: Dict[str, str] = {
    "t1_road":                 "#ECECEC",
    "t2_road":                 "#D5AC6C",
    "t3_road":                 "#D5816F",
    "beach":                   "#B6A177",
}

# RGB color (hex) used by the dive_alert overlay in 5_finalize_exports.py;
# alpha fades from full at the water surface to 0 at DEEP_WATER_DEPTH.
DIVE_ALERT_COLOR = "#BA759C"

# Per-layer colors used by 5_finalize_exports.py when compositing the
# terrain weightmap layers under export/_layers/<layer>/ into a single
# materials.png. Keys match the layer folder names (case-insensitive
# lookup at consume time). Layers not listed here get a deterministic
# random bright color assigned at runtime.
#
# "_default" is a special entry: the fallback color used for terrain
# pixels that aren't claimed by any layer. Black is reserved for
# non-terrain pixels and must not be used here.
LAYER_COLORS: Dict[str, str] = {
    "K":                       "#CCCBC9",
    "Grass":                   "#CCB5A5",
    "a":                       "#CCB5A5",
    "Snow":                    "#DDDDDD",
    "SnowRough":               "#DDDDDD",
    "WetSand":                 "#C6B19B",
    "b":                       "#C6B19B",
    "Dirt":                    "#C6B19B",
    "Sand":                    "#C6B19B",
    "Extra02":                 "#C6B19B",
    "Rock":                    "#A3A3A3",
    "Stone":                   "#A3A3A3",
    "Cobble2":                 "#A3A3A3",
    "D":                       "#A3A3A3",
    "Ice":                     "#BCBEE2",
    "Road":                    "#B7A491",
    "TownStone":               "#B7A491",
    "Highway":                 "#B7A491",
    "DataLayer__":             "#B7A491",
    "E":                       "#B7A491",
    "G":                       "#B7A491",
    "MuddyGround":             "#B7A491",
    "TrenchDirt":              "#B7A491",
}

ID_RECOLOR: Dict[str, str] = {
    "water":                   "#DFE8ED",
    "terrain":                 "#9495A1",
    "rocks":                   "#727480",
    "glaciers":                "#E0E0E0",
    "deep_water":              "#9B9B9B",
    "landscape_meshes_brown":  "#90746B",
    "landscape_meshes_gray":   "#5A5A5A",
}



# ------------------------------------------------------------------------------
#  SVG layers (4_render_spills.py)
# ------------------------------------------------------------------------------

# Default False uses the U65 procedural bridge aim renderer in 4_render_spills.py.
# True restores the legacy static SVG stamping path and the step-5 gated
# assembly/bridges_aim.png output.
ENABLE_LEGACY_BRIDGE_AIM = False
LEGACY_BRIDGE_AIM_WATER_ERODE_PX = 25

# Each key defines an output layer rendered via cairosvg into
# SVG_LAYERS_DIR/<layer>/<region>.png, later stitched by
# 5_finalize_exports.py into FINAL_DIR/svg_layers/<layer>.png.
#
# The value is an ORDERED list of SVG categories (subdirectories of
# utils/svg/); placements from earlier categories are drawn first, so
# later categories appear on top. Within a category, <use> elements are
# emitted in the order returned by sorted(glob("*.svg")).
#
# Each utils/svg/<category>/<name>.svg becomes a reusable <symbol
# id="<category>_<name>" overflow="visible"> wrapping the original
# svg's inner content. Placements are pulled from the region's
# export/_json/<region>.json: if <name> matches a blueprint key, the
# blueprint's per-instance "_self" transform is used; otherwise <name>
# is matched as a mesh across "symbols", "groups", and any nested
# blueprint mesh entries.
#
# UE world-space (cm) -> SVG pixel conversion is
# x_px = x_cm * 1776 / 189000 + 1024 (same for y); scale_x/scale_y/yaw
# are applied as-is to the <use> transform.
SVG_LAYERS: Dict[str, list] = {
    "bridges":       ["bridges"],
    "ranges_ai":     ["ranges_ai"],
    "ranges_cg":     ["ranges_cg"],
    "ranges_aag":    ["ranges_aag"],
    "ranges_intel":  ["ranges_intel"],
    "ranges_mh":     ["ranges_mh"],
    "ranges_tap":    ["ranges_tap"],
    "wells":         ["wells"],
    "foliage":       ["foliage_low", "foliage_medium", "foliage_tall"],
    "foliage_invis": ["foliage_invis"],
    "rdz_grace":     ["rdz_grace"],
    "highlights":    ["stairs", "interiors"],
    # Default: rendered procedurally by utils.svg_render.render_bridges_aim_layer.
    # Legacy mode: stamp the restored utils/svg/bridges_aim/*.svg symbols.
    "bridges_aim":   (["bridges_aim"] if ENABLE_LEGACY_BRIDGE_AIM else []),
    "drop_pads":     ["drop_pads"],
    "urban":         ["tiers", "safehouses"],
    "runways":       ["runways"],
    "runways_aim":   ["runways_aim"],
    "garrisons":     ["garrisons"],
}

# ------------------------------------------------------------------------------
#  Bridge aim lines (procedural; utils/svg_render.render_bridges_aim_layer)
# ------------------------------------------------------------------------------
#
# The "bridges_aim" layer is special-cased: instead of stamping the static
# utils/svg/bridges_aim/*.svg symbols, 4_render_spills.py computes the aim
# lines per region. Every bridge gets two sockets emanating from its centre
# along the passage axis (the bridge's local +x / -x). Each socket either:
#   * snaps to a facing socket on a nearby bridge, forming a smooth curve
#     that links the two crossings (so the line never crosses another
#     bridge), or
#   * extends straight outward and is truncated where it meets land, which
#     replaces the old water-erosion gate in 5_finalize_exports.py.
#
# All values are in tile pixels (1 px == PIXEL_SIZE_M metres).

# Blueprint class names (as they appear in export/_json/<region>.json) that
# are treated as bridges. Each placement's "_self" transform spawns one aim
# line pair. This replaces the old utils/svg/bridges_aim/*.svg registry.
BRIDGES_AIM_BLUEPRINTS = [
    "BPDrawbridgeA_C",
    "BPDrawbridgeB_C",
    "BPDrawbridgeC_C",
    "BPTrainBridgeA_C",
    "BPTrainBridgeC_C",
]

# Half-length of each aim line, measured from the bridge centre (matches the
# 100-unit reach of the legacy utils/svg/bridges_aim/*.svg lines).
BRIDGES_AIM_LENGTH_PX = 90.0
# Gap around the bridge centre where no line is drawn (legacy 5-unit gap).
BRIDGES_AIM_GAP_PX = 10.0
# Stroke width / colour of the rasterised aim lines.
BRIDGES_AIM_STROKE_PX = 1.0
BRIDGES_AIM_COLOR = "#B83535"

# Snapping: two sockets on *different* bridges snap together when the two
# bridge centres are within this distance AND the sockets face one another
# (each points roughly toward the other bridge). The closest eligible pair
# is matched first (greedy).
BRIDGES_AIM_SNAP_DIST_PX = 200.0
# Minimum dot(socket_dir, unit_vector_to_other_bridge) for a pair to count
# as "facing" (1.0 = perfectly head-on, 0.5 ~= within 60 degrees).
BRIDGES_AIM_FACE_MIN_DOT = 0.7

# Both unpaired (outward) sockets and snapped pairs are routed through the
# NAVIGABLE water mask: the water coverage eroded by MIN_CLEARANCE_PX, so
# every cell of the route sits at least that far from any shore (the ship is
# modelled as a ball of that radius rolling down the channel). Navigability
# is read from the export/id/water coverage field (water when coverage >=
# BRIDGES_AIM_WATER_THRESH); the bridge deck reads as non-water and so acts
# as a wall -- routes never cross a bridge, and the two sockets of one bridge
# stay on opposite banks. The shortest grid route is then string-pulled into a
# taut polyline (it goes straight as far as the channel allows and only turns
# where an obstacle forces it) and rounded with a centripetal spline.
#
# Clearance guarantee: every control point keeps MIN_CLEARANCE_PX from shore,
# and the spline between them is sampled and repaired (by subdividing) until
# it, too, stays clear -- EXCEPT across spans shorter than MIN_CTRL_SPACING_PX,
# where smoothness wins over clearance (the curve is left alone rather than
# studded with control points every few pixels).
#
#   WATER_THRESH         coverage [0..255] at/above which a pixel is water
#   MIN_CLEARANCE_PX     erosion radius / min distance-to-shore (px) kept by
#                        every control point and the curve spanning them
#   SNAP_TO_WATER_PX     max radius used to pull a bridge gap onto navigable
#                        water before routing (the gap sits on the deck)
#   CENTER_BIAS          OFF (0) by default. A small cost penalty for routing
#                        close to shore, nudging the line toward deeper water.
#                        Keep it low: large values make a long detour through
#                        open water cheaper than the direct channel, which
#                        produces wild U-shapes, and chase the river's medial
#                        axis, which makes the line squiggle. Taut routing
#                        (string-pulling) already keeps the line clear, so
#                        this is only a gentle optional nudge.
#   CHANNEL_PREF_PX      distance-to-shore (px) at/above which water is "deep
#                        enough"; no centring penalty is applied past it.
#   MIN_CTRL_SPACING_PX  control points closer than this are never split
#                        further to chase clearance (see exception above)
#   CURVE_CHECK_STEP_PX  spacing of samples used when testing curve clearance
#   REFINE_PASSES        max subdivision passes enforcing curve clearance
#   PAIR_MAX_DETOUR      a snapped pair's water route is accepted only when its
#                        length is at most this multiple of the straight gap-
#                        to-gap distance. When two close, slightly misaligned
#                        bridges have their direct channel pinched shut by the
#                        erosion, A* would otherwise loop the long way around
#                        the far end of the other bridge's deck -- the U-shape
#                        that crosses back over it. Past this ratio the route
#                        is rejected in favour of a short, direct connector.
BRIDGES_AIM_WATER_THRESH = 200
BRIDGES_AIM_MIN_CLEARANCE_PX = 10.0
BRIDGES_AIM_SNAP_TO_WATER_PX = 30.0
BRIDGES_AIM_CENTER_BIAS = 3.0
BRIDGES_AIM_CHANNEL_PREF_PX = 30.0
BRIDGES_AIM_MIN_CTRL_SPACING_PX = 9.0
BRIDGES_AIM_CURVE_CHECK_STEP_PX = 1.5
BRIDGES_AIM_REFINE_PASSES = 24
BRIDGES_AIM_PAIR_MAX_DETOUR = 1.6
