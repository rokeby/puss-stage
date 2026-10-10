"""Unreal-independent policy for the guarded S3 feet-by-hand workflow."""
from __future__ import annotations

import hashlib
import json
import math
import re

SCHEMA = "s3_feet_by_hand/2"
CAPTURE_COMPATIBLE_SNAPSHOT_SCHEMAS = ("s3_feet_by_hand/1", SCHEMA)
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
ROOT_SEQUENCE = "/Game/Scenes/LS_Clams"
FIXED_LABELS = tuple("Shore%02d_%s Clam" % item for item in (
    (1, "M56"), (2, "F52"), (3, "M59"),
    (4, "F55"), (5, "M53"), (6, "F25"),
))
VARIANT_PREFIX = "P40 Shore Variant "
LOCATION = ("Location.X", "Location.Y", "Location.Z")
ROTATION = ("Rotation.X", "Rotation.Y", "Rotation.Z")
SCALE = ("Scale.X", "Scale.Y", "Scale.Z")
TRANSFORM_CHANNELS = LOCATION + ROTATION + SCALE
MODES = ("DRY", "SNAPSHOT", "CAPTURE", "APPLY", "REVERT")


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def stable_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def channel_base(raw):
    """Strip UE proxy suffixes such as Location.Z_183 without guessing by index."""
    text = str(raw).split(" (", 1)[0]
    return re.sub(r"_\d+$", "", text)


CROWD_PREFIX = "S3 Crowd "  # 10 Oct: Gary moved crowd copies too; admitted only when named in extra_target_labels

def is_target_label(label, include_variants=True, extra=()):
    return label in FIXED_LABELS or (include_variants and label.startswith(VARIANT_PREFIX)) or label in tuple(extra)


def binding_aliases(label):
    """Known asset display names, deliberately excluding body and float-hold bindings."""
    if label.startswith(VARIANT_PREFIX) or label.startswith(CROWD_PREFIX) or label == "Shore05_M53 Clam":
        return (label,)
    require(label in FIXED_LABELS, "UNKNOWN_TARGET_LABEL|" + label)
    return (label, label[:-4] + "Shore")


def validate_config(cfg):
    require(cfg.get("mode") in MODES, "MODE")
    require(isinstance(cfg.get("apply_xy"), bool), "APPLY_XY_BOOL")
    require(isinstance(cfg.get("allow_yaw", False), bool), "ALLOW_YAW_BOOL")
    cfg.setdefault("allow_yaw", False)
    cfg.setdefault("readback_tolerance_deg", 0.001)
    for key in ("max_delta_cm", "min_z_delta_cm", "rotation_tolerance_deg",
                "scale_tolerance", "readback_tolerance_cm", "readback_tolerance_deg"):
        require(isinstance(cfg.get(key), (int, float)) and not isinstance(cfg.get(key), bool),
                "CONFIG_NUMBER|" + key)
        require(float(cfg[key]) >= 0.0, "CONFIG_NONNEGATIVE|" + key)
    require(0.0 < float(cfg["max_delta_cm"]) <= 200.0, "MAX_DELTA_LIMIT")
    require(cfg.get("root_sequence") == ROOT_SEQUENCE, "ROOT_SEQUENCE")
    require(cfg.get("world") == WORLD, "WORLD")
    require(cfg.get("confirm", "") in ("", "APPLY S3 FEET", "REVERT S3 FEET"), "CONFIRM_VALUE")
    extra = cfg.setdefault("extra_target_labels", [])
    require(isinstance(extra, list) and all(isinstance(x, str) and x.startswith(CROWD_PREFIX) for x in extra), "EXTRA_TARGET_LABELS")
    return cfg


def vector_delta(before, after):
    require(len(before) == len(after) == 3, "VECTOR_LENGTH")
    return [float(after[i]) - float(before[i]) for i in range(3)]


def wrapped_degrees_delta(before, after):
    raw = float(after) - float(before)
    return (raw + 180.0) % 360.0 - 180.0


