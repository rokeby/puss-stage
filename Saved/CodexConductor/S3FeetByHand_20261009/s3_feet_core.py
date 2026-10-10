"""Unreal-independent policy for the guarded S3 feet-by-hand workflow."""
from __future__ import annotations

import hashlib
import json
import math
import re

SCHEMA = "s3_feet_by_hand/1"
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


def is_target_label(label, include_variants=True):
    return label in FIXED_LABELS or (include_variants and label.startswith(VARIANT_PREFIX))


def binding_aliases(label):
    """Known asset display names, deliberately excluding body and float-hold bindings."""
    if label.startswith(VARIANT_PREFIX) or label == "Shore05_M53 Clam":
        return (label,)
    require(label in FIXED_LABELS, "UNKNOWN_TARGET_LABEL|" + label)
    return (label, label[:-4] + "Shore")


def validate_config(cfg):
    require(cfg.get("mode") in MODES, "MODE")
    require(isinstance(cfg.get("apply_xy"), bool), "APPLY_XY_BOOL")
    for key in ("max_delta_cm", "min_z_delta_cm", "rotation_tolerance_deg",
                "scale_tolerance", "readback_tolerance_cm"):
        require(isinstance(cfg.get(key), (int, float)) and not isinstance(cfg.get(key), bool),
                "CONFIG_NUMBER|" + key)
        require(float(cfg[key]) >= 0.0, "CONFIG_NONNEGATIVE|" + key)
    require(0.0 < float(cfg["max_delta_cm"]) <= 200.0, "MAX_DELTA_LIMIT")
    require(cfg.get("root_sequence") == ROOT_SEQUENCE, "ROOT_SEQUENCE")
    require(cfg.get("world") == WORLD, "WORLD")
    require(cfg.get("confirm", "") in ("", "APPLY S3 FEET", "REVERT S3 FEET"), "CONFIRM_VALUE")
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
    require(max(abs(x) for x in rot) <= float(cfg["rotation_tolerance_deg"]),
            "ROTATION_CHANGED|%s|%r" % (label, rot))
    require(max(abs(x) for x in scale) <= float(cfg["scale_tolerance"]),
            "SCALE_CHANGED|%s|%r" % (label, scale))
    require(abs(loc[2]) >= float(cfg["min_z_delta_cm"]),
            "Z_DELTA_REQUIRED|%s|%.6f" % (label, loc[2]))
    require(max(abs(x) for x in loc) <= float(cfg["max_delta_cm"]),
            "DELTA_AXIS_OVER_LIMIT|%s|%r" % (label, loc))
    require(math.sqrt(sum(x * x for x in loc)) <= float(cfg["max_delta_cm"]),
            "DELTA_VECTOR_OVER_LIMIT|%s|%r" % (label, loc))
    applied = list(loc) if cfg["apply_xy"] else [0.0, 0.0, loc[2]]
    return {"reported_location_delta_cm": loc, "applied_location_delta_cm": applied,
            "rotation_delta_deg": rot, "scale_delta": scale,
            "xy_policy": "apply" if cfg["apply_xy"] else "report_only"}


def validate_target_labels(labels, include_variants=True):
    require(len(labels) == len(set(labels)), "DUPLICATE_TARGET_LABEL")
    missing = sorted(set(FIXED_LABELS) - set(labels))
    extra = sorted(x for x in labels if not is_target_label(x, include_variants))
    require(not missing, "MISSING_FIXED_TARGETS|" + repr(missing))
    require(not extra, "UNEXPECTED_TARGETS|" + repr(extra))
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


def make_expected_binding(binding, applied_delta):
    out = json.loads(json.dumps(binding))
    for section in out["transform_sections"]:
        require(section.get("blend_type") in ("ABSOLUTE", "ADDITIVE"), "NON_ABSOLUTE_SECTION|" + repr(section.get("blend_type")))
        channels = section["channels"]
        for index, name in enumerate(LOCATION):
            channels[name] = shifted_channel(channels[name], applied_delta[index])
    if out["kind"] == "spawnable":
        require(out.get("template_transform") is not None, "SPAWNABLE_TEMPLATE_MISSING")
        for index in range(3):
            out["template_transform"]["location"][index] += float(applied_delta[index])
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

