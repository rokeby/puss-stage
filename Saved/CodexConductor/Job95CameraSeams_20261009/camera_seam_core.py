"""Pure maths and validation shared by the Job 95 Unreal tool and offline harness."""

import math
import re


RUN_RE = re.compile(r"^J95-[A-Z0-9][A-Z0-9_-]{2,63}$")
MODES = ("DRY", "APPLY", "REVERT")
CONFIRMS = {mode: "CONFIRM_JOB95_%s" % mode for mode in MODES}


def validate_args(args):
    mode = str(args.get("mode", "")).upper()
    run = str(args.get("run", ""))
    if mode not in MODES:
        raise ValueError("mode must be DRY, APPLY, or REVERT")
    if not RUN_RE.match(run):
        raise ValueError("run must match %s" % RUN_RE.pattern)
    if args.get("confirm") != CONFIRMS[mode]:
        raise ValueError("confirm must be %s" % CONFIRMS[mode])
    settle = float(args.get("settle_seconds", 3.0))
    if not math.isfinite(settle) or settle < 1.0 or settle > 5.0:
        raise ValueError("settle_seconds must be finite and in [1, 5]")
    if mode == "REVERT" and not str(args.get("record", "")):
        raise ValueError("REVERT requires record")
    return mode, run, settle


def quat_angle_deg(a, b):
    dot = abs(sum(float(x) * float(y) for x, y in zip(a, b)))
    return math.degrees(2.0 * math.acos(max(-1.0, min(1.0, dot))))


def distance_cm(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def seam_delta(passage, entry):
    return {
        "position_cm": distance_cm(passage["location"], entry["location"]),
        "rotation_deg": quat_angle_deg(passage["quaternion"], entry["quaternion"]),
        "focal_mm": abs(float(passage["focal_mm"]) - float(entry["focal_mm"])),
        "focus_cm": abs(float(passage["focus_cm"]) - float(entry["focus_cm"])),
    }


def seam_is_matched(delta, limits=None):
    limits = limits or {"position_cm": 0.5, "rotation_deg": 0.05, "focal_mm": 0.01, "focus_cm": 0.1}
    return all(float(delta[name]) <= float(limit) for name, limit in limits.items())


def exact_census(rows):
    numbers = sorted(int(row["number"]) for row in rows)
    if numbers != list(range(1, 7)):
        raise ValueError("expected exact Scene census [1..6], got %r" % numbers)
    if len({row["rig_path"] for row in rows}) != 6:
        raise ValueError("expected six distinct Passage rigs")
    if len({row["entry_path"] for row in rows}) != 6:
        raise ValueError("expected six distinct Scene Entry cameras")
    return {
        "passage_scene_seams": 6,
        "passage_rigs": 6,
        "scene_entry_cameras": 6,
        "matched": sum(bool(row["matched"]) for row in rows),
        "stale": sum(not bool(row["matched"]) for row in rows),
    }


def weighted_look(pitch, yaw, settle_weight):
    weight = max(0.0, min(1.0, float(settle_weight)))
    return float(pitch) * weight, float(yaw) * weight