def capture_delta(before, after, cfg, label):
    loc = vector_delta(before["location"], after["location"])
    rot = [wrapped_degrees_delta(before["rotation"][i], after["rotation"][i]) for i in range(3)]
    scale = vector_delta(before["scale"], after["scale"])
    tolerance = float(cfg["rotation_tolerance_deg"])
    require(max(abs(rot[0]), abs(rot[1])) <= tolerance,
            "ROLL_PITCH_CHANGED|%s|%r" % (label, rot[:2]))
    if abs(rot[2]) > tolerance:
        require(cfg["allow_yaw"], "YAW_CHANGED_WITHOUT_ALLOW_YAW|%s|%.6f" % (label, rot[2]))
    require(max(abs(x) for x in scale) <= float(cfg["scale_tolerance"]),
            "SCALE_CHANGED|%s|%r" % (label, scale))
    # 10 Oct: Gary moved only some figures; an UNMOVED target is a zero, no-op row (not a refusal).
    yaw_delta = rot[2] if abs(rot[2]) > tolerance else 0.0
    if max(abs(x) for x in loc) < float(cfg["min_z_delta_cm"]) and yaw_delta == 0.0:
        return {"reported_location_delta_cm": loc,
                "applied_location_delta_cm": [0.0, 0.0, 0.0],
                "reported_rotation_delta_deg": rot, "applied_yaw_delta_deg": 0.0,
                "unmoved": True}
    require(abs(loc[2]) >= float(cfg["min_z_delta_cm"]) or cfg["apply_xy"] or yaw_delta != 0.0,
            "Z_DELTA_REQUIRED|%s|%.6f" % (label, loc[2]))
    require(max(abs(x) for x in loc) <= float(cfg["max_delta_cm"]),
            "DELTA_AXIS_OVER_LIMIT|%s|%r" % (label, loc))
    require(math.sqrt(sum(x * x for x in loc)) <= float(cfg["max_delta_cm"]),
            "DELTA_VECTOR_OVER_LIMIT|%s|%r" % (label, loc))
    applied = list(loc) if cfg["apply_xy"] else [0.0, 0.0, loc[2]]
    return {"reported_location_delta_cm": loc, "applied_location_delta_cm": applied,
            "reported_rotation_delta_deg": rot, "applied_yaw_delta_deg": yaw_delta,
            "scale_delta": scale,
            "xy_policy": "apply" if cfg["apply_xy"] else "report_only"}


def validate_target_labels(labels, include_variants=True, extra=()):
    require(len(labels) == len(set(labels)), "DUPLICATE_TARGET_LABEL")
    missing = sorted(set(FIXED_LABELS) - set(labels))
    extra_found = sorted(x for x in labels if not is_target_label(x, include_variants, extra))
    require(not missing, "MISSING_FIXED_TARGETS|" + repr(missing))
    require(not extra_found, "UNEXPECTED_TARGETS|" + repr(extra_found))
    require(set(extra) <= set(labels), "EXTRA_TARGET_NOT_FOUND|" + repr(sorted(set(extra) - set(labels))))
    return sorted(labels)


def shifted_channel(state, delta):
    """Offset every key, or the default only when the channel has no keys."""
    out = json.loads(json.dumps(state))
    keys = out.get("keys", [])
    if keys:
        for row in keys:
            row["value"] = float(row["value"]) + float(delta)
    else:
        require(out.get("has_default") is True, "UNKEYED_CHANNEL_WITHOUT_DEFAULT")
        out["default"] = float(out["default"]) + float(delta)
    return out


def rotate_xy(x, y, yaw_delta_deg):
    """Rotate one additive XY offset about its zero/pivot by a UE yaw delta."""
    radians = math.radians(float(yaw_delta_deg))
    cosine, sine = math.cos(radians), math.sin(radians)
    return [cosine * float(x) - sine * float(y),
            sine * float(x) + cosine * float(y)]


