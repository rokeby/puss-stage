"""Pure contract for the P03 bone-dune asset and Show-placement tools.

No Blender or Unreal import is allowed here: the offline harness imports this module.
Coordinates are centimetres in a P03 station frame: +X follows the route, +Y is right.
"""
from __future__ import annotations

import copy
import math
import random


TARGET_CUE = {
    "passage": "P03",
    "ordinal": 13,
    "label": "P03 Wing 013",
    "guid": "622946E51046353D4D27EF8B20389CE3",
    "side": "R",
    "measured_inner_edge_cm": 638.739,
    "evidence": "Saved/CodexConductor/Effects_20261007/fx_smoke_place_report_DRY_20261007-103456.json",
}

BONE_SPECS = (
    {
        "name": "HominidCranium",
        "prompt": "Isolated small adult hominid cranium, anatomically believable, empty eye sockets, no lower jaw, aged dry bone with restrained sand staining and weathering, archaeological specimen, neutral object only, no stand, no other bones, calm matte surface.",
        "bbox_cm": [24, 20, 28],
        "target_longest_cm": 28.0,
        "seed": 4311,
        "symmetry": "balanced",
    },
    {
        "name": "HominidPelvis",
        "prompt": "Isolated adult hominid pelvis bone, anatomically believable complete pelvic ring, aged dry bone with restrained sand staining and weathering, archaeological specimen, neutral object only, no stand, no other bones, calm matte surface.",
        "bbox_cm": [30, 22, 24],
        "target_longest_cm": 30.0,
        "seed": 4312,
        "symmetry": "balanced",
    },
    {
        "name": "HominidScapula",
        "prompt": "Isolated human scapula shoulder blade, anatomically believable thin plate and spine, aged dry bone with restrained sand staining and weathering, archaeological specimen, neutral object only, no stand, no other bones, calm matte surface.",
        "bbox_cm": [18, 5, 24],
        "target_longest_cm": 24.0,
        "seed": 4313,
        "symmetry": "asymmetric",
    },
    {
        "name": "HominidVertebraChain",
        "prompt": "Short articulated chain of five human vertebrae with natural spacing, anatomically believable, aged dry bone with restrained sand staining and weathering, archaeological specimen, neutral object only, no stand, no other bones, calm matte surface.",
        "bbox_cm": [14, 32, 14],
        "target_longest_cm": 32.0,
        "seed": 4314,
        "symmetry": "balanced",
    },
    {
        "name": "HominidFemurLong",
        "prompt": "Single complete adult human femur long bone, anatomically believable head neck shaft and condyles, aged dry bone with restrained sand staining and weathering, archaeological specimen, neutral object only, no stand, no other bones, calm matte surface.",
        "bbox_cm": [10, 48, 10],
        "target_longest_cm": 48.0,
        "seed": 4315,
        "symmetry": "asymmetric",
    },
    {
        "name": "HominidHandBones",
        "prompt": "Isolated partial human hand skeleton, carpals metacarpals and finger bones held in a natural loose arrangement, anatomically believable, aged dry bone with restrained sand staining and weathering, archaeological specimen, neutral object only, no stand, no other bones, calm matte surface.",
        "bbox_cm": [18, 5, 20],
        "target_longest_cm": 20.0,
        "seed": 4316,
        "symmetry": "asymmetric",
    },
)

DEFAULT_BONE_LAYOUT = [
    {"bone": "HominidCranium", "xy_cm": [-95.0, -30.0], "rotation_rpy_deg": [12.0, 78.0, -18.0], "burial_depth_cm": 11.0},
    {"bone": "HominidPelvis", "xy_cm": [45.0, 72.0], "rotation_rpy_deg": [-8.0, 22.0, 31.0], "burial_depth_cm": 10.0},
    {"bone": "HominidScapula", "xy_cm": [-185.0, 95.0], "rotation_rpy_deg": [24.0, 56.0, 8.0], "burial_depth_cm": 7.0},
    {"bone": "HominidVertebraChain", "xy_cm": [75.0, -72.0], "rotation_rpy_deg": [18.0, 68.0, -38.0], "burial_depth_cm": 9.0},
    {"bone": "HominidFemurLong", "xy_cm": [-20.0, -135.0], "rotation_rpy_deg": [4.0, 82.0, 54.0], "burial_depth_cm": 7.0},
    {"bone": "HominidHandBones", "xy_cm": [125.0, 80.0], "rotation_rpy_deg": [-12.0, 38.0, 17.0], "burial_depth_cm": 5.0},
]

