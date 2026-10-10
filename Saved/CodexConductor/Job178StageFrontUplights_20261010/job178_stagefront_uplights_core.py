"""Pure contract for Job 178A.  This module never imports Unreal."""
from __future__ import annotations

import hashlib
import json
import math

PIECES = (
    ("arch", "Stage Front Architecture", 0.0, 0.72),
    ("wall", "Stage Front Wall", -720.0, 0.48),
    ("gilt", "Stage Front Gilt", 720.0, 0.62),
    ("crest", "Stage Front Crest", 0.0, 0.72),
    ("column_l", "Stage Front Column L", -1432.4, 0.56),
    ("column_r", "Stage Front Column R", 1432.4, 0.56),
    ("cat_l", "Stage Front Cat Candelabra L", -1090.0, 0.50),
    ("cat_r", "Stage Front Cat Candelabra R", 1090.0, 0.50),
)
EXPECTED_LABELS = tuple(row[1] for row in PIECES)
P87_PREFIX = "P87 Stage Front Uplight "
OWNER_PREFIX = "JOB178 Stage Front 3D Uplight - "
OWNER_TAG = "PussStage.Job178.StageFront3DUplight"
CONFIRM = {"DRY": "DRY JOB178A STAGE FRONT UPLIGHTS",
           "APPLY": "APPLY JOB178A STAGE FRONT UPLIGHTS",
           "REVERT": "REVERT JOB178A STAGE FRONT UPLIGHTS"}


class ContractError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise ContractError(message)


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_args(raw, active=False):
    args = dict(raw)
    mode = str(args.get("mode", "DRY")).upper()
    require(mode in CONFIRM, "MODE")
    require(args.get("confirm") == CONFIRM[mode], "CONFIRM|" + CONFIRM[mode])
    require(not active if mode == "APPLY" else True, "ACTIVE_RECORD_EXISTS")
    require(active if mode == "REVERT" else True, "ACTIVE_RECORD_REQUIRED")
    args["mode"] = mode
    args.setdefault("stage_lip_x_cm", -440.0)
    args.setdefault("stage_lip_z_cm", 45.0)
    args.setdefault("max_y_cm", 1550.0)
    for key, lo, hi in (("stage_lip_x_cm", -1000.0, 100.0), ("stage_lip_z_cm", -20.0, 200.0),
                        ("max_y_cm", 1000.0, 2000.0)):
        args[key] = float(args[key]); require(lo <= args[key] <= hi, "ARG_RANGE|" + key)
    return args


def aim_rotation(location, target):
    dx, dy, dz = (float(target[i]) - float(location[i]) for i in range(3))
    planar = math.hypot(dx, dy)
    return [0.0, math.degrees(math.atan2(dz, planar)), math.degrees(math.atan2(dy, dx))]


def plan(piece_rows, style, args):
    by_label = {row["label"]: row for row in piece_rows}
    require(set(by_label) == set(EXPECTED_LABELS), "PIECE_LABEL_SET")
    require(len(piece_rows) == 8, "PIECE_COUNT")
    rows = []
    for key, label, fallback_y, aim_fraction in PIECES:
        piece = by_label[label]
        require("PussStage.StageFront3D" in piece["tags"], "PIECE_TAG|" + label)
        require("PussStage.StageFront3D." + key.split("_")[0] in piece["tags"], "PIECE_KIND_TAG|" + label)
        centre, extent = piece["bounds_center_cm"], piece["bounds_extent_cm"]
        y = max(-args["max_y_cm"], min(args["max_y_cm"], fallback_y if abs(fallback_y) > 1 else centre[1]))
        location = [args["stage_lip_x_cm"], y, args["stage_lip_z_cm"]]
        target = [centre[0], centre[1], centre[2] - extent[2] + 2.0 * extent[2] * aim_fraction]
        rows.append({"piece": key, "piece_label": label, "piece_path": piece["path"],
                     "label": OWNER_PREFIX + label, "location_cm": location, "target_cm": target,
                     "rotation_rpy_deg": aim_rotation(location, target), "style": dict(style)})
    out = {"pieces": piece_rows, "source_style": style, "lights": rows}
    out["hash"] = stable_hash(out)
    return out


def compare_light(actual, wanted, tolerance=1e-4):
    problems = []
    for key in ("intensity", "temperature_kelvin", "inner_cone_angle_degrees", "outer_cone_angle_degrees",
                "attenuation_radius_cm", "light_falloff_exponent", "volumetric_scattering_intensity"):
        if abs(float(actual[key]) - float(wanted[key])) > tolerance:
            problems.append(key)
    for key in ("cast_shadows", "cast_volumetric_shadow", "use_temperature", "use_inverse_squared_falloff"):
        if bool(actual[key]) != bool(wanted[key]): problems.append(key)
    if any(abs(float(a)-float(b)) > tolerance for a, b in zip(actual["color_rgb_linear"], wanted["color_rgb_linear"])):
        problems.append("color_rgb_linear")
    return problems