def rotated_xy_channels(x_state, y_state, yaw_delta_deg):
    """Rotate paired additive XY keys/defaults without changing channel topology."""
    x_out = json.loads(json.dumps(x_state))
    y_out = json.loads(json.dumps(y_state))
    x_keys, y_keys = x_out.get("keys", []), y_out.get("keys", [])
    require(bool(x_keys) == bool(y_keys), "XY_KEY_TOPOLOGY_MISMATCH")
    if x_keys:
        require(len(x_keys) == len(y_keys), "XY_KEY_COUNT_MISMATCH")
        require([row["frame"] for row in x_keys] == [row["frame"] for row in y_keys],
                "XY_KEY_FRAME_MISMATCH")
        for x_row, y_row in zip(x_keys, y_keys):
            x_row["value"], y_row["value"] = rotate_xy(
                x_row["value"], y_row["value"], yaw_delta_deg)
    else:
        require(x_out.get("has_default") is True and y_out.get("has_default") is True,
                "XY_UNKEYED_WITHOUT_DEFAULT")
        x_out["default"], y_out["default"] = rotate_xy(
            x_out["default"], y_out["default"], yaw_delta_deg)
    return x_out, y_out


def evaluated_additive_world_position(base_location, additive_location):
    """Offline model used by the harness and explicitly gated by the live A/B probe."""
    require(len(base_location) == len(additive_location) == 3, "VECTOR_LENGTH")
    return [float(base_location[i]) + float(additive_location[i]) for i in range(3)]


def make_expected_binding(binding, applied_delta, yaw_delta_deg=0.0):
    out = json.loads(json.dumps(binding))
    for section in out["transform_sections"]:
        require(section.get("blend_type") in ("ABSOLUTE", "ADDITIVE"), "NON_ABSOLUTE_SECTION|" + repr(section.get("blend_type")))
        channels = section["channels"]
        if abs(float(yaw_delta_deg)) > 0.0:
            require(section.get("blend_type") == "ADDITIVE",
                    "YAW_REQUIRES_ADDITIVE_SECTION|" + repr(section.get("blend_type")))
            channels[LOCATION[0]], channels[LOCATION[1]] = rotated_xy_channels(
                channels[LOCATION[0]], channels[LOCATION[1]], yaw_delta_deg)
            channels[ROTATION[2]] = shifted_channel(channels[ROTATION[2]], yaw_delta_deg)
        for index, name in enumerate(LOCATION):
            channels[name] = shifted_channel(channels[name], applied_delta[index])
    if out["kind"] == "spawnable":
        require(out.get("template_transform") is not None, "SPAWNABLE_TEMPLATE_MISSING")
        for index in range(3):
            out["template_transform"]["location"][index] += float(applied_delta[index])
        out["template_transform"]["rotation"][2] += float(yaw_delta_deg)
    return out


def structural_binding(binding):
    """State used to refuse drift while allowing value changes during APPLY/REVERT."""
    return {
        "sequence_path": binding["sequence_path"],
        "binding_guid": binding["binding_guid"],
        "binding_display_name": binding["binding_display_name"],
        "kind": binding["kind"],
        "sections": [{"track_index": s["track_index"], "section_index": s["section_index"],
                      "track_name": s["track_name"], "section_name": s["section_name"],
                      "blend_type": s["blend_type"],
                      "channel_names": sorted(s["channels"]),
                      "key_frames": {n: [k["frame"] for k in s["channels"][n]["keys"]]
                                     for n in sorted(s["channels"])} }
                     for s in binding["transform_sections"]],
    }


def near(a, b, tolerance):
    return abs(float(a) - float(b)) <= float(tolerance)


def transform_near(a, b, loc_tol=1.0e-4, rot_tol=1.0e-4, scale_tol=1.0e-6):
    return (all(near(a["location"][i], b["location"][i], loc_tol) for i in range(3)) and
            all(abs(wrapped_degrees_delta(a["rotation"][i], b["rotation"][i])) <= rot_tol for i in range(3)) and
            all(near(a["scale"][i], b["scale"][i], scale_tol) for i in range(3)))

