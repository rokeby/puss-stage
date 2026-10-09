"""Pure planning and safety rules for P87 Opening fixes.

No Unreal import belongs in this module.  The live adapter and the offline fake
backend both consume these plans, which keeps the destructive path testable.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os


FPS = 25.0
OPENING_END_FRAME = 2409
PARTS = ("CURTAIN", "CAMERA", "UPLIGHTS", "BULBS")
MODES = ("DRY", "APPLY", "REVERT")
CONFIRM = {m: "%s P87" % m for m in MODES}
FLOAT_TOL = 1.0e-4
POSE_POS_TOL_CM = 0.01
POSE_ROT_TOL_DEG = 0.001

DEFAULTS = {
    "parts": list(PARTS),
    "ack_records": [],
    "fps": FPS,
    "opening_end_frame": OPENING_END_FRAME,
    # Must be pinned after live DRY.  00:37:50 is ambiguous at 25 fps.
    "first_flurry_frame": None,
    "first_flurry_clock": "UNRESOLVED: Gary 00:37:50; resolve Master vs Opening-local",
    "curtain_fall_frames": 250,
    "curtain_hold_offset_ticks": 23200,
    "curtain_pile_offset_ticks": 263999,
    "wide_pose": {"location": [-2400.0, 0.0, 150.0],
                  "rotation": [9.0, 0.0, 0.0], "focal_mm": 15.0, "focus_cm": 100000.0},
    "camera_ease": "smootherstep",
    "camera_sample_step_frames": 1,
    "proscenium_half_width_cm": 1050.0,
    "proscenium_bottom_cm": -120.0,
    "proscenium_top_cm": 1250.0,
    "sensor_width_mm": 36.0,
    "sensor_height_mm": 20.25,
    "uplight_count": 6,
    "uplight_x_cm": -135.0,
    "uplight_y_min_cm": -850.0,
    "uplight_y_max_cm": 850.0,
    "uplight_z_cm": 45.0,
    "uplight_aim_x_cm": -60.0,
    "uplight_aim_z_cm": 1120.0,
    "uplight_lumens": 350.0,
    "uplight_kelvin": 3200.0,
    "uplight_inner_cone_deg": 16.0,
    "uplight_outer_cone_deg": 24.0,
    "uplight_attenuation_cm": 1800.0,
    "uplight_fade_frames": 20,
    "uplight_mesh": "/Game/InfinityStage/Lighting/Fixtures/Meshes/SM_Lantern_ParCan",
    "uplight_cast_shadows": False,
    "bulb_seed": "P87-GARY-20261009",
    "bulb_front_min_cm": 70.0,
    "bulb_front_max_cm": 190.0,
    "bulb_side_jitter_cm": 55.0,
    "bulb_yaw_deg": 28.0,
    "bulb_tilt_deg": 18.0,
    "bulb_wing_clearance_cm": 35.0,
    "bulb_trace_up_cm": 120.0,
    "bulb_trace_down_cm": 300.0,
}


class P87Error(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def stable_unit(seed, identity, value_name):
    """One independent draw for one named value; adding fields cannot reorder draws."""
    raw = "%s|%s|%s" % (seed, identity, value_name)
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:13], 16) / float(16 ** 13)


def _num(p, name, lo, hi, integer=False):
    try:
        value = int(p[name]) if integer else float(p[name])
    except (KeyError, TypeError, ValueError):
        raise P87Error("ARG_%s|not numeric" % name)
    if not lo <= value <= hi:
        raise P87Error("ARG_%s|%s outside [%s,%s]" % (name, value, lo, hi))
    p[name] = value


def merge_args(raw=None, require_flurry=False):
    raw = raw or {}
    unknown = sorted(set(raw) - set(DEFAULTS))
    if unknown:
        raise P87Error("UNKNOWN_ARGS|%s" % unknown)
    p = copy.deepcopy(DEFAULTS)
    p.update(copy.deepcopy(raw))
    if not isinstance(p["parts"], list) or not p["parts"]:
        raise P87Error("PARTS|non-empty list required")
    p["parts"] = [str(v).upper() for v in p["parts"]]
    if len(set(p["parts"])) != len(p["parts"]) or any(v not in PARTS for v in p["parts"]):
        raise P87Error("PARTS|must be unique subset of %s" % (PARTS,))
    if not isinstance(p["ack_records"], list) or any(not isinstance(v, str) for v in p["ack_records"]):
        raise P87Error("ACK_RECORDS|must be a list of exact paths")
    p["ack_records"] = sorted(set(os.path.normcase(os.path.abspath(v)) for v in p["ack_records"]))
    for name, lo, hi in (
        ("fps", 1, 120), ("opening_end_frame", 2, 100000),
        ("curtain_fall_frames", 1, 10000), ("camera_sample_step_frames", 1, 100),
        ("uplight_count", 2, 12), ("uplight_lumens", 0, 5000),
        ("uplight_kelvin", 1800, 10000), ("uplight_fade_frames", 1, 1000),
        ("bulb_front_min_cm", 1, 1000), ("bulb_front_max_cm", 1, 2000),
        ("bulb_side_jitter_cm", 0, 500), ("bulb_yaw_deg", 0, 180),
        ("bulb_tilt_deg", 0, 89), ("bulb_wing_clearance_cm", 0, 500),
    ):
        _num(p, name, lo, hi, name in {"opening_end_frame", "curtain_fall_frames", "camera_sample_step_frames",
                                       "uplight_count", "uplight_fade_frames"})
    if p["bulb_front_min_cm"] >= p["bulb_front_max_cm"]:
        raise P87Error("BULB_FRONT_BAND|minimum must be below maximum")
    ff = p.get("first_flurry_frame")
    if ff is not None:
        ff = int(ff)
        if not 1 <= ff < p["opening_end_frame"]:
            raise P87Error("FIRST_FLURRY_FRAME|outside Opening")
        p["first_flurry_frame"] = ff
    if require_flurry and p["first_flurry_frame"] is None:
        raise P87Error("FIRST_FLURRY_UNPINNED|run live DRY; pin Opening-local frame after clock report")
    if p["camera_ease"] != "smootherstep":
        raise P87Error("CAMERA_EASE|only smootherstep is implemented")
    if not str(p["uplight_mesh"]).startswith("/Game/"):
        raise P87Error("UPLIGHT_MESH|must be /Game path")
    if p["uplight_cast_shadows"] is not False:
        raise P87Error("UPLIGHT_SHADOWS|P87 GPU gate requires false by default")
    return p


def preflight(mode, confirm, context, record, parts):
    failures = []
    if mode not in MODES:
        failures.append("MODE")
    if confirm != CONFIRM.get(mode):
        failures.append("CONFIRM|need='%s'" % CONFIRM.get(mode))
    if context.get("pie"):
        failures.append("PIE_ACTIVE")
    if context.get("sequencer_open"):
        failures.append("SEQUENCER_OPEN")
    if context.get("world") != "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice":
        failures.append("WORLD")
    if context.get("dirty") != {"content": [], "maps": []}:
        failures.append("DIRTY_CENSUS|%s" % canonical(context.get("dirty")))
    if mode == "APPLY" and record:
        failures.append("ACTIVE_RECORD")
    if mode == "REVERT" and not record:
        failures.append("REVERT_RECORD_ABSENT")
    if record and mode == "REVERT" and record.get("status") != "saved_readback_verified":
        failures.append("REVERT_RECORD_STATE|%s" % record.get("status"))
    if record and mode == "REVERT" and sorted(record.get("parts", [])) != sorted(parts):
        failures.append("REVERT_PARTS_MISMATCH")
    return failures


def smootherstep(t):
    t = max(0.0, min(1.0, float(t)))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def lerp(a, b, t):
    return float(a) + (float(b) - float(a)) * t


def camera_plan(p, live_end_pose):
    start = p["first_flurry_frame"]
    end = p["opening_end_frame"]
    if start is None:
        return {"status": "blocked_on_clock", "end_pose": copy.deepcopy(live_end_pose)}
    if start + 2 >= end:
        raise P87Error("CAMERA_DURATION|too short")
    wide = p["wide_pose"]
    fields = ("location", "rotation")
    if any(len(wide[k]) != 3 or len(live_end_pose[k]) != 3 for k in fields):
        raise P87Error("CAMERA_POSE|location/rotation triples required")
    frames = sorted(set([0, start] + list(range(start, end + 1, p["camera_sample_step_frames"])) + [end]))
    keys = []
    for f in frames:
        u = 0.0 if f <= start else smootherstep((f - start) / float(end - start))
        keys.append({"frame": f,
                     "location": [lerp(a, b, u) for a, b in zip(wide["location"], live_end_pose["location"])],
                     "rotation": [lerp(a, b, u) for a, b in zip(wide["rotation"], live_end_pose["rotation"])],
                     "focal_mm": lerp(wide["focal_mm"], live_end_pose["focal_mm"], u),
                     "focus_cm": lerp(wide["focus_cm"], live_end_pose["focus_cm"], u)})
    if keys[-1]["location"] != list(live_end_pose["location"]) or keys[-1]["rotation"] != list(live_end_pose["rotation"]):
        raise P87Error("CAMERA_END_IDENTITY")
    return {"status": "planned", "hold_end_frame": start, "move_frames": end - start,
            "move_seconds": (end - start) / p["fps"], "wide_pose": copy.deepcopy(wide),
            "end_pose": copy.deepcopy(live_end_pose), "keys": keys}


def curtain_plan(p, live_sections):
    if p["first_flurry_frame"] is None:
        return {"status": "blocked_on_clock", "live_sections": copy.deepcopy(live_sections)}
    start = p["first_flurry_frame"]
    fall_end = start + p["curtain_fall_frames"]
    if fall_end >= p["opening_end_frame"]:
        raise P87Error("CURTAIN_FALL_OVERRUN")
    sections = [
        {"role": "HOLD", "start": 0, "end": start, "start_offset_ticks": p["curtain_hold_offset_ticks"]},
        {"role": "FALL", "start": start, "end": fall_end, "start_offset_ticks": p["curtain_hold_offset_ticks"]},
        {"role": "PILE_HOLD", "start": fall_end, "end": p["opening_end_frame"],
         "start_offset_ticks": p["curtain_pile_offset_ticks"]},
    ]
    return {"status": "planned", "sections": sections, "fall_count": 1,
            "deactivated_sections": [s for s in live_sections if s.get("role") == "FALL" and s != sections[1]],
            "recorded_not_deleted": True}


def aim_rotation(origin, target):
    dx, dy, dz = [float(b) - float(a) for a, b in zip(origin, target)]
    flat = math.hypot(dx, dy)
    return [math.degrees(math.atan2(dz, flat)), math.degrees(math.atan2(dy, dx)), 0.0]


def uplight_plan(p):
    f = p["first_flurry_frame"]
    if f is None:
        return {"status": "blocked_on_clock", "rows": []}
    ys = ([0.0] if p["uplight_count"] == 1 else
          [lerp(p["uplight_y_min_cm"], p["uplight_y_max_cm"], i / float(p["uplight_count"] - 1))
           for i in range(p["uplight_count"])])
    rows = []
    for i, y in enumerate(ys, 1):
        loc = [p["uplight_x_cm"], y, p["uplight_z_cm"]]
        aim = [p["uplight_aim_x_cm"], y, p["uplight_aim_z_cm"]]
        rows.append({"label": "P87 Stage Front Uplight %02d" % i, "location": loc,
                     "rotation": aim_rotation(loc, aim), "mesh": p["uplight_mesh"],
                     "lumens": p["uplight_lumens"], "kelvin": p["uplight_kelvin"],
                     "inner_cone_deg": p["uplight_inner_cone_deg"],
                     "outer_cone_deg": p["uplight_outer_cone_deg"],
                     "attenuation_cm": p["uplight_attenuation_cm"], "cast_shadows": False,
                     "intensity_keys": [[0, 0.0], [f, 0.0], [f + p["uplight_fade_frames"], p["uplight_lumens"]]]})
    return {"status": "planned", "rows": rows, "on_after_first_flurry": True,
            "new_shadow_casters": sum(bool(r["cast_shadows"]) for r in rows)}


def bulb_scatter_plan(p, bulbs):
    rows = []
    for bulb in sorted(bulbs, key=lambda v: v["id"]):
        identity = bulb["id"]
        side = -1.0 if float(bulb.get("side_sign", -1)) < 0 else 1.0
        front = lerp(p["bulb_front_min_cm"], p["bulb_front_max_cm"], stable_unit(p["bulb_seed"], identity, "front"))
        lateral = (stable_unit(p["bulb_seed"], identity, "lateral") * 2.0 - 1.0) * p["bulb_side_jitter_cm"]
        # Wing-local +X is downstage/front in the existing floor-practicals planner.
        loc = [float(bulb["wing_location"][0]) - front,
               float(bulb["wing_location"][1]) + side * abs(lateral),
               float(bulb["floor_z_cm"])]
        yaw = (stable_unit(p["bulb_seed"], identity, "yaw") * 2.0 - 1.0) * p["bulb_yaw_deg"]
        pitch = (stable_unit(p["bulb_seed"], identity, "tilt_pitch") * 2.0 - 1.0) * p["bulb_tilt_deg"]
        roll = (stable_unit(p["bulb_seed"], identity, "tilt_roll") * 2.0 - 1.0) * p["bulb_tilt_deg"]
        distance = math.hypot(loc[0] - float(bulb["wing_location"][0]), loc[1] - float(bulb["wing_location"][1]))
        if distance < p["bulb_wing_clearance_cm"]:
            raise P87Error("BULB_CLEARANCE|%s|%.3f" % (identity, distance))
        rows.append({"id": identity, "location_xy_proposal": loc[:2], "floor_z_fallback_cm": loc[2],
                     "rotation_pyr": [pitch, yaw, roll], "wing_clearance_cm": distance,
                     "trace": {"start_z": loc[2] + p["bulb_trace_up_cm"],
                               "end_z": loc[2] - p["bulb_trace_down_cm"], "channel": "ECC_CAT_FLOOR"},
                     "draws": {name: stable_unit(p["bulb_seed"], identity, name)
                               for name in ("front", "lateral", "yaw", "tilt_pitch", "tilt_roll")}})
    return {"status": "planned", "seed": p["bulb_seed"], "rows": rows,
            "single_draw_per_named_value": True}


def build_plan(p, live):
    plan = {"schema": 1, "parts": list(p["parts"]), "clock": copy.deepcopy(live["clock"]),
            "targets": {"show": live["show_path"], "level": live["level_path"],
                        "opening_sequence": live["sequence_path"]}}
    if "CURTAIN" in p["parts"]:
        plan["curtain"] = curtain_plan(p, live.get("curtain_sections", []))
    if "CAMERA" in p["parts"]:
        plan["camera"] = camera_plan(p, live["camera_end_pose"])
    if "UPLIGHTS" in p["parts"]:
        plan["uplights"] = uplight_plan(p)
    if "BULBS" in p["parts"]:
        plan["bulbs"] = bulb_scatter_plan(p, live.get("bulbs", []))
    plan["plan_sha256"] = digest(plan)
    return plan


def changed_paths(before, after, prefix=""):
    out = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            out += changed_paths(before.get(key), after.get(key), prefix + ("." if prefix else "") + str(key))
    elif isinstance(before, list) and isinstance(after, list):
        for i in range(max(len(before), len(after))):
            a = before[i] if i < len(before) else None
            b = after[i] if i < len(after) else None
            out += changed_paths(a, b, "%s[%d]" % (prefix, i))
    elif before != after:
        out.append(prefix)
    return out


def apply_model(state, plan):
    new = copy.deepcopy(state)
    for part in plan["parts"]:
        new[part.lower()] = copy.deepcopy(plan[part.lower()])
    return new


def revert_model(current, record):
    if digest(current) != record["after_sha256"]:
        raise P87Error("REVERT_DRIFT|current state differs from recorded after state")
    return copy.deepcopy(record["before"])
