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

STAGE_FRONT_OCCUPANCY_BOXES = [
    {"name": "stage_lip", "min": [-497, -1660, -120], "max": [-480, 1660, 0]},
    {"name": "outer_bay_l", "min": [-398, -1660, 0], "max": [-330, -1250, 1400]},
    {"name": "outer_bay_r", "min": [-398, 1250, 0], "max": [-330, 1660, 1400]},
    {"name": "vestibule_l", "min": [-354, -1290, 0], "max": [-30, -1230, 1400]},
    {"name": "vestibule_r", "min": [-354, 1230, 0], "max": [-30, 1290, 1400]},
    {"name": "arch_head", "min": [-354, -1285, 1350], "max": [-330, 1285, 1405]},
    {"name": "entablature", "min": [-681, -1660, 1400], "max": [-330, 1660, 1700]},
    {"name": "column_l", "min": [-587.56, -1601.84, 0], "max": [-222.44, -1262.96, 1400]},
    {"name": "column_r", "min": [-587.56, 1262.96, 0], "max": [-222.44, 1601.84, 1400]},
    {"name": "crest", "min": [-646.84, -400, 1260], "max": [-500, 400, 1759.08]},
    {"name": "cat_l", "min": [-174.37, -1146.64, 0], "max": [-35.03, -1033.36, 550]},
    {"name": "cat_r", "min": [-174.37, 1033.36, 0], "max": [-35.03, 1146.64, 550]},
    {"name": "paper_side_l", "min": [-76.05, -1231, -100], "max": [-56.20, -874.87, 1100]},
    {"name": "paper_side_r", "min": [-76.05, 874.90, -100], "max": [-56.20, 1198, 1100]},
    {"name": "paper_valance", "min": [-61.05, -1244.08, 930], "max": [-45, 1244.08, 1330]},
]

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
    "wide_pose": {"location": [-3000.0, 0.0, 819.54],
                  "rotation": [0.0, 0.0, 0.0], "focal_mm": 14.5, "focus_cm": 2644.54},
    "expected_end_pose": {"location": [0.0, 0.0, 150.0],
                          "rotation": [0.0, 0.0, 0.0], "focal_mm": 25.0, "focus_cm": 600.0},
    "stage_front_bbox_cm": {"min": [-681.0, -1660.0, -120.0],
                            "max": [-21.0, 1660.0, 1759.08]},
    "camera_ease": "smootherstep",
    "camera_sample_step_frames": 1,
    "proscenium_half_width_cm": 1050.0,
    "proscenium_bottom_cm": -120.0,
    "proscenium_top_cm": 1250.0,
    "sensor_width_mm": 23.76,
    "sensor_height_mm": 13.365,
    "wide_min_margin_fraction": 0.10,
    "uplight_count": 6,
    "uplight_x_cm": -440.0,
    "uplight_y_min_cm": -1000.0,
    "uplight_y_max_cm": 1000.0,
    "uplight_z_cm": 45.0,
    "uplight_aim_x_cm": -330.0,
    "uplight_aim_z_cm": 1120.0,
    "uplight_lumens": 350.0,
    "uplight_kelvin": 3200.0,
    "uplight_inner_cone_deg": 16.0,
    "uplight_outer_cone_deg": 24.0,
    "uplight_attenuation_cm": 1800.0,
    "uplight_fade_frames": 20,
    "uplight_mesh": "/Game/InfinityStage/Lighting/Fixtures/Meshes/SM_Lantern_ParCan",
    "uplight_cast_shadows": False,
    "uplight_geometry_clearance_cm": 10.0,
    "bulb_seed": "P87-GARY-20261009",
    "bulb_front_min_cm": 70.0,
    "bulb_front_max_cm": 190.0,
    "bulb_side_jitter_cm": 55.0,
    "bulb_yaw_deg": 28.0,
    "bulb_tilt_deg": 18.0,
    "bulb_wing_clearance_cm": 35.0,
    "bulb_stage_front_clearance_cm": 25.0,
    "bulb_trace_up_cm": 120.0,
    "bulb_trace_down_cm": 300.0,
    "stage_front_occupancy_boxes_cm": STAGE_FRONT_OCCUPANCY_BOXES,
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
        ("bulb_stage_front_clearance_cm", 0, 500), ("uplight_geometry_clearance_cm", 0, 200),
        ("wide_min_margin_fraction", 0, 0.4),
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
    _validate_geometry_args(p)
    return p


def _triple(value, label):
    if not isinstance(value, list) or len(value) != 3:
        raise P87Error("%s|three numbers required" % label)
    try:
        return [float(x) for x in value]
    except (TypeError, ValueError):
        raise P87Error("%s|three numbers required" % label)