DEFAULTS = {
    "mode": "DRY",
    "seed": 1703,
    "cue_label": TARGET_CUE["label"],
    "cue_guid": TARGET_CUE["guid"],
    "dune": {
        "length_cm": 800.0,
        "width_cm": 600.0,
        "height_cm": 350.0,
        "grid_x": 121,
        "grid_y": 91,
        "ripple_spacing_cm": 34.0,
        "ripple_height_cm": 5.5,
        "station_offset_cm": [100.0, 500.0, 0.0],
        "yaw_deg": 0.0,
    },
    "bone_layout": DEFAULT_BONE_LAYOUT,
    "revert_accept_drift": False,
}

CONFIRMS = {
    "APPLY": "APPLY P03 BONE DUNE",
    "REVERT": "REVERT P03 BONE DUNE",
}


def require(condition, token):
    if not condition:
        raise ValueError(token)


def check_args(raw=None):
    raw = copy.deepcopy(raw or {})
    unknown = sorted(set(raw) - set(DEFAULTS) - {"confirm"})
    require(not unknown, "UNKNOWN_ARGS|%s" % unknown)
    out = copy.deepcopy(DEFAULTS)
    out.update({k: v for k, v in raw.items() if k != "dune"})
    if "dune" in raw:
        require(isinstance(raw["dune"], dict), "DUNE_ARGS_OBJECT")
        bad = sorted(set(raw["dune"]) - set(DEFAULTS["dune"]))
        require(not bad, "UNKNOWN_DUNE_ARGS|%s" % bad)
        out["dune"].update(raw["dune"])
    out["mode"] = str(out["mode"]).upper()
    require(out["mode"] in ("DRY", "APPLY", "REVERT"), "MODE")
    if out["mode"] in CONFIRMS:
        require(raw.get("confirm") == CONFIRMS[out["mode"]], "CONFIRM_MISSING")
    require(out["cue_label"] == TARGET_CUE["label"], "CUE_LABEL")
    require(out["cue_guid"] == TARGET_CUE["guid"], "CUE_GUID")
    d = out["dune"]
    require(400.0 <= float(d["length_cm"]) <= 1200.0, "DUNE_LENGTH_RANGE")
    require(300.0 <= float(d["width_cm"]) <= 900.0, "DUNE_WIDTH_RANGE")
    require(150.0 <= float(d["height_cm"]) <= 500.0, "DUNE_HEIGHT_RANGE")
    require(41 <= int(d["grid_x"]) <= 401 and 41 <= int(d["grid_y"]) <= 401, "DUNE_GRID_RANGE")
    require(float(d["ripple_spacing_cm"]) >= 12.0, "RIPPLE_SPACING")
    require(0.0 <= float(d["ripple_height_cm"]) <= 15.0, "RIPPLE_HEIGHT")
    require(len(d["station_offset_cm"]) == 3, "STATION_OFFSET")
    require(float(d["station_offset_cm"][1]) - float(d["width_cm"]) * 0.5 >= 100.0,
            "CAT_ROUTE_CLEARANCE_LT_100CM")
    layout = out["bone_layout"]
    require(isinstance(layout, list) and len(layout) == len(BONE_SPECS), "BONE_LAYOUT_COUNT")
    required = {"bone", "xy_cm", "rotation_rpy_deg", "burial_depth_cm"}
    require(all(isinstance(row, dict) and set(row) == required for row in layout), "BONE_LAYOUT_KEYS")
    require({row["bone"] for row in layout} == {row["name"] for row in BONE_SPECS}, "BONE_LAYOUT_NAMES")
    for row in layout:
        require(len(row["xy_cm"]) == 2 and len(row["rotation_rpy_deg"]) == 3, "BONE_LAYOUT_VECTOR")
        require(abs(float(row["xy_cm"][0])) < float(d["length_cm"]) * 0.46 and
                abs(float(row["xy_cm"][1])) < float(d["width_cm"]) * 0.46, "BONE_LAYOUT_FOOTPRINT")
        require(2.0 <= float(row["burial_depth_cm"]) <= 30.0, "BONE_LAYOUT_BURIAL")
    require(isinstance(out["revert_accept_drift"], bool), "REVERT_DRIFT_BOOL")
    return out


