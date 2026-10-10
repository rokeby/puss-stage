"""Offline-safe planning helpers for job 115 S3 hessian shirts."""
from __future__ import annotations

import hashlib
import os
from typing import Any


SCHEMA = "j115_s3_hessian_shirts/1"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
OUTFIT_DIR = "/Game/Metahuman/ShoreCast_20260910/OutfitHessian"
WEAVE_BC = "/Game/Metahuman/ShoreCast_20260910/ShroudHessian/Textures/T_Shroud_Weave_BC"
WEAVE_N = "/Game/Metahuman/ShoreCast_20260910/ShroudHessian/Textures/T_Shroud_Weave_N"
FIGURES = (
    "Shore01_M56", "Shore02_F52", "Shore03_M59",
    "Shore04_F55", "Shore05_M53", "Shore06_F25",
)
BODY_SHAPE = {
    "Shore01_M56": "A", "Shore02_F52": "B", "Shore03_M59": "A",
    "Shore04_F55": "B", "Shore05_M53": "A", "Shore06_F25": "B",
}
BASE_LABELS = {figure: figure + " Clam" for figure in FIGURES}
P40_TAG = "P40.ShoreFigure"
DEFAULT_MEAN_SRGB = (0.6658808661, 0.6412755957, 0.6070530256)
DEFAULT_MEAN_LINEAR = (0.4400743730, 0.4071881324, 0.3630656971)