def _validate_geometry_args(p):
    bbox = p.get("stage_front_bbox_cm")
    if not isinstance(bbox, dict):
        raise P87Error("STAGE_FRONT_BBOX")
    bbox["min"], bbox["max"] = _triple(bbox.get("min"), "STAGE_FRONT_BBOX_MIN"), _triple(bbox.get("max"), "STAGE_FRONT_BBOX_MAX")
    if any(a >= b for a, b in zip(bbox["min"], bbox["max"])):
        raise P87Error("STAGE_FRONT_BBOX_ORDER")
    for label in ("wide_pose", "expected_end_pose"):
        row = p.get(label)
        if not isinstance(row, dict):
            raise P87Error(label.upper())
        row["location"] = _triple(row.get("location"), label.upper() + "_LOCATION")
        row["rotation"] = _triple(row.get("rotation"), label.upper() + "_ROTATION")
        for field in ("focal_mm", "focus_cm"):
            row[field] = float(row[field])
            if row[field] <= 0: raise P87Error("%s_%s" % (label.upper(), field.upper()))
    if any(abs(x) > FLOAT_TOL for x in p["wide_pose"]["rotation"]):
        raise P87Error("WIDE_ROTATION|offline bbox proof requires axis-aligned +X camera")
    boxes = p.get("stage_front_occupancy_boxes_cm")
    if not isinstance(boxes, list) or not boxes:
        raise P87Error("STAGE_FRONT_BOXES|non-empty list required")
    names = set()
    for row in boxes:
        if not isinstance(row, dict) or not row.get("name") or row["name"] in names:
            raise P87Error("STAGE_FRONT_BOX_NAME")
        names.add(row["name"])
        row["min"], row["max"] = _triple(row.get("min"), "BOX_MIN"), _triple(row.get("max"), "BOX_MAX")
        if any(a >= b for a, b in zip(row["min"], row["max"])):
            raise P87Error("STAGE_FRONT_BOX_ORDER|%s" % row["name"])


def point_box_hit(point, boxes, clearance=0.0):
    point = [float(x) for x in point]
    for row in boxes:
        if all(float(row["min"][i]) - clearance <= point[i] <= float(row["max"][i]) + clearance for i in range(3)):
            return row["name"]
    return None


def framing_metrics(pose, bbox, sensor_width_mm, sensor_height_mm):
    """Axis-aligned +X camera proof over all eight conservative AABB corners."""
    cx, cy, cz = pose["location"]; focal = float(pose["focal_mm"])
    worst_h = worst_v = 0.0
    for x in (bbox["min"][0], bbox["max"][0]):
        depth = x - cx
        if depth <= 0: raise P87Error("WIDE_BBOX_BEHIND_CAMERA")
        for y in (bbox["min"][1], bbox["max"][1]):
            worst_h = max(worst_h, abs(y - cy) * 2.0 * focal / (depth * sensor_width_mm))
        for z in (bbox["min"][2], bbox["max"][2]):
            worst_v = max(worst_v, abs(z - cz) * 2.0 * focal / (depth * sensor_height_mm))
    return {"horizontal_fill_fraction": worst_h, "vertical_fill_fraction": worst_v,
            "horizontal_margin_fraction": 1.0 - worst_h, "vertical_margin_fraction": 1.0 - worst_v}


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
    expected_end = p["expected_end_pose"]
    for field, tolerance in (("location", POSE_POS_TOL_CM), ("rotation", POSE_ROT_TOL_DEG)):
        if any(abs(float(a) - float(b)) > tolerance for a, b in zip(live_end_pose[field], expected_end[field])):
            raise P87Error("CAMERA_END_POSE_DRIFT|%s|live=%s|expected=%s" %
                           (field, live_end_pose[field], expected_end[field]))
    for field, tolerance in (("focal_mm", FLOAT_TOL), ("focus_cm", POSE_POS_TOL_CM)):
        if abs(float(live_end_pose[field]) - float(expected_end[field])) > tolerance:
            raise P87Error("CAMERA_END_POSE_DRIFT|%s|live=%s|expected=%s" %
                           (field, live_end_pose[field], expected_end[field]))
    framing = framing_metrics(wide, p["stage_front_bbox_cm"], p["sensor_width_mm"], p["sensor_height_mm"])
    if min(framing["horizontal_margin_fraction"], framing["vertical_margin_fraction"]) + FLOAT_TOL < p["wide_min_margin_fraction"]:
        raise P87Error("WIDE_FRAME_MARGIN|%s" % canonical(framing))
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
            "wide_framing": framing, "filmback_mm": [p["sensor_width_mm"], p["sensor_height_mm"]],
            "framed_bounds_cm": copy.deepcopy(p["stage_front_bbox_cm"]),
            "end_pose": copy.deepcopy(live_end_pose), "end_framing": "exact guarded P01 start pose",
            "keys": keys}


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
        hit = point_box_hit(loc, p["stage_front_occupancy_boxes_cm"], p["uplight_geometry_clearance_cm"])
        if hit:
            raise P87Error("UPLIGHT_STAGE_FRONT_INTERSECTION|%02d|%s" % (i, hit))
        aim = [p["uplight_aim_x_cm"], y, p["uplight_aim_z_cm"]]
        rows.append({"label": "P87 Stage Front Uplight %02d" % i, "location": loc,
                     "rotation": aim_rotation(loc, aim), "mesh": p["uplight_mesh"],
                     "lumens": p["uplight_lumens"], "kelvin": p["uplight_kelvin"],
                     "inner_cone_deg": p["uplight_inner_cone_deg"],
                     "outer_cone_deg": p["uplight_outer_cone_deg"],
                     "attenuation_cm": p["uplight_attenuation_cm"], "cast_shadows": False,
                     "geometry_clearance_cm": p["uplight_geometry_clearance_cm"],
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
        hit = point_box_hit(loc, p["stage_front_occupancy_boxes_cm"], p["bulb_stage_front_clearance_cm"])
        if hit:
            raise P87Error("BULB_STAGE_FRONT_INTERSECTION|%s|%s" % (identity, hit))
        rows.append({"id": identity, "location_xy_proposal": loc[:2], "floor_z_fallback_cm": loc[2],
                     "rotation_pyr": [pitch, yaw, roll], "wing_clearance_cm": distance,
                     "stage_front_clearance_cm": p["bulb_stage_front_clearance_cm"],
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
