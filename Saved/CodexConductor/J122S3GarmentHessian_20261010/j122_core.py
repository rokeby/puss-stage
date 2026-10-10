"""Offline-safe contracts for Job 122's twelve hessian garment MIs."""
from __future__ import annotations

import hashlib
import json
from typing import Any


SCHEMA = "j122_s3_garment_hessian/1"
FIGURES = (
    "Shore01_M56", "Shore02_F52", "Shore03_M59",
    "Shore04_F55", "Shore05_M53", "Shore06_F25",
)
KINDS = ("Shirt", "Shorts")
ROOT = "/Game/Metahuman/ShoreCast_20260910/OutfitHessian"
TEX_ROOT = "/Game/Metahuman/ShoreCast_20260910/ShroudHessian/Textures"
WEAVE_BC = TEX_ROOT + "/T_Shroud_Weave_BC"
WEAVE_N = TEX_ROOT + "/T_Shroud_Weave_N"
STAIN_BY_FIGURE = {
    "Shore01_M56": 3, "Shore02_F52": 5, "Shore03_M59": 6,
    "Shore04_F55": 4, "Shore05_M53": 7, "Shore06_F25": 8,
}
DETAIL = {
    "A": {"color": "DetailTex_Color", "normal": "detailTex_normal",
          "tiling": "DetailTex_UVTtiling", "color_switch": "DoDetailColor",
          "normal_switch": "DoDetailNormal"},
    "B": {"color": "B_DetailTex_Color", "normal": "B_detailTex_normal",
          "tiling": "B_DetailTex_UVTtiling", "color_switch": "B_DoDetailColor",
          "normal_switch": "B_DoDetailNormal"},
    # The live parameter inventory supplied with J115 contains no C detail pair.
    "C": None,
}
PRINT = {"map": "Print1Map", "tiling": "Print1Tiling", "strength": "Print1Strength",
         "switch": "bDoPrint1", "colors": {x: "Print1Color" + x for x in "ABC"}}
ACTIVE_SWITCHES = ("DoMaterialC", "MaterialB option")


class ContractError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ContractError(message)


def targets() -> list[str]:
    return [f"{ROOT}/MI_{figure}_{kind}_Hessian_v1" for figure in FIGURES for kind in KINDS]


def figure_from_path(path: str) -> str:
    hits = [figure for figure in FIGURES if f"MI_{figure}_" in path]
    require(len(hits) == 1, "TARGET_FIGURE|" + path)
    return hits[0]


def stain_paths(figure: str) -> dict[str, str]:
    number = STAIN_BY_FIGURE[figure]
    return {"mask": f"{TEX_ROOT}/T_Shroud_Stain_{number:02d}_Mask",
            "tint": f"{TEX_ROOT}/T_Shroud_Stain_{number:02d}_Tint"}


def validate_args(raw: dict[str, Any], record_exists: bool) -> dict[str, Any]:
    mode = str(raw.get("mode", "PROBE")).upper()
    require(mode in ("PROBE", "DRY", "APPLY", "VERIFY", "REVERT"), "MODE|" + mode)
    if mode in ("APPLY", "REVERT"):
        require(raw.get("confirm") == f"{mode} J122GARMENTS", f"CONFIRM|want '{mode} J122GARMENTS'")
    if mode == "APPLY":
        require(not record_exists, "RECORD_EXISTS|REVERT first")
    if mode in ("VERIFY", "REVERT"):
        require(record_exists, "NO_RECORD")
    tiling = raw.get("weave_tiling", 8.0)
    strength = raw.get("print_strength", 1.0)
    color = raw.get("print_color", [1.0, 1.0, 1.0, 1.0])
    kind = str(raw.get("print_texture_kind", "tint")).lower()
    require(isinstance(tiling, (int, float)) and not isinstance(tiling, bool) and 0.01 <= tiling <= 100.0,
            "WEAVE_TILING|0.01..100")
    require(isinstance(strength, (int, float)) and not isinstance(strength, bool) and 0.0 <= strength <= 4.0,
            "PRINT_STRENGTH|0..4")
    require(isinstance(color, list) and len(color) == 4 and all(isinstance(x, (int, float)) for x in color),
            "PRINT_COLOR|RGBA")
    require(all(0.0 <= float(x) <= 1.0 for x in color), "PRINT_COLOR|0..1")
    require(kind in ("mask", "tint"), "PRINT_TEXTURE_KIND|mask or tint")
    return {"mode": mode, "weave_tiling": float(tiling), "print_strength": float(strength),
            "print_color": [float(x) for x in color], "print_texture_kind": kind}


