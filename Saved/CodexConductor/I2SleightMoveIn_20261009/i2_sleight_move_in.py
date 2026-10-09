"""P34: replace I2's frame-1250 hard-cut feeling with a matched push-in.

Offline-authored.  ``unreal`` is imported only by :class:`UnrealBackend` when
the conductor runs this file through the guarded project-Python route.

Modes and exact confirms:
  DRY / ``DRY I2MOVEIN``
  APPLY / ``APPLY I2MOVEIN``
  REVERT / ``REVERT I2MOVEIN``

Evidence tiers:
  declaration-proven: scope, GUIDs, cut frame, modes, defaults, backup/save and
    preview contracts come from
    Docs/Conductor/codex_briefs/p34_i2_sleight_move_in.md:1-50.
  measured-upstream: the read-only evidence files named by that brief contain
    the saved p27/I2Order snapshots and I2PROBE-222723 drape bounds.  DRY reads
    them again and records SHA-256 hashes; this source does not call that a new
    Unreal measurement.
  measured-offline: test_i2_sleight_move_in.py exercises fake-Unreal negative
    controls and an APPLY->REVERT round trip.
  inferred: analytical frame coverage predicts hidden drape edges.  Only Gary's
    later rendered review can accept the look.
"""

from __future__ import division

import copy
import datetime
import hashlib
import json
import math
import os
import shutil


TOOL = "I2_MOVE_IN"
TOOL_VERSION = "2026-10-09a"
FOLDER = "I2SleightMoveIn_20261009"
SEQ_PATH = "/Game/InfinityStage/Interactions/LS_Interaction_02_Turnips"
MAP_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
HANGAR_GUID = "55C3CAC6436730E6463F3A8220611E72"
MOUTH_GUID = "E6CF63464549232FD6CEA88D81178F0D"
MOUTH_COMPONENT_GUID = "A4162B8C4B7F601B6D73BF97DB42FD91"
HANGAR_NAME = "I2 Hangar Hold Camera"
HANGAR_TAG = "I2HangarHoldCamera"
MOUTH_NAME = "I2 Sleight Mouth Camera"
MOUTH_COMPONENT_NAME = "I2 Sleight Mouth Camera/CameraComponent"
HANGAR_COMPONENT_NAME = "I2 Hangar Hold Camera/CameraComponent"
TRACK_NAME = "I2 Sleight Move-In (Conductor)"
ORIGINAL_TRACK_NAME = "CurtainSleight (Conductor)"
TRANSFORM_CLASS = "MovieScene3DTransformTrack"
FLOAT_CLASS = "MovieSceneFloatTrack"
EXPECTED_FPS = 25.0
EXPECTED_TICK = 24000.0
EXPECTED_PLAYBACK = [0, 2226]
CUT_FRAME = 1250
RECORD = "i2_sleight_move_in_record.json"
PLAN_FILE = "i2_sleight_move_in_plan.json"
CONFIRMS = {"DRY": "DRY I2MOVEIN", "APPLY": "APPLY I2MOVEIN", "REVERT": "REVERT I2MOVEIN"}
DEFAULT_EVIDENCE = {
    "hangar_record": "E:/PussStage/Saved/CodexConductor/I2HangarCam_20261009/i2_hangar_cam_record.json",
    "order_record": "E:/PussStage/Saved/CodexConductor/I2Order_20261008/i2_order_record.json",
    "drape_probe": "E:/PussStage/Saved/CodexConductor/I2Order_20261008/i2_drape_probe_I2PROBE-222723.json",
}
DEFAULTS = {
    "move_start": 1150,
    "close_distance_cm": 600.0,
    "mouth_after": "EASE_OUT",
    "ease_out_s": 6.0,
    "horizontal_fov_deg": 50.0,
    "output_aspect": 16.0 / 9.0,
    "edge_guard_cm": 0.0,
    "location_tolerance_cm": 0.01,
    "rotation_tolerance_deg": 0.001,
    "lens_tolerance_mm": 0.001,
    "evidence": DEFAULT_EVIDENCE,
}
PREVIEW_FRAMES = [1150, 1200, 1249, 1250, 1300, 1400]
TRANSFORM_CHANNELS = (
    "Location.X", "Location.Y", "Location.Z",
    "Rotation.X", "Rotation.Y", "Rotation.Z",
    "Scale.X", "Scale.Y", "Scale.Z",
)


class Stop(RuntimeError):
    pass