def dune_height_cm(x_cm, y_cm, dune=None, seed=1703):
    """Asymmetric wind dune: long windward ramp, steep lee face and lobed toe."""
    d = copy.deepcopy(DEFAULTS["dune"])
    if dune:
        d.update(dune)
    half_x = float(d["length_cm"]) * 0.5
    half_y = float(d["width_cm"]) * 0.5
    u = float(x_cm) / half_x
    v = float(y_cm) / half_y
    radial = max(0.0, 1.0 - (abs(u) ** 2.15 + abs(v) ** 2.35))
    if radial <= 0.0:
        return 0.0
    crest = -0.08 + 0.10 * math.sin(v * 1.6)
    if u <= crest:
        along = max(0.0, (u + 1.0) / (crest + 1.0)) ** 1.55
    else:
        # A compact slip face ends at a broad, low toe. Keeping this span much
        # shorter than the windward run makes the asymmetry measurable rather
        # than relying on camera angle to communicate it.
        along = max(0.0, 1.0 - (u - crest) / 0.45) ** 1.05
    cross = max(0.0, 1.0 - abs(v) ** 2.0) ** 0.72
    h = float(d["height_cm"]) * along * cross * (radial ** 0.22)
    # Cross-wind ripples live mainly on the windward shoulder, not the collapsing lee face.
    ripple_gate = max(0.0, min(1.0, (crest + 0.18 - u) / 0.8)) * radial
    phase = (float(x_cm) + 0.31 * float(y_cm) + seed * 0.17) / float(d["ripple_spacing_cm"])
    h += float(d["ripple_height_cm"]) * math.sin(phase * math.tau) * ripple_gate
    # Two deterministic slump lobes at the lee toe.
    rng = random.Random(int(seed))
    for sign in (-1.0, 1.0):
        cx = half_x * (0.76 + rng.uniform(-0.025, 0.025))
        cy = sign * half_y * (0.28 + rng.uniform(-0.04, 0.04))
        sx, sy = half_x * 0.14, half_y * 0.22
        h += float(d["height_cm"]) * 0.085 * math.exp(-((x_cm - cx) / sx) ** 2 - ((y_cm - cy) / sy) ** 2)
    return max(0.0, h)


def bone_placements(args=None):
    a = check_args(args or {})
    d = a["dune"]
    station = [float(x) for x in d["station_offset_cm"]]
    rows = []
    for item in a["bone_layout"]:
        name = item["bone"]
        x, y = (float(v) for v in item["xy_cm"])
        rpy = [float(v) for v in item["rotation_rpy_deg"]]
        burial = float(item["burial_depth_cm"])
        surface = dune_height_cm(x, y, d, a["seed"])
        local = [float(x), float(y), round(surface - burial, 3)]
        rows.append({
            "bone": name,
            "mesh": "/Game/InfinityStage/Dev/Generated/P03Bones/%s/SM_%s" % (name, name),
            "dune_local_transform": {"location_cm": local, "rotation_rpy_deg": list(rpy), "scale": [1, 1, 1]},
            "station_relative_transform": {
                "location_cm": [round(station[i] + local[i], 3) for i in range(3)],
                "rotation_rpy_deg": list(rpy), "scale": [1, 1, 1],
            },
            "burial_depth_cm": burial,
            "sampled_surface_cm": round(surface, 3),
        })
    return rows


def placement_plan(args=None):
    a = check_args(args or {})
    d = a["dune"]
    dune_row = {
        "label": "P03 BONE DUNE",
        "mesh": "/Game/InfinityStage/Dev/Generated/P03Dune/SM_P03_BoneDune",
        "transform": {"location_cm": list(d["station_offset_cm"]),
                      "rotation_rpy_deg": [0.0, 0.0, float(d["yaw_deg"])], "scale": [1, 1, 1]},
        "kind": "PROP", "anchor": "STATION",
    }
    bones = []
    for row in bone_placements(a):
        bones.append({"label": "P03 BONE DUNE " + row["bone"], "mesh": row["mesh"],
                      "transform": row["station_relative_transform"], "kind": "PROP", "anchor": "STATION",
                      "burial_depth_cm": row["burial_depth_cm"]})
    return {"target": copy.deepcopy(TARGET_CUE), "dune": dune_row, "bones": bones,
            "route_clearance_cm": float(d["station_offset_cm"][1]) - float(d["width_cm"]) * 0.5,
            "all": [dune_row] + bones}


def drift_paths(expected, actual, path=""):
    if type(expected) is not type(actual):
        return [path or "$type"]
    if isinstance(expected, dict):
        out = []
        for key in sorted(set(expected) | set(actual)):
            child = "%s.%s" % (path, key) if path else key
            if key not in expected or key not in actual:
                out.append(child)
            else:
                out.extend(drift_paths(expected[key], actual[key], child))
        return out
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return [path + ".length"]
        out = []
        for index, (left, right) in enumerate(zip(expected, actual)):
            out.extend(drift_paths(left, right, "%s[%d]" % (path, index)))
        return out
    if isinstance(expected, float):
        return [] if abs(expected - actual) <= 1e-4 else [path]
    return [] if expected == actual else [path]