def infer_layer(effective_switches: dict[str, bool]) -> dict[str, str]:
    missing = [name for name in ACTIVE_SWITCHES if name not in effective_switches]
    require(not missing, "ACTIVE_SWITCHES_MISSING|" + repr(missing))
    if effective_switches["DoMaterialC"]:
        layer = "C"
        reason = "DoMaterialC=True"
    elif effective_switches["MaterialB option"]:
        layer = "B"
        reason = "DoMaterialC=False and MaterialB option=True"
    else:
        layer = "A"
        reason = "DoMaterialC=False and MaterialB option=False"
    return {"layer": layer, "reason": reason, "proof": "effective_static_switch_selection"}


def plan(names: dict[str, list[str]], effective_switches: dict[str, bool], graph_probe: dict[str, Any]) -> dict[str, Any]:
    layer_evidence = infer_layer(effective_switches)
    layer = layer_evidence["layer"]
    problems: list[str] = []
    masks_probe = graph_probe.get("masks", {})
    consumers = graph_probe.get("parameter_consumers", {})
    detail = DETAIL[layer]
    if detail is None:
        problems.append("ACTIVE_LAYER_C_HAS_NO_EXPOSED_DETAIL_COLOR_NORMAL_PAIR")
    else:
        for key in ("color", "normal"):
            if detail[key] not in names["texture"]:
                problems.append("DETAIL_TEXTURE_MISSING|" + detail[key])
            elif not consumers.get(detail[key]):
                problems.append("DETAIL_GRAPH_FEED_UNPROVED|" + detail[key])
        if detail["tiling"] not in names["scalar"]:
            problems.append("DETAIL_TILING_MISSING|" + detail["tiling"])
        for key in ("color_switch", "normal_switch"):
            if detail[key] not in names["static_switch"]:
                problems.append("DETAIL_SWITCH_MISSING|" + detail[key])
    if PRINT["map"] not in names["texture"]:
        problems.append("PRINT_MAP_MISSING")
    elif not consumers.get(PRINT["map"]):
        problems.append("PRINT_GRAPH_FEED_UNPROVED|" + PRINT["map"])
    if PRINT["colors"][layer] not in names["vector"]:
        problems.append("PRINT_COLOR_MISSING|" + PRINT["colors"][layer])
    for name in (PRINT["tiling"], PRINT["strength"]):
        if name not in names["scalar"]:
            problems.append("PRINT_SCALAR_MISSING|" + name)
    if PRINT["switch"] not in names["static_switch"]:
        problems.append("PRINT_SWITCH_MISSING")
    if not masks_probe.get("parameter_found"):
        problems.append("MASKS_PARAMETER_NOT_FOUND_IN_MASTER_GRAPH")
    if not any(row.get("channel") for row in masks_probe.get("channel_consumers", [])):
        problems.append("MASKS_CHANNEL_USE_UNPROVED")
    return {"active_layer": layer_evidence, "detail": detail, "print": PRINT,
            "masks_probe": masks_probe,
            "selected_graph_feeds": {name: consumers.get(name, []) for name in
                                      ([detail["color"], detail["normal"]] if detail else []) + [PRINT["map"]]},
            "problems": problems, "apply_ready": not problems}


def fingerprint(value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