class PlanError(ValueError):
    pass


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sha256_file(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def json_read(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise PlanError("EVIDENCE_MISSING|%s" % path)
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def json_write(path, value, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if exclusive:
        with open(path, "x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def merged_params(raw):
    raw = raw or {}
    p = dict(DEFAULTS)
    p.update(raw)
    evidence = dict(DEFAULT_EVIDENCE)
    evidence.update(raw.get("evidence") or {})
    p["evidence"] = {key: os.path.abspath(str(value)) for key, value in evidence.items()}
    p["move_start"] = int(p["move_start"])
    for key in ("close_distance_cm", "ease_out_s", "horizontal_fov_deg", "output_aspect", "edge_guard_cm",
                "location_tolerance_cm", "rotation_tolerance_deg", "lens_tolerance_mm"):
        p[key] = float(p[key])
    p["mouth_after"] = str(p["mouth_after"]).upper()
    if not 0 <= p["move_start"] < CUT_FRAME - 1:
        raise PlanError("MOVE_START_RANGE|%d" % p["move_start"])
    if p["close_distance_cm"] <= 1.0:
        raise PlanError("CLOSE_DISTANCE_RANGE|%s" % p["close_distance_cm"])
    if p["mouth_after"] not in ("EASE_OUT", "HOLD_CLOSE"):
        raise PlanError("MOUTH_AFTER|%s" % p["mouth_after"])
    if p["mouth_after"] == "EASE_OUT" and p["ease_out_s"] <= 0.0:
        raise PlanError("EASE_OUT_SECONDS|%s" % p["ease_out_s"])
    if not 1.0 < p["horizontal_fov_deg"] < 170.0:
        raise PlanError("HFOV_RANGE|%s" % p["horizontal_fov_deg"])
    if p["output_aspect"] <= 0.0 or p["edge_guard_cm"] < 0.0:
        raise PlanError("FRAME_GEOMETRY_RANGE")
    return p


def ease_cubic_in_out(t):
    t = max(0.0, min(1.0, float(t)))
    return 4.0 * t * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def ease_cubic_out(t):
    t = max(0.0, min(1.0, float(t)))
    return 1.0 - (1.0 - t) ** 3


def lerp(a, b, t):
    return float(a) + (float(b) - float(a)) * float(t)


def lerp3(a, b, t):
    return [lerp(a[index], b[index], t) for index in range(3)]


def rotate_z(local, yaw_deg):
    angle = math.radians(float(yaw_deg))
    x, y, z = [float(value) for value in local]
    return [x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle), z]


def world_from_frame(frame, local):
    delta = rotate_z(local, frame["yaw"])
    return [float(frame["origin"][index]) + delta[index] for index in range(3)]


def local_from_frame(frame, world):
    delta = [float(world[index]) - float(frame["origin"][index]) for index in range(3)]
    return rotate_z(delta, -float(frame["yaw"]))


def focal_for_hfov(sensor_width_mm, hfov_deg):
    return float(sensor_width_mm) / (2.0 * math.tan(math.radians(float(hfov_deg)) / 2.0))


def hfov_for_focal(sensor_width_mm, focal_mm):
    return math.degrees(2.0 * math.atan(float(sensor_width_mm) / (2.0 * float(focal_mm))))


def _track(binding, cls, prop):
    rows = [row for row in binding.get("tracks", [])
            if row.get("class") == cls and row.get("property") == prop]
    if len(rows) != 1:
        raise PlanError("TRACK_COUNT|%s|%s|%s|%d" % (binding.get("name"), cls, prop, len(rows)))
    return rows[0]


def _binding(snapshot, guid, expected_name=None):
    rows = [row for row in snapshot.get("bindings", []) if row.get("guid") == guid]
    if len(rows) != 1:
        raise PlanError("BINDING_GUID_COUNT|%s|%d" % (guid, len(rows)))
    if expected_name is not None and rows[0].get("name") != expected_name:
        raise PlanError("BINDING_NAME|%s|%s!=%s" % (guid, rows[0].get("name"), expected_name))
    return rows[0]


def _channel(track, name):
    sections = track.get("sections", [])
    if len(sections) != 1:
        raise PlanError("SECTION_COUNT|%s|%d" % (track.get("property"), len(sections)))
    rows = [row for row in sections[0].get("channels", []) if row.get("name") == name]
    if len(rows) != 1:
        raise PlanError("CHANNEL_COUNT|%s|%s|%d" % (track.get("property"), name, len(rows)))
    return rows[0]


def _constant_value(channel, expected_keys=None, tolerance=1.0e-4):
    keys = channel.get("keys", [])
    if expected_keys is not None and [int(row[0]) for row in keys] != list(expected_keys):
        raise PlanError("RECORDED_CONSTANT_KEY_TIMES|%s" % keys)
    values = [float(row[1]) for row in keys]
    if not values or max(values) - min(values) > tolerance:
        raise PlanError("RECORDED_CONSTANT_VALUES|%s" % keys)
    return values[0]


def load_evidence(params):
    paths = params["evidence"]
    hangar = json_read(paths["hangar_record"])
    order = json_read(paths["order_record"])
    probe = json_read(paths["drape_probe"])
    if not hangar.get("applied") or not order.get("applied"):
        raise PlanError("EVIDENCE_NOT_APPLIED")
    if hangar.get("sequence") != SEQ_PATH or order.get("sequence") != SEQ_PATH:
        raise PlanError("EVIDENCE_SEQUENCE")
    drapes = []
    for row in probe.get("drapes", []):
        assets = [gc.get("asset", "") for gc in row.get("gc", [])]
        if any("GC_CurtainDrop_Opening" in asset for asset in assets):
            drapes.append(row)
    hangar_point = hangar["plan"]["actor"]["focus_point_world_cm"]
    hangar_rows = sorted(drapes, key=lambda row: math.hypot(float(row["origin"][0]) - float(hangar_point[0]),
                                                            float(row["origin"][1]) - float(hangar_point[1])))
    mouth_rows = sorted(drapes, key=lambda row: math.hypot(float(row["origin"][0]) + 1.0,
                                                           float(row["origin"][1]) - 160000.0))
    if not hangar_rows or not mouth_rows or hangar_rows[0] is mouth_rows[0]:
        raise PlanError("DRAPE_EVIDENCE_SELECTION")
    mouth_extent = [float(value) for value in mouth_rows[0]["extent"]]
    evidence = {
        "paths": paths,
        "sha256": {key: sha256_file(value) for key, value in paths.items()},
        "hangar_actor": hangar["actor_after"],
        "hangar_snapshot": hangar["snapshot_after"],
        "order_snapshot": order["snapshot_after"],
        "hangar_drape": {"origin": [float(hangar_point[0]), float(hangar_point[1]),
                                      float(hangar_rows[0]["origin"][2])],
                           "yaw": float(hangar["actor_after"]["rotation_deg"]["yaw"])},
        "mouth_drape": {"origin": [float(value) for value in mouth_rows[0]["origin"]], "yaw": 0.0},
        "drape_bounds": {"half_width_cm": mouth_extent[1], "half_height_cm": mouth_extent[2],
                          "half_thickness_cm": mouth_extent[0]},
    }
    return evidence


def recorded_mouth_constant(evidence):
    snap = evidence["hangar_snapshot"]
    mouth = _binding(snap, MOUTH_GUID, MOUTH_NAME)
    component = _binding(snap, MOUTH_COMPONENT_GUID, MOUTH_COMPONENT_NAME)
    if component.get("parent", "") != MOUTH_GUID:
        raise PlanError("MOUTH_COMPONENT_PARENT")
    transform = _track(mouth, TRANSFORM_CLASS, "Transform")
    values = {}
    for name in TRANSFORM_CHANNELS[:6]:
        values[name] = _constant_value(_channel(transform, name), expected_keys=[0, 2226])
    focal = _constant_value(_channel(_track(component, FLOAT_CLASS, "CurrentFocalLength"), "None"),
                            expected_keys=[0, 2226])
    focus = _constant_value(_channel(_track(component, FLOAT_CLASS, "ManualFocusDistance"), "None"),
                            expected_keys=[0, 2226])
    return {"transform": values, "focal_mm": focal, "focus_cm": focus}


def _assert_live_baseline(live, evidence, params):
    snapshot = live["snapshot"]
    if abs(float(snapshot["display_rate"]) - EXPECTED_FPS) > 1.0e-9:
        raise PlanError("DISPLAY_RATE|%s" % snapshot["display_rate"])
    if abs(float(snapshot["tick_resolution"]) - EXPECTED_TICK) > 1.0e-9:
        raise PlanError("TICK_RESOLUTION|%s" % snapshot["tick_resolution"])
    if snapshot["playback"] != EXPECTED_PLAYBACK:
        raise PlanError("PLAYBACK|%s" % snapshot["playback"])
    hangar = _binding(snapshot, HANGAR_GUID, HANGAR_NAME)
    mouth = _binding(snapshot, MOUTH_GUID, MOUTH_NAME)
    component = _binding(snapshot, MOUTH_COMPONENT_GUID, MOUTH_COMPONENT_NAME)
    if component.get("parent", "") != MOUTH_GUID:
        raise PlanError("MOUTH_COMPONENT_PARENT_LIVE")
    cuts = sorted([[row["binding_guid"], int(row["range"][0]), int(row["range"][1])]
                   for row in snapshot.get("cuts", []) if row.get("active")], key=lambda row: row[1])
    if cuts != [[HANGAR_GUID, 0, CUT_FRAME], [MOUTH_GUID, CUT_FRAME, EXPECTED_PLAYBACK[1]]]:
        raise PlanError("CUT_OR_BINDING_GUARD|%s" % cuts)
    existing = [row for row in hangar.get("tracks", []) if row.get("class") == TRANSFORM_CLASS]
    if existing:
        raise PlanError("EXISTING_HANGAR_TRANSFORM_TRACK")
    children = [row for row in snapshot.get("bindings", []) if row.get("parent") == HANGAR_GUID]
    if children:
        raise PlanError("EXISTING_HANGAR_CHILD_BINDING|%s" % [row.get("guid") for row in children])
    expected = recorded_mouth_constant(evidence)["transform"]
    transform = _track(mouth, TRANSFORM_CLASS, "Transform")
    for name in TRANSFORM_CHANNELS[:6]:
        got = _constant_value(_channel(transform, name), expected_keys=[0, 2226])
        if abs(got - expected[name]) > params["location_tolerance_cm"]:
            raise PlanError("MOUTH_RECORDED_CONSTANT_DRIFT|%s|%s!=%s" % (name, got, expected[name]))
    hfact, mfact = live["hangar_camera"], live["mouth_camera"]
    if hfact["binding_guid"] != HANGAR_GUID or mfact["binding_guid"] != MOUTH_GUID:
        raise PlanError("ACTOR_BINDING_GUID_DRIFT")
    recorded_actor = evidence["hangar_actor"]
    for index, want in enumerate(recorded_actor["location_cm"]):
        if abs(float(hfact["location_cm"][index]) - float(want)) > params["location_tolerance_cm"]:
            raise PlanError("HANGAR_ACTOR_LOCATION_DRIFT|%d" % index)
    for name in ("pitch", "yaw", "roll"):
        if abs(float(hfact["rotation_deg"][name]) - float(recorded_actor["rotation_deg"][name])) > params["rotation_tolerance_deg"]:
            raise PlanError("HANGAR_ACTOR_ROTATION_DRIFT|%s" % name)


def coverage_for_pose(pose, drape, bounds, hfov_deg, aspect, edge_guard_cm):
    local = local_from_frame(drape, pose["loc"])
    distance = -float(local[0])
    tan_h = math.tan(math.radians(float(hfov_deg)) / 2.0)
    tan_v = tan_h / float(aspect)
    half_w, half_h = distance * tan_h, distance * tan_v
    margins = {
        "left": float(bounds["half_width_cm"]) - float(edge_guard_cm) - (abs(float(local[1])) + half_w),
        "right": float(bounds["half_width_cm"]) - float(edge_guard_cm) - (abs(float(local[1])) + half_w),
        "top": float(bounds["half_height_cm"]) - float(edge_guard_cm) - (abs(float(local[2])) + half_h),
        "bottom": float(bounds["half_height_cm"]) - float(edge_guard_cm) - (abs(float(local[2])) + half_h),
    }
    return {"camera_local_cm": local, "distance_to_plane_cm": distance,
            "footprint_half_cm": [half_w, half_h], "margins_cm": margins,
            "fills_frame": distance > 0.0 and min(margins.values()) >= -1.0e-6}


def _key_rows(frames, values):
    return [[int(frame), float(value)] for frame, value in zip(frames, values)]


def _transform_spec(name, keys, section_range, replace_from=None):
    channels = []
    defaults = {"Location.X": 0.0, "Location.Y": 0.0, "Location.Z": 0.0,
                "Rotation.X": 0.0, "Rotation.Y": 0.0, "Rotation.Z": 0.0,
                "Scale.X": 1.0, "Scale.Y": 1.0, "Scale.Z": 1.0}
    for channel_name in TRANSFORM_CHANNELS:
        channels.append({"name": channel_name, "default": defaults[channel_name],
                         "keys": copy.deepcopy(keys.get(channel_name, []))})
    return {"class": TRANSFORM_CLASS, "name": name, "property": "Transform", "path": "Transform",
            "range": list(section_range), "channels": channels, "replace_from": replace_from}


def _float_spec(name, prop, path, keys, section_range, replace_from=None):
    return {"class": FLOAT_CLASS, "name": name, "property": prop, "path": path,
            "range": list(section_range), "channels": [{"name": "None", "default": None, "keys": keys}],
            "replace_from": replace_from}


def pose_at(plan, side, frame):
    frame = int(frame)
    if side == "hangar":
        if frame <= plan["move_start"]:
            loc = plan["hangar"]["start_pose"]["loc"]
        elif frame >= CUT_FRAME - 1:
            loc = plan["hangar"]["close_pose"]["loc"]
        else:
            t = (frame - plan["move_start"]) / float((CUT_FRAME - 1) - plan["move_start"])
            loc = lerp3(plan["hangar"]["start_pose"]["loc"], plan["hangar"]["close_pose"]["loc"], ease_cubic_in_out(t))
        return {"loc": list(loc), "pitch": plan["hangar"]["start_pose"]["pitch"],
                "yaw": plan["hangar"]["start_pose"]["yaw"], "roll": plan["hangar"]["start_pose"]["roll"]}
    if frame <= CUT_FRAME or plan["mouth_after"] == "HOLD_CLOSE":
        return copy.deepcopy(plan["mouth"]["close_pose"])
    end = int(plan["mouth"]["ease_end_frame"])
    if frame >= end:
        return copy.deepcopy(plan["mouth"]["hold_pose"])
    t = (frame - CUT_FRAME) / float(end - CUT_FRAME)
    e = ease_cubic_out(t)
    close, hold = plan["mouth"]["close_pose"], plan["mouth"]["hold_pose"]
    return {"loc": lerp3(close["loc"], hold["loc"], e),
            "pitch": lerp(close["pitch"], hold["pitch"], e),
            "yaw": lerp(close["yaw"], hold["yaw"], e), "roll": lerp(close["roll"], hold["roll"], e)}


def build_plan(live, evidence, params):
    _assert_live_baseline(live, evidence, params)
    recorded = recorded_mouth_constant(evidence)
    hangar_fact, mouth_fact = live["hangar_camera"], live["mouth_camera"]
    hangar_drape, mouth_drape = evidence["hangar_drape"], evidence["mouth_drape"]
    hstart = {"loc": [float(value) for value in hangar_fact["location_cm"]],
              "pitch": float(hangar_fact["rotation_deg"]["pitch"]),
              "yaw": float(hangar_fact["rotation_deg"]["yaw"]),
              "roll": float(hangar_fact["rotation_deg"]["roll"])}
    hlocal = local_from_frame(hangar_drape, hstart["loc"])
    if hlocal[0] >= -1.0 or abs(hlocal[1]) > 5.0:
        raise PlanError("HANGAR_CAMERA_NOT_ON_DRAPE_AXIS|%s" % hlocal)
    hclose_local = [-params["close_distance_cm"], hlocal[1], hlocal[2]]
    hclose = dict(hstart, loc=world_from_frame(hangar_drape, hclose_local))
    mhold = {"loc": [recorded["transform"]["Location.X"], recorded["transform"]["Location.Y"],
                     recorded["transform"]["Location.Z"]],
             "pitch": recorded["transform"]["Rotation.Y"], "yaw": recorded["transform"]["Rotation.Z"],
             "roll": recorded["transform"]["Rotation.X"]}
    mclose_local = [-params["close_distance_cm"], hlocal[1], hlocal[2]]
    mclose = {"loc": world_from_frame(mouth_drape, mclose_local), "pitch": hclose["pitch"],
              "yaw": mouth_drape["yaw"], "roll": hclose["roll"]}
    hangar_focal = focal_for_hfov(hangar_fact["sensor_width_mm"], params["horizontal_fov_deg"])
    mouth_focal = focal_for_hfov(mouth_fact["sensor_width_mm"], params["horizontal_fov_deg"])
    if abs(hfov_for_focal(hangar_fact["sensor_width_mm"], hangar_focal) -
           hfov_for_focal(mouth_fact["sensor_width_mm"], mouth_focal)) > 1.0e-7:
        raise PlanError("CUT_HFOV_MISMATCH")
    ease_frames = int(round(params["ease_out_s"] * EXPECTED_FPS))
    ease_end = min(EXPECTED_PLAYBACK[1], CUT_FRAME + ease_frames)
    if params["mouth_after"] == "EASE_OUT" and ease_end <= CUT_FRAME:
        raise PlanError("EASE_OUT_FRAME_RANGE")
    plan = {
        "tool_version": TOOL_VERSION, "sequence": SEQ_PATH, "cut_frame": CUT_FRAME,
        "move_start": params["move_start"], "hangar_close_frame": CUT_FRAME - 1,
        "close_distance_cm": params["close_distance_cm"],
        "mouth_after": params["mouth_after"], "ease_out_s": params["ease_out_s"],
        "hfov_deg": params["horizontal_fov_deg"], "output_aspect": params["output_aspect"],
        "edge_guard_cm": params["edge_guard_cm"], "drape_bounds": evidence["drape_bounds"],
        "hangar_drape": hangar_drape, "mouth_drape": mouth_drape,
        "guids": {"hangar": HANGAR_GUID, "mouth": MOUTH_GUID, "mouth_component": MOUTH_COMPONENT_GUID},
        "hangar": {"start_pose": hstart, "close_pose": hclose, "sensor_width_mm": hangar_fact["sensor_width_mm"],
                   "sensor_height_mm": hangar_fact["sensor_height_mm"], "focal_mm": hangar_focal,
                   "start_focus_cm": -hlocal[0]},
        "mouth": {"close_pose": mclose, "hold_pose": mhold, "sensor_width_mm": mouth_fact["sensor_width_mm"],
                  "sensor_height_mm": mouth_fact["sensor_height_mm"], "focal_mm": mouth_focal,
                  "original_focal_mm": recorded["focal_mm"], "original_focus_cm": recorded["focus_cm"],
                  "ease_end_frame": ease_end},
    }
    coverage = {}
    for side, drape in (("hangar", hangar_drape), ("mouth", mouth_drape)):
        coverage[side] = {}
        for frame in PREVIEW_FRAMES:
            coverage[side][str(frame)] = coverage_for_pose(pose_at(plan, side, frame), drape,
                                                           evidence["drape_bounds"], plan["hfov_deg"],
                                                           plan["output_aspect"], plan["edge_guard_cm"])
    plan["coverage"] = coverage
    if not coverage["hangar"][str(CUT_FRAME)]["fills_frame"] or not coverage["mouth"][str(CUT_FRAME)]["fills_frame"]:
        raise PlanError("EDGE_IN_FRAME_AT_CUT|hangar=%s|mouth=%s" %
                        (coverage["hangar"][str(CUT_FRAME)]["margins_cm"],
                         coverage["mouth"][str(CUT_FRAME)]["margins_cm"]))
    hframes = list(range(params["move_start"], CUT_FRAME + 1))
    hposes = [pose_at(plan, "hangar", frame) for frame in hframes]
    hkeys = {}
    for index, name in enumerate(("Location.X", "Location.Y", "Location.Z")):
        values = [pose["loc"][index] for pose in hposes]
        hkeys[name] = [[0, hstart["loc"][index]]] + _key_rows(hframes, values)
    for name, value in (("Rotation.X", hstart["roll"]), ("Rotation.Y", hstart["pitch"]),
                        ("Rotation.Z", hstart["yaw"])):
        hkeys[name] = [[0, value], [CUT_FRAME, value]]
    htransform = _transform_spec(TRACK_NAME, hkeys, [0, CUT_FRAME + 1])
    hfocus = _key_rows(hframes, [-local_from_frame(hangar_drape, pose["loc"])[0] for pose in hposes])
    hfocus = [[0, -hlocal[0]]] + hfocus
    hfocal = [[0, hangar_focal], [CUT_FRAME, hangar_focal]]
    if params["mouth_after"] == "EASE_OUT":
        mframes = list(range(CUT_FRAME, ease_end + 1))
        if ease_end < EXPECTED_PLAYBACK[1]:
            mframes.append(EXPECTED_PLAYBACK[1])
    else:
        mframes = [CUT_FRAME, EXPECTED_PLAYBACK[1]]
    mposes = [pose_at(plan, "mouth", frame) for frame in mframes]
    mkeys = {}
    for index, name in enumerate(("Location.X", "Location.Y", "Location.Z")):
        mkeys[name] = _key_rows(mframes, [pose["loc"][index] for pose in mposes])
    for name, field in (("Rotation.X", "roll"), ("Rotation.Y", "pitch"), ("Rotation.Z", "yaw")):
        mkeys[name] = _key_rows(mframes, [pose[field] for pose in mposes])
    mtransform = _transform_spec(ORIGINAL_TRACK_NAME, mkeys, [0, EXPECTED_PLAYBACK[1] + 1], CUT_FRAME)
    mfocus = _key_rows(mframes, [-local_from_frame(mouth_drape, pose["loc"])[0] for pose in mposes])
    plan["writes"] = {
        "hangar_transform": htransform,
        "hangar_focal": _float_spec(TRACK_NAME, "CurrentFocalLength", "CurrentFocalLength", hfocal,
                                    [0, CUT_FRAME + 1]),
        "hangar_focus": _float_spec(TRACK_NAME, "ManualFocusDistance", "FocusSettings.ManualFocusDistance", hfocus,
                                    [0, CUT_FRAME + 1]),
        "mouth_transform": mtransform,
        "mouth_focal": _float_spec(ORIGINAL_TRACK_NAME, "CurrentFocalLength", "CurrentFocalLength",
                                   [[CUT_FRAME, mouth_focal], [EXPECTED_PLAYBACK[1], mouth_focal]],
                                   [0, EXPECTED_PLAYBACK[1] + 1], CUT_FRAME),
        "mouth_focus": _float_spec(ORIGINAL_TRACK_NAME, "ManualFocusDistance", "FocusSettings.ManualFocusDistance",
                                   mfocus, [0, EXPECTED_PLAYBACK[1] + 1], CUT_FRAME),
    }
    plan["cut_match"] = {
        "hangar_distance_cm": -local_from_frame(hangar_drape, hclose["loc"])[0],
        "mouth_distance_cm": -local_from_frame(mouth_drape, mclose["loc"])[0],
        "height_relative_cm": [local_from_frame(hangar_drape, hclose["loc"])[2],
                               local_from_frame(mouth_drape, mclose["loc"])[2]],
        "hfov_deg": [hfov_for_focal(hangar_fact["sensor_width_mm"], hangar_focal),
                     hfov_for_focal(mouth_fact["sensor_width_mm"], mouth_focal)],
        "focus_cm": [params["close_distance_cm"], params["close_distance_cm"]],
    }
    plan["digest"] = digest({key: value for key, value in plan.items() if key != "digest"})
    return plan


def _svg_escape(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_previews(plan, folder):
    os.makedirs(folder, exist_ok=True)
    plan_path = os.path.join(folder, "preview_plan.svg")
    cards_path = os.path.join(folder, "preview_coverage.svg")
    points = []
    for side, drape in (("hangar", plan["hangar_drape"]), ("mouth", plan["mouth_drape"])):
        frames = (list(range(plan["move_start"], CUT_FRAME + 1, 5)) if side == "hangar" else
                  list(range(CUT_FRAME, int(plan["mouth"]["ease_end_frame"]) + 1, 5)))
        if not frames:
            frames = [CUT_FRAME]
        points.append((side, [local_from_frame(drape, pose_at(plan, side, frame)["loc"]) for frame in frames]))
    def project(side, local):
        centre_y = 220.0 if side == "hangar" else 390.0
        return 820.0 + float(local[0]) * 0.28, centre_y - float(local[1]) * 0.12
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="560" viewBox="0 0 900 560">',
           '<rect width="900" height="560" fill="#101318"/>',
           '<text x="40" y="38" fill="#f1eadf" font-family="sans-serif" font-size="24">I2 sleight move-in — analytical plan view</text>',
           '<text x="40" y="62" fill="#aeb8c5" font-family="sans-serif" font-size="13">Not a scene render. Gary judges the later rendered slot.</text>']
    svg.append('<line x1="820" y1="125" x2="820" y2="465" stroke="#8c2635" stroke-width="12"/><text x="790" y="105" fill="#e8a5af" font-family="sans-serif" font-size="13">drape plane</text>')
    for side, rows in points:
        color = "#ef9d45" if side == "hangar" else "#5ab7d9"
        coords = " ".join("%.1f,%.1f" % project(side, row) for row in rows)
        svg.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="4"/>' % (coords, color))
        for label, loc in (("start", rows[0]), ("end", rows[-1])):
            x, y = project(side, loc)
            svg.append('<circle cx="%.1f" cy="%.1f" r="6" fill="%s"/><text x="%.1f" y="%.1f" fill="#f1eadf" font-family="sans-serif" font-size="12">%s %s</text>' %
                       (x, y, color, x + 9, y - 7, side, label))
        svg.append('<text x="75" y="%.1f" fill="%s" font-family="sans-serif" font-size="16">%s path in its drape-local plan</text>' %
                   ((185 if side == "hangar" else 355), color, side))
    svg.append('<text x="40" y="535" fill="#aeb8c5" font-family="monospace" font-size="13">move_start=%d  cut=%d  close=%.1f cm  mouth=%s  ease=%.2f s  HFOV=%.2f°</text>' %
               (plan["move_start"], CUT_FRAME, plan["close_distance_cm"], plan["mouth_after"], plan["ease_out_s"], plan["hfov_deg"]))
    svg.append('</svg>')
    with open(plan_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(svg) + "\n")
    card_w, card_h, gap = 280, 210, 15
    width, height = 3 * card_w + 4 * gap, 4 * card_h + 5 * gap
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (width, height, width, height),
           '<rect width="100%" height="100%" fill="#101318"/>']
    for index, frame in enumerate(PREVIEW_FRAMES):
        col, block = index % 3, index // 3
        for side_index, side in enumerate(("hangar", "mouth")):
            x = gap + col * (card_w + gap)
            y = gap + (block * 2 + side_index) * (card_h + gap)
            cov = plan["coverage"][side][str(frame)]
            fill = "#153d32" if cov["fills_frame"] else "#472626"
            svg.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="%s" stroke="#77818f"/>' %
                       (x, y, card_w, card_h, fill))
            svg.append('<text x="%d" y="%d" fill="#f1eadf" font-family="sans-serif" font-size="18">f%d — %s</text>' %
                       (x + 12, y + 25, frame, side))
            svg.append('<text x="%d" y="%d" fill="#d9e2ec" font-family="monospace" font-size="13">distance %.1f cm</text>' %
                       (x + 12, y + 50, cov["distance_to_plane_cm"]))
            margins = cov["margins_cm"]
            svg.append('<text x="%d" y="%d" fill="#d9e2ec" font-family="monospace" font-size="12">L/R %.1f  T/B %.1f cm</text>' %
                       (x + 12, y + 71, min(margins["left"], margins["right"]), min(margins["top"], margins["bottom"])))
            svg.append('<text x="%d" y="%d" fill="%s" font-family="sans-serif" font-size="15">%s</text>' %
                       (x + 12, y + 96, "#7ff0bd" if cov["fills_frame"] else "#ff9b91",
                        "DRAPE FILLS FRAME" if cov["fills_frame"] else "EDGE WOULD SHOW"))
            local = cov["camera_local_cm"]
            svg.append('<text x="%d" y="%d" fill="#aeb8c5" font-family="monospace" font-size="11">local [%.1f, %.1f, %.1f]</text>' %
                       (x + 12, y + 122, local[0], local[1], local[2]))
            note = "live" if (side == "hangar" and frame < CUT_FRAME) or (side == "mouth" and frame >= CUT_FRAME) else "comparison / not live"
            svg.append('<text x="%d" y="%d" fill="#aeb8c5" font-family="sans-serif" font-size="12">%s</text>' %
                       (x + 12, y + 147, _svg_escape(note)))
    svg.append('</svg>')
    with open(cards_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(svg) + "\n")
    return [plan_path, cards_path]


def _expected_track(before_track, spec):
    if spec.get("replace_from") is None:
        return {"class": spec["class"], "display_name": spec["name"], "property": spec["property"],
                "path": spec["path"], "sections": [{"range": spec["range"], "active": True,
                "completion": "PROJECT_DEFAULT", "channels": copy.deepcopy(spec["channels"])}]}
    out = copy.deepcopy(before_track)
    out["display_name"] = spec["name"]
    section = out["sections"][0]
    section["range"] = list(spec["range"])
    for sch in spec["channels"]:
        channel = _channel(out, sch["name"])
        keep = [row for row in channel.get("keys", []) if int(row[0]) < int(spec["replace_from"])]
        channel["keys"] = keep + copy.deepcopy(sch["keys"])
    return out


def expected_owned_tracks(before, plan):
    mouth = _binding(before, MOUTH_GUID)
    component = _binding(before, MOUTH_COMPONENT_GUID)
    return {
        "hangar_transform": _expected_track(None, plan["writes"]["hangar_transform"]),
        "hangar_focal": _expected_track(None, plan["writes"]["hangar_focal"]),
        "hangar_focus": _expected_track(None, plan["writes"]["hangar_focus"]),
        "mouth_transform": _expected_track(_track(mouth, TRANSFORM_CLASS, "Transform"), plan["writes"]["mouth_transform"]),
        "mouth_focal": _expected_track(_track(component, FLOAT_CLASS, "CurrentFocalLength"), plan["writes"]["mouth_focal"]),
        "mouth_focus": _expected_track(_track(component, FLOAT_CLASS, "ManualFocusDistance"), plan["writes"]["mouth_focus"]),
    }


def _value_tolerance(channel_name, params):
    if channel_name.startswith("Location") or "Focus" in channel_name or channel_name == "None":
        return params["location_tolerance_cm"]
    if channel_name.startswith("Rotation"):
        return params["rotation_tolerance_deg"]
    return params["lens_tolerance_mm"]


def compare_track(got, want, params, label):
    problems = []
    for key in ("class", "display_name", "property", "path"):
        if got.get(key) != want.get(key):
            problems.append("%s_%s|%s!=%s" % (label, key, got.get(key), want.get(key)))
    if len(got.get("sections", [])) != 1 or len(want.get("sections", [])) != 1:
        return problems + ["%s_SECTION_COUNT" % label]
    gs, ws = got["sections"][0], want["sections"][0]
    if gs.get("range") != ws.get("range"):
        problems.append("%s_RANGE|%s!=%s" % (label, gs.get("range"), ws.get("range")))
    for key in ("active", "completion"):
        if gs.get(key) != ws.get(key):
            problems.append("%s_SECTION_%s|%s!=%s" % (label, key, gs.get(key), ws.get(key)))
    if len(gs.get("channels", [])) != len(ws.get("channels", [])):
        problems.append("%s_CHANNEL_COUNT" % label)
        return problems
    for wc in ws["channels"]:
        rows = [row for row in gs["channels"] if row.get("name") == wc.get("name")]
        if len(rows) != 1:
            problems.append("%s_CHANNEL|%s|%d" % (label, wc.get("name"), len(rows)))
            continue
        gc = rows[0]
        if gc.get("default") != wc.get("default"):
            problems.append("%s_DEFAULT|%s|%s!=%s" % (label, wc.get("name"), gc.get("default"), wc.get("default")))
        gkeys, wkeys = gc.get("keys", []), wc.get("keys", [])
        if len(gkeys) != len(wkeys):
            problems.append("%s_KEY_COUNT|%s|%d!=%d" % (label, wc.get("name"), len(gkeys), len(wkeys)))
            continue
        tol = _value_tolerance(wc.get("name", ""), params)
        for index, (gkey, wkey) in enumerate(zip(gkeys, wkeys)):
            if int(gkey[0]) != int(wkey[0]) or abs(float(gkey[1]) - float(wkey[1])) > tol:
                problems.append("%s_KEY|%s|%d|%s!=%s" % (label, wc.get("name"), index, gkey, wkey))
    return problems


def validate_apply(before, after, plan, mutation, params):
    problems = []
    expected = expected_owned_tracks(before, plan)
    hangar = _binding(after, HANGAR_GUID)
    mouth = _binding(after, MOUTH_GUID)
    mouth_comp = _binding(after, MOUTH_COMPONENT_GUID)
    new_comp = _binding(after, mutation["hangar_component_guid"], HANGAR_COMPONENT_NAME)
    if new_comp.get("parent") != HANGAR_GUID:
        problems.append("HANGAR_COMPONENT_PARENT")
    problems += compare_track(_track(hangar, TRANSFORM_CLASS, "Transform"), expected["hangar_transform"], params, "HANGAR_TRANSFORM")
    problems += compare_track(_track(new_comp, FLOAT_CLASS, "CurrentFocalLength"), expected["hangar_focal"], params, "HANGAR_FOCAL")
    problems += compare_track(_track(new_comp, FLOAT_CLASS, "ManualFocusDistance"), expected["hangar_focus"], params, "HANGAR_FOCUS")
    problems += compare_track(_track(mouth, TRANSFORM_CLASS, "Transform"), expected["mouth_transform"], params, "MOUTH_TRANSFORM")
    problems += compare_track(_track(mouth_comp, FLOAT_CLASS, "CurrentFocalLength"), expected["mouth_focal"], params, "MOUTH_FOCAL")
    problems += compare_track(_track(mouth_comp, FLOAT_CLASS, "ManualFocusDistance"), expected["mouth_focus"], params, "MOUTH_FOCUS")
    normalized = copy.deepcopy(after)
    normalized["bindings"] = [row for row in normalized["bindings"] if row.get("guid") != mutation["hangar_component_guid"]]
    nh = _binding(normalized, HANGAR_GUID)
    nh["tracks"] = [row for row in nh["tracks"] if not (row.get("class") == TRANSFORM_CLASS and row.get("property") == "Transform")]
    for guid, cls, prop in ((MOUTH_GUID, TRANSFORM_CLASS, "Transform"),
                            (MOUTH_COMPONENT_GUID, FLOAT_CLASS, "CurrentFocalLength"),
                            (MOUTH_COMPONENT_GUID, FLOAT_CLASS, "ManualFocusDistance")):
        nb, bb = _binding(normalized, guid), _binding(before, guid)
        nb["tracks"] = [row for row in nb["tracks"] if not (row.get("class") == cls and row.get("property") == prop)]
        nb["tracks"].append(copy.deepcopy(_track(bb, cls, prop)))
        nb["tracks"].sort(key=lambda row: (row.get("class", ""), row.get("property", ""), row.get("display_name", "")))
    normalized["bindings"].sort(key=lambda row: (row.get("guid", ""), row.get("name", "")))
    if normalized != before:
        problems.append("UNOWNED_I2_CHANGED|before=%s|normalized_after=%s" % (digest(before), digest(normalized)))
    match = plan["cut_match"]
    for key in ("hangar_distance_cm", "mouth_distance_cm"):
        if abs(float(match[key]) - plan["close_distance_cm"]) > params["location_tolerance_cm"]:
            problems.append("CUT_DISTANCE|%s" % key)
    if abs(match["height_relative_cm"][0] - match["height_relative_cm"][1]) > params["location_tolerance_cm"]:
        problems.append("CUT_HEIGHT_MISMATCH")
    if abs(match["hfov_deg"][0] - match["hfov_deg"][1]) > 1.0e-4:
        problems.append("CUT_HFOV_MISMATCH")
    if match["focus_cm"] != [plan["close_distance_cm"], plan["close_distance_cm"]]:
        problems.append("CUT_FOCUS_MISMATCH")
    return problems


class UnrealBackend(object):
    """Thin UE 5.8 adapter.  The harness supplies a fake with this interface."""

    def __init__(self):
        import unreal  # noqa: WPS433 - deliberately local
        self.ue = unreal
        self.world = None
        self.seq = None

    def log(self, message):
        self.ue.log(message)

    def stop(self, message):
        self.ue.log_error(message)

    def _world_path(self, world):
        try:
            return str(world.get_outermost().get_name())
        except Exception:
            return str(world.get_path_name()).split(".")[0]

    def census(self):
        lib = self.ue.EditorLoadingAndSavingUtils
        return {"content": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_content_packages()),
                "maps": sorted(p.get_path_name().split(".")[0] for p in lib.get_dirty_map_packages())}

    def preflight(self, mode):
        editor = self.ue.get_editor_subsystem(self.ue.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            raise PlanError("PIE_OR_SIE_ACTIVE")
        self.world = editor.get_editor_world()
        if self.world is None or self._world_path(self.world) != MAP_PATH:
            raise PlanError("WRONG_WORLD|%s" % (self._world_path(self.world) if self.world else None))
        if self.ue.LevelSequenceEditorBlueprintLibrary.get_current_level_sequence() is not None:
            raise PlanError("SEQUENCER_IS_OPEN")
        if self.census() != {"content": [], "maps": []}:
            raise PlanError("DIRTY_CENSUS|%s" % self.census())
        self.seq = self.ue.load_asset(SEQ_PATH)
        if self.seq is None:
            raise PlanError("SEQUENCE_LOAD_FAILED")

    def _plain(self, value):
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if hasattr(value, "value"):
            return self._plain(value.value)
        return str(value)

    def _guid(self, value):
        return str(value).replace("-", "").upper()

    def _rate(self, value):
        return float(value.numerator) / float(value.denominator)

    def _section_range(self, section):
        start = int(section.get_start_frame()) if section.has_start_frame() else int(self.seq.get_playback_start())
        end = int(section.get_end_frame()) if section.has_end_frame() else int(self.seq.get_playback_end())
        return [start, end]

    def _track_row(self, track):
        prop = path = ""
        try:
            prop, path = str(track.get_property_name()), str(track.get_property_path())
        except Exception:
            pass
        sections = []
        for section in track.get_sections():
            channels = []
            for channel in section.get_all_channels():
                keys = []
                for key in channel.get_keys():
                    time = key.get_time(time_unit=self.ue.MovieSceneTimeUnit.DISPLAY_RATE)
                    keys.append([int(time.frame_number.value), self._plain(key.get_value())])
                default = None
                try:
                    if not hasattr(channel, "has_default") or channel.has_default():
                        default = self._plain(channel.get_default())
                except Exception:
                    pass
                channels.append({"name": str(getattr(channel, "channel_name", "")), "default": default, "keys": keys})
            completion = "PROJECT_DEFAULT"
            try:
                value = section.get_completion_mode()
                if hasattr(value, "name"):
                    completion = str(value.name)
                else:
                    text = str(value).strip("<>")
                    completion = text.split(".")[-1].split(":")[0].strip()
            except Exception:
                pass
            sections.append({"range": self._section_range(section), "active": bool(section.is_active()),
                             "completion": completion, "channels": channels})
        return {"class": track.get_class().get_name(), "display_name": str(track.get_display_name()),
                "property": prop, "path": path, "sections": sections}

    def snapshot(self):
        bindings = []
        for binding in self.seq.get_bindings():
            parent = binding.get_parent()
            tracks = [self._track_row(track) for track in binding.get_tracks()]
            tracks.sort(key=lambda row: (row["class"], row["property"], row["display_name"]))
            bindings.append({"guid": self._guid(binding.get_id()), "name": str(binding.get_display_name()),
                             "parent": self._guid(parent.get_id()) if parent is not None and parent.is_valid() else "",
                             "tracks": tracks})
        bindings.sort(key=lambda row: (row["guid"], row["name"]))
        cuts = []
        tracks = list(self.seq.find_tracks_by_type(self.ue.MovieSceneCameraCutTrack))
        for track_index, track in enumerate(tracks):
            for section_index, section in enumerate(track.get_sections()):
                bid = section.get_camera_binding_id().get_editor_property("guid")
                cuts.append({"track_index": track_index, "section_index": section_index,
                             "range": self._section_range(section), "active": bool(section.is_active()),
                             "binding_guid": self._guid(bid)})
        markers = sorted([[str(mark.get_editor_property("label")), int(mark.get_editor_property("frame_number").value)]
                          for mark in self.seq.get_marked_frames_from_sequence(self.ue.MovieSceneTimeUnit.DISPLAY_RATE)])
        roots = [self._track_row(track) for track in self.seq.get_tracks()
                 if track.get_class().get_name() != "MovieSceneCameraCutTrack"]
        roots.sort(key=lambda row: (row["class"], row["property"], row["display_name"]))
        return {"display_rate": self._rate(self.seq.get_display_rate()),
                "tick_resolution": self._rate(self.seq.get_tick_resolution()),
                "playback": [int(self.seq.get_playback_start()), int(self.seq.get_playback_end())],
                "bindings": bindings, "cuts": cuts, "markers": markers, "root_tracks": roots,
                "cut_track_count": len(tracks)}

    def _actors(self):
        return list(self.ue.get_editor_subsystem(self.ue.EditorActorSubsystem).get_all_level_actors())

    def _camera_component(self, actor):
        try:
            component = actor.get_cine_camera_component()
        except Exception:
            component = actor.get_component_by_class(self.ue.CineCameraComponent)
        if component is None:
            raise PlanError("CINE_CAMERA_COMPONENT_MISSING|%s" % actor.get_actor_label())
        return component

    def _binding_object_guid(self, obj):
        path = str(obj.get_path_name())
        bindings = [binding for binding in self.seq.get_bindings()
                    if any(str(bound.get_path_name()) == path
                           for bound in self.seq.locate_bound_objects(binding, self.world))]
        if len(bindings) > 1:
            raise PlanError("OBJECT_MULTIBOUND|%s|%d" % (path, len(bindings)))
        return self._guid(bindings[0].get_id()) if bindings else ""

    def _camera_fact(self, actor, expected_guid):
        component = self._camera_component(actor)
        filmback = component.get_editor_property("filmback")
        loc, rot = actor.get_actor_location(), actor.get_actor_rotation()
        guid = self._binding_object_guid(actor)
        if guid != expected_guid:
            raise PlanError("BOUND_OBJECT_GUID|%s|%s!=%s" % (actor.get_actor_label(), guid, expected_guid))
        return {"label": str(actor.get_actor_label()), "binding_guid": guid,
                "location_cm": [float(loc.x), float(loc.y), float(loc.z)],
                "rotation_deg": {"pitch": float(rot.pitch), "yaw": float(rot.yaw), "roll": float(rot.roll)},
                "sensor_width_mm": float(filmback.get_editor_property("sensor_width")),
                "sensor_height_mm": float(filmback.get_editor_property("sensor_height"))}

    def inspect(self):
        by_label = {}
        by_tag = []
        for actor in self._actors():
            by_label.setdefault(str(actor.get_actor_label()), []).append(actor)
            if HANGAR_TAG in [str(tag) for tag in (actor.get_editor_property("tags") or [])]:
                by_tag.append(actor)
        if len(by_tag) != 1 or len(by_label.get(MOUTH_NAME, [])) != 1:
            raise PlanError("CAMERA_ACTOR_COUNT|hangar=%d|mouth=%d" % (len(by_tag), len(by_label.get(MOUTH_NAME, []))))
        self._hangar_actor, self._mouth_actor = by_tag[0], by_label[MOUTH_NAME][0]
        self._hangar_component, self._mouth_component = self._camera_component(self._hangar_actor), self._camera_component(self._mouth_actor)
        if self._binding_object_guid(self._mouth_component) != MOUTH_COMPONENT_GUID:
            raise PlanError("MOUTH_COMPONENT_OBJECT_GUID")
        return {"snapshot": self.snapshot(),
                "hangar_camera": self._camera_fact(self._hangar_actor, HANGAR_GUID),
                "mouth_camera": self._camera_fact(self._mouth_actor, MOUTH_GUID)}

    def _binding_live(self, guid):
        rows = [binding for binding in self.seq.get_bindings() if self._guid(binding.get_id()) == guid]
        if len(rows) != 1:
            raise PlanError("LIVE_BINDING_COUNT|%s|%d" % (guid, len(rows)))
        return rows[0]

    def _track_live(self, binding, cls, prop):
        rows = []
        for track in binding.get_tracks():
            try:
                tprop = str(track.get_property_name())
            except Exception:
                tprop = ""
            if track.get_class().get_name() == cls and tprop == prop:
                rows.append(track)
        if len(rows) != 1:
            raise PlanError("LIVE_TRACK_COUNT|%s|%s|%d" % (binding.get_display_name(), prop, len(rows)))
        return rows[0]

    def _set_key_constant(self, key):
        if not hasattr(key, "set_interpolation_mode"):
            raise PlanError("KEY_INTERPOLATION_API_MISSING")
        key.set_interpolation_mode(self.ue.RichCurveInterpMode.RCIM_CONSTANT)

    def _write_spec(self, binding, spec, create):
        if create:
            track = binding.add_track(getattr(self.ue, spec["class"]))
            if track is None:
                raise PlanError("ADD_TRACK_FAILED|%s" % spec["property"])
            track.set_property_name_and_path(spec["property"], spec["path"])
            track.set_display_name(spec["name"])
            section = track.add_section()
            section.set_range(int(spec["range"][0]), int(spec["range"][1]))
        else:
            track = self._track_live(binding, spec["class"], spec["property"])
            sections = list(track.get_sections())
            if len(sections) != 1:
                raise PlanError("LIVE_SECTION_COUNT|%s" % spec["property"])
            section = sections[0]
            section.set_range(int(spec["range"][0]), int(spec["range"][1]))
        channels = {str(getattr(channel, "channel_name", "")): channel for channel in section.get_all_channels()}
        for row in spec["channels"]:
            channel = channels.get(row["name"])
            if channel is None:
                raise PlanError("LIVE_CHANNEL_MISSING|%s|%s" % (spec["property"], row["name"]))
            replace_from = spec.get("replace_from")
            if replace_from is None:
                for key in list(channel.get_keys()):
                    channel.remove_key(key)
                if row["default"] is not None:
                    channel.set_default(row["default"])
            else:
                preceding = []
                for key in list(channel.get_keys()):
                    time = key.get_time(time_unit=self.ue.MovieSceneTimeUnit.DISPLAY_RATE)
                    frame = int(time.frame_number.value)
                    if frame >= int(replace_from):
                        channel.remove_key(key)
                    else:
                        preceding.append((frame, key))
                if row["keys"] and preceding:
                    self._set_key_constant(sorted(preceding, key=lambda item: item[0])[-1][1])
            for frame, value in row["keys"]:
                channel.add_key(self.ue.FrameNumber(int(frame)), float(value),
                                time_unit=self.ue.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=self.ue.MovieSceneKeyInterpolation.LINEAR)
        return track

    def apply(self, plan):
        self.seq.modify()
        hangar = self._binding_live(HANGAR_GUID)
        mouth = self._binding_live(MOUTH_GUID)
        mouth_component = self._binding_live(MOUTH_COMPONENT_GUID)
        before_guids = {self._guid(binding.get_id()) for binding in self.seq.get_bindings()}
        child = self.seq.add_possessable(self._hangar_component)
        if child is None or not child.is_valid() or self._guid(child.get_id()) in before_guids:
            raise PlanError("HANGAR_COMPONENT_BINDING_NOT_NEW")
        child.set_parent(hangar)
        child.set_display_name(HANGAR_COMPONENT_NAME)
        self._write_spec(hangar, plan["writes"]["hangar_transform"], True)
        self._write_spec(child, plan["writes"]["hangar_focal"], True)
        self._write_spec(child, plan["writes"]["hangar_focus"], True)
        self._write_spec(mouth, plan["writes"]["mouth_transform"], False)
        self._write_spec(mouth_component, plan["writes"]["mouth_focal"], False)
        self._write_spec(mouth_component, plan["writes"]["mouth_focus"], False)
        return {"hangar_component_guid": self._guid(child.get_id())}

    def _restore_track(self, binding, original):
        track = self._track_live(binding, original["class"], original["property"])
        sections = list(track.get_sections())
        if len(sections) != 1:
            raise PlanError("RESTORE_SECTION_COUNT|%s" % original["property"])
        section, source = sections[0], original["sections"][0]
        section.set_range(int(source["range"][0]), int(source["range"][1]))
        channels = {str(getattr(channel, "channel_name", "")): channel for channel in section.get_all_channels()}
        for row in source["channels"]:
            channel = channels[row["name"]]
            for key in list(channel.get_keys()):
                channel.remove_key(key)
            if row.get("default") is not None:
                channel.set_default(row["default"])
            for frame, value in row.get("keys", []):
                channel.add_key(self.ue.FrameNumber(int(frame)), float(value),
                                time_unit=self.ue.MovieSceneTimeUnit.DISPLAY_RATE,
                                interpolation=self.ue.MovieSceneKeyInterpolation.LINEAR)

    def revert(self, record):
        self.seq.modify()
        hangar = self._binding_live(HANGAR_GUID)
        rows = [track for track in hangar.get_tracks()
                if track.get_class().get_name() == TRANSFORM_CLASS and str(track.get_property_name()) == "Transform"]
        if len(rows) != 1 or str(rows[0].get_display_name()) != TRACK_NAME:
            raise PlanError("REVERT_HANGAR_TRACK_IDENTITY")
        hangar.remove_track(rows[0])
        child = self._binding_live(record["mutation"]["hangar_component_guid"])
        if str(child.get_display_name()) != HANGAR_COMPONENT_NAME:
            raise PlanError("REFUSE_REMOVE_FOREIGN_CHILD")
        child.remove()
        before = record["snapshot_before"]
        for guid, cls, prop in ((MOUTH_GUID, TRANSFORM_CLASS, "Transform"),
                                (MOUTH_COMPONENT_GUID, FLOAT_CLASS, "CurrentFocalLength"),
                                (MOUTH_COMPONENT_GUID, FLOAT_CLASS, "ManualFocusDistance")):
            self._restore_track(self._binding_live(guid), _track(_binding(before, guid), cls, prop))

    def verify_evaluation(self, plan):
        """Assert count and pre-cut holds using display-rate ranges (rule 9)."""
        problems = []
        targets = ((MOUTH_GUID, TRANSFORM_CLASS, "Transform"),
                   (MOUTH_COMPONENT_GUID, FLOAT_CLASS, "CurrentFocalLength"),
                   (MOUTH_COMPONENT_GUID, FLOAT_CLASS, "ManualFocusDistance"))
        before_values = {}
        for guid, cls, prop in targets:
            track = self._track_live(self._binding_live(guid), cls, prop)
            section = list(track.get_sections())[0]
            rng = self.seq.make_range(0, CUT_FRAME)
            rate = self.seq.get_display_rate()
            for channel in section.get_all_channels():
                name = str(getattr(channel, "channel_name", ""))
                if name.startswith("Scale"):
                    continue
                values = list(channel.evaluate_keys(rng, rate))
                if len(values) != CUT_FRAME:
                    problems.append("EVALUATE_COUNT|%s|%s|%d" % (prop, name, len(values)))
                    continue
                if values and max(float(value) for value in values) - min(float(value) for value in values) > 1.0e-4:
                    problems.append("PRECUT_EVALUATION_CHANGED|%s|%s" % (prop, name))
                before_values["%s:%s" % (prop, name)] = float(values[0]) if values else None
        return problems

    def backup(self, run):
        project = os.path.abspath(self.ue.Paths.project_dir())
        source = os.path.join(project, "Content", *SEQ_PATH[len("/Game/"):].split("/")) + ".uasset"
        root = os.path.join(project, "Backups", "PreI2MoveIn-%s" % run)
        os.makedirs(root, exist_ok=False)
        target = os.path.join(root, os.path.basename(source))
        shutil.copy2(source, target)
        if os.path.getsize(source) != os.path.getsize(target) or sha256_file(source) != sha256_file(target):
            raise PlanError("BACKUP_VERIFY_FAILED")
        return {"root": root, "files": [{"package": SEQ_PATH, "source": source, "backup": target,
                                           "bytes": os.path.getsize(target), "sha256": sha256_file(target)}]}

    def save(self):
        expected = {"content": [SEQ_PATH], "maps": []}
        if self.census() != expected:
            raise PlanError("UNEXPECTED_DIRTY_PACKAGES|live=%s|expected=%s" % (self.census(), expected))
        if not bool(self.ue.EditorAssetLibrary.save_asset(SEQ_PATH, only_if_is_dirty=True)):
            raise PlanError("SAVE_FAILED|%s" % SEQ_PATH)
        if self.census() != {"content": [], "maps": []}:
            raise PlanError("DIRTY_AFTER_SAVE|%s" % self.census())
        self.seq = self.ue.load_asset(SEQ_PATH)
        return [SEQ_PATH]


def _tool_root(tool_root=None):
    return os.path.abspath(tool_root or os.path.dirname(__file__))


def _stop(backend, run, reason):
    message = "%s_STOPPED|run=%s|reason=%s" % (TOOL, run, reason)
    backend.stop(message)
    raise Stop(message)


def _report(live, evidence, params, run):
    plan = build_plan(live, evidence, params)
    inputs = {"snapshot": live["snapshot"], "hangar_camera": live["hangar_camera"],
              "mouth_camera": live["mouth_camera"], "evidence_sha256": evidence["sha256"], "params": params}
    return {"schema_version": 1, "tool_version": TOOL_VERSION, "run": run, "mode": "DRY",
            "sequence": SEQ_PATH, "params": params, "evidence": {"paths": evidence["paths"], "sha256": evidence["sha256"]},
            "plan": plan, "plan_digest": plan["digest"], "inputs_digest": digest(inputs),
            "snapshot_digest": digest(live["snapshot"]), "snapshot": live["snapshot"], "apply_ready": True,
            "claims": [
                {"tier": "declaration-proven", "claim": "Only LS_Interaction_02_Turnips may be saved.",
                 "cite": "Docs/Conductor/codex_briefs/p34_i2_sleight_move_in.md:34-43"},
                {"tier": "measured-upstream", "claim": "The named main-tree records provide the camera and drape baseline.",
                 "cite": "Docs/Conductor/codex_briefs/p34_i2_sleight_move_in.md:18-20"},
                {"tier": "inferred", "claim": "Analytical bounds predict whether a drape edge enters frame; rendered acceptance remains open.",
                 "cite": "Docs/Conductor/codex_briefs/p34_i2_sleight_move_in.md:31-32"},
            ]}


def run_dry(run, params, backend, root):
    backend.preflight("DRY")
    evidence = load_evidence(params)
    live = backend.inspect()
    report = _report(live, evidence, params, run)
    report_path = os.path.join(root, "i2_sleight_move_in_dry_%s.json" % run)
    previews = write_previews(report["plan"], root)
    report["previews"] = previews
    json_write(report_path, report)
    json_write(os.path.join(root, PLAN_FILE), {"run": run, "plan_digest": report["plan_digest"],
                                               "inputs_digest": report["inputs_digest"],
                                               "snapshot_digest": report["snapshot_digest"],
                                               "params": params, "report": report_path})
    if backend.census() != {"content": [], "maps": []}:
        _stop(backend, run, "DRY_DIRTIED|%s" % backend.census())
    backend.log("%s_DRY_OK|run=%s|mutated=0|cut=%d|move_start=%d|close_cm=%.3f|mouth_after=%s|plan=%s|previews=%s" %
                (TOOL, run, CUT_FRAME, report["plan"]["move_start"], report["plan"]["close_distance_cm"],
                 report["plan"]["mouth_after"], report_path, ",".join(previews)))
    return report


def run_apply(run, params, backend, root):
    backend.preflight("APPLY")
    record_path = os.path.join(root, RECORD)
    if os.path.exists(record_path):
        _stop(backend, run, "RECORD_EXISTS|REVERT first")
    evidence = load_evidence(params)
    live = backend.inspect()
    report = _report(live, evidence, params, run)
    dry = json_read(os.path.join(root, PLAN_FILE))
    if (dry.get("plan_digest") != report["plan_digest"] or dry.get("inputs_digest") != report["inputs_digest"] or
            dry.get("snapshot_digest") != report["snapshot_digest"]):
        _stop(backend, run, "I2_CHANGED_SINCE_DRY|rerun DRY")
    backup = backend.backup(run)
    record = {"schema_version": 1, "tool_version": TOOL_VERSION, "run": run, "applied": False,
              "sequence": SEQ_PATH, "params": params, "plan": report["plan"], "dry": dry, "backup": backup,
              "evidence": report["evidence"], "snapshot_before": live["snapshot"]}
    try:
        json_write(record_path, record, exclusive=True)
    except FileExistsError:
        _stop(backend, run, "RECORD_EXISTS|nothing mutated")
    try:
        mutation = backend.apply(report["plan"])
        record["mutation"] = mutation
        json_write(record_path, record)
        after = backend.inspect()["snapshot"]
        problems = validate_apply(live["snapshot"], after, report["plan"], mutation, params)
        problems += backend.verify_evaluation(report["plan"])
        if problems:
            _stop(backend, run, "PRESAVE_READBACK|%s|NOTHING SAVED; Don't-Save restart; backup=%s" %
                  (json.dumps(problems), backup["root"]))
        if backend.census() != {"content": [SEQ_PATH], "maps": []}:
            _stop(backend, run, "DIRTY_CENSUS_AFTER_APPLY|%s|NOTHING SAVED; Don't-Save restart" % backend.census())
        saves = backend.save()
        after2 = backend.inspect()["snapshot"]
        problems = validate_apply(live["snapshot"], after2, report["plan"], mutation, params)
        problems += backend.verify_evaluation(report["plan"])
        if after2 != after:
            problems.append("POSTSAVE_SNAPSHOT_DIFFERS")
        if problems or backend.census() != {"content": [], "maps": []}:
            _stop(backend, run, "POSTSAVE_READBACK|%s|restore=%s" % (json.dumps(problems), backup["root"]))
    except Stop:
        raise
    except Exception as error:
        _stop(backend, run, "MUTATION_ERROR|%s|NOTHING SAVED unless save marker already appeared; Don't-Save restart; backup=%s" %
              (error, backup["root"]))
    record.update({"applied": True, "mutation": mutation, "snapshot_after": after2,
                   "snapshot_after_digest": digest(after2), "saves": saves, "census_after": backend.census()})
    json_write(record_path, record)
    backend.log("%s_APPLY_OK|run=%s|cut=%d|move=[%d,%d]|close_cm=%.3f|mouth_after=%s|keys_read_back=all|saved=%s|backup=%s|record=%s" %
                (TOOL, run, CUT_FRAME, report["plan"]["move_start"], CUT_FRAME - 1,
                 report["plan"]["close_distance_cm"], report["plan"]["mouth_after"], ",".join(saves),
                 backup["root"], record_path))
    return record


def run_revert(run, params, backend, root):
    backend.preflight("REVERT")
    record_path = os.path.join(root, RECORD)
    record = json_read(record_path)
    if not record.get("applied") or record.get("sequence") != SEQ_PATH:
        _stop(backend, run, "REVERT_RECORD_CONTEXT")
    live = backend.inspect()["snapshot"]
    if live != record.get("snapshot_after"):
        _stop(backend, run, "STATE_DRIFTED_SINCE_APPLY|live=%s|recorded=%s" %
              (digest(live), record.get("snapshot_after_digest")))
    backup = backend.backup(run)
    txn = os.path.join(root, "i2_sleight_move_in_revert_%s.json" % run)
    json_write(txn, {"run": run, "completed": False, "backup": backup, "source_record": record_path,
                     "snapshot_before_revert": live}, exclusive=True)
    try:
        backend.revert(record)
        after = backend.inspect()["snapshot"]
        if after != record["snapshot_before"]:
            _stop(backend, run, "REVERT_PRESAVE_NOT_EXACT|live=%s|wanted=%s|NOTHING SAVED; Don't-Save restart" %
                  (digest(after), digest(record["snapshot_before"])))
        if backend.census() != {"content": [SEQ_PATH], "maps": []}:
            _stop(backend, run, "REVERT_DIRTY_CENSUS|%s|NOTHING SAVED; Don't-Save restart" % backend.census())
        saves = backend.save()
        after2 = backend.inspect()["snapshot"]
        if after2 != record["snapshot_before"] or backend.census() != {"content": [], "maps": []}:
            _stop(backend, run, "REVERT_POSTSAVE_NOT_EXACT|restore=%s" % backup["root"])
    except Stop:
        raise
    except Exception as error:
        _stop(backend, run, "REVERT_ERROR|%s|NOTHING SAVED unless save marker already appeared; Don't-Save restart" % error)
    archived = record_path + ".reverted-" + run
    os.rename(record_path, archived)
    json_write(txn, {"run": run, "completed": True, "backup": backup, "archived_record": archived,
                     "saves": saves, "census_after": backend.census()})
    backend.log("%s_REVERT_OK|run=%s|exact=1|saved=%s|backup=%s|record=%s" %
                (TOOL, run, ",".join(saves), backup["root"], archived))
    return {"archived_record": archived, "backup": backup, "saves": saves}


def main(args, backend=None, tool_root=None):
    args = dict(args or {})
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run_id") or datetime.datetime.now().strftime("I2MOVEIN-%Y%m%d-%H%M%S"))
    backend = backend or UnrealBackend()
    root = _tool_root(tool_root)
    try:
        if str(args.get("confirm", "")).strip() != CONFIRMS.get(mode):
            _stop(backend, run, "CONFIRM_MISMATCH|want=%r|got=%r" % (CONFIRMS.get(mode), args.get("confirm")))
        params = merged_params(args.get("params") or {})
        function = {"DRY": run_dry, "APPLY": run_apply, "REVERT": run_revert}.get(mode)
        if function is None:
            _stop(backend, run, "MODE|%s" % mode)
        return function(run, params, backend, root)
    except PlanError as error:
        _stop(backend, run, "PLAN_REFUSED|%s" % error)