class PlanError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PlanError(message)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def srgb_to_linear(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def texture_mean(path: str) -> dict[str, Any]:
    """Measure the source pixels; alpha-zero pixels are excluded if alpha exists."""
    from PIL import Image, ImageStat

    require(os.path.isfile(path), "WEAVE_SOURCE_MISSING|" + path)
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
        alpha = rgba.getchannel("A")
        extrema = alpha.getextrema()
        mask = alpha if extrema != (255, 255) else None
        rgb = rgba.convert("RGB")
        stat = ImageStat.Stat(rgb, mask=mask)
        srgb = tuple(float(x) / 255.0 for x in stat.mean[:3])
        # Average each source pixel in linear space.  Linearising the already
        # averaged sRGB value is materially darker and is not the same colour
        # statistic used by the earlier hessian work.
        histogram = rgb.histogram(mask=mask)
        linear_values = [srgb_to_linear(index / 255.0) for index in range(256)]
        linear = []
        for channel in range(3):
            counts = histogram[channel * 256:(channel + 1) * 256]
            total = float(sum(counts))
            require(total > 0.0, "WEAVE_SOURCE_EMPTY|" + path)
            linear.append(sum(linear_values[index] * counts[index] for index in range(256)) / total)
        linear = tuple(linear)
        pixels = int(rgba.width * rgba.height)
        return {"path": os.path.normpath(path), "sha256": sha256_file(path),
                "size": [rgba.width, rgba.height], "sampled_pixels": pixels,
                "mean_srgb": list(srgb), "mean_linear": list(linear)}


def classify_material(path: str | None) -> str:
    low = (path or "").lower()
    if "defaultgarment" in low and "_shirt" in low:
        return "shirt"
    if "defaultgarment" in low and "_short" in low:
        return "short"
    return "unknown"


def child_path(figure: str, version: int) -> str:
    require(figure in FIGURES, "FIGURE|" + figure)
    return "%s/MI_%s_Shirt_Hessian_v%d" % (OUTFIT_DIR, figure, version)


def validate_args(raw: dict[str, Any], record_exists: bool = False) -> dict[str, Any]:
    mode = str(raw.get("mode", "DRY")).upper()
    require(mode in ("DRY", "APPLY", "VERIFY", "REVERT"), "MODE|" + mode)
    if mode in ("APPLY", "REVERT"):
        require(raw.get("confirm") == "%s J115SHIRTS" % mode,
                "CONFIRM|want '%s J115SHIRTS'" % mode)
    if mode == "APPLY":
        require(not record_exists, "RECORD_EXISTS|REVERT first")
    if mode in ("VERIFY", "REVERT"):
        require(record_exists, "NO_RECORD")
    version = raw.get("asset_version", 1)
    require(isinstance(version, int) and not isinstance(version, bool) and 1 <= version <= 99,
            "ASSET_VERSION|1..99")
    roughness = raw.get("fallback_roughness", 0.84)
    require(isinstance(roughness, (int, float)) and not isinstance(roughness, bool) and 0.5 <= roughness <= 1.0,
            "FALLBACK_ROUGHNESS|0.5..1.0")
    specular = raw.get("fallback_specular", 0.18)
    require(isinstance(specular, (int, float)) and not isinstance(specular, bool) and 0.0 <= specular <= 0.5,
            "FALLBACK_SPECULAR|0..0.5")
    candidates = raw.get("parameter_candidates") or {}
    required = ("base_color_texture", "normal_texture", "tint_vector", "roughness_scalar")
    require(all(isinstance(candidates.get(key), list) and candidates[key] for key in required),
            "PARAMETER_CANDIDATES|missing required lists")
    switches = raw.get("texture_mode_static_switches", {})
    require(isinstance(switches, dict) and all(isinstance(k, str) and isinstance(v, bool)
                                               for k, v in switches.items()),
            "STATIC_SWITCHES|values must be JSON true/false")
    return {"mode": mode, "asset_version": version, "fallback_roughness": float(roughness),
            "fallback_specular": float(specular), "parameter_candidates": candidates,
            "texture_mode_static_switches": switches,
            "source_png_relative": str(raw.get("source_png_relative",
                "Saved/CodexConductor/ShroudHessian_20261008/T_Shroud_Weave_BC.png"))}


def choose_named(available: list[str], preferred: list[str], token: str, required: bool = True) -> str | None:
    exact = [name for name in preferred if name in available]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise PlanError("%s_AMBIGUOUS|%r" % (token, exact))
    folded = {name.casefold(): name for name in available}
    hits = [folded[name.casefold()] for name in preferred if name.casefold() in folded]
    hits = sorted(set(hits))
    if len(hits) == 1:
        return hits[0]
    if required:
        raise PlanError("%s_MISSING|available=%r" % (token, available))
    return None


def plan_parameter_strategy(parameter_names: dict[str, list[str]], candidates: dict[str, list[str]]) -> dict[str, Any]:
    bc = choose_named(parameter_names["texture"], candidates["base_color_texture"], "BASE_COLOR_TEXTURE", False)
    normal = choose_named(parameter_names["texture"], candidates["normal_texture"], "NORMAL_TEXTURE", False)
    if bc is not None or normal is not None:
        require(bc is not None and normal is not None,
                "TEXTURE_PAIR_INCOMPLETE|base=%r normal=%r" % (bc, normal))
        return {"mode": "textures", "base_color_texture": bc, "normal_texture": normal}
    tint = choose_named(parameter_names["vector"], candidates["tint_vector"], "TINT_VECTOR")
    roughness = choose_named(parameter_names["scalar"], candidates["roughness_scalar"], "ROUGHNESS_SCALAR")
    specular = choose_named(parameter_names["scalar"], candidates.get("specular_scalar", []),
                            "SPECULAR_SCALAR", False)
    return {"mode": "tint_roughness", "tint_vector": tint,
            "roughness_scalar": roughness, "specular_scalar": specular}


def expected_actor_scope(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Require exactly one canonical actor per figure and include only P40-tagged variants."""
    base_counts = {figure: 0 for figure in FIGURES}
    selected = []
    for row in rows:
        figure = row.get("figure")
        if figure not in FIGURES:
            continue
        is_base = row.get("label") == BASE_LABELS[figure]
        is_variant = P40_TAG in set(row.get("tags") or [])
        if is_base:
            base_counts[figure] += 1
        if is_base or is_variant:
            selected.append(row)
    require(all(count == 1 for count in base_counts.values()), "BASE_ACTOR_COUNTS|%r" % base_counts)
    require(len({row["path"] for row in selected}) == len(selected), "ACTOR_PATH_DUPLICATE")
    return sorted(selected, key=lambda row: (row["figure"], row["label"], row["path"]))


DIAG_CANDIDATES = (
    "gloss_dark", "uv_channel", "weave_scale", "texture_interpretation", "transparency_culling",
)


def diagnostic_fix_matrix() -> list[dict[str, Any]]:
    """Exact create-only fixes, each intentionally gated on diag-v2 evidence."""
    return [
        {"candidate": "gloss_dark",
         "gate": "effective roughness/specular values or base shading model are outside the reviewed cloth regime",
         "fix": "create versioned child shroud MIs overriding exposed Roughness/Specular; if the base shading model is wrong, create a fresh versioned cloth master and child MIs, then reassign only recorded shroud slots"},
        {"candidate": "uv_channel",
         "gate": "a referenced TextureCoordinate index is >= the cloth mesh UV-channel count",
         "fix": "create a versioned cloth material master that samples the weave from a valid measured UV channel (normally UV0), create child MIs, then reassign only recorded shroud slots; do not edit the existing graph"},
        {"candidate": "weave_scale",
         "gate": "effective tiling/UV/scale values are zero, extreme, or disagree across the visibly bad figures",
         "fix": "create versioned child shroud MIs with reviewed nonzero tiling scalar overrides; if tiling is hard-coded, create a fresh versioned master with parameterised UV scaling"},
        {"candidate": "texture_interpretation",
         "gate": "BC is not sRGB/color-compressed, N is sRGB or not normal-map compressed, or measured green-channel orientation is wrong",
         "fix": "duplicate BC/N to versioned texture assets, set the duplicate import/compression flags, create child shroud MIs referencing only the duplicates, and leave source textures untouched"},
        {"candidate": "transparency_culling",
         "gate": "blend mode, two-sided, opacity clip, or effective opacity/mask values disagree with the opaque/masked two-sided cloth design",
         "fix": "create a fresh versioned cloth master with the measured approved blend/two-sided/clip settings and correctly wired opacity/mask, using StaticSwitch True/False pins explicitly; create child MIs and reassign only recorded shroud slots"},
    ]
