"""Pure planning and validation for Job 190. No Unreal dependency."""

from __future__ import annotations

import hashlib
import json
import math
import re


PARAMETERS = (
    "Weird", "Invert", "HueDrift", "Solarize", "ChromaSplit", "Warp", "Mirror", "Phase",
)
UNIT_PARAMETERS = set(PARAMETERS) - {"Phase"}
PRESETS = ("gentle_to_invert", "gentle_to_liquid", "both")
MOVE_IN_MODES = ("off", "match_nested")
SOURCE_PRESET_NAMES = {
    "gentle_to_invert": "Gentle->Invert",
    "gentle_to_liquid": "Gentle->Liquid",
    "both": "Both",
}
PRESET_ALIASES = {
    "gentle->invert": "gentle_to_invert",
    "gentle_to_invert": "gentle_to_invert",
    "gentle->liquid": "gentle_to_liquid",
    "gentle_to_liquid": "gentle_to_liquid",
    "both": "both",
}
RUN_RE = re.compile(r"^J190-[A-Z0-9][A-Z0-9_-]{2,63}$")
CONFIRM = {
    "APPLY": "APPLY JOB190 S6 WARP PP",
    "REVERT": "REVERT JOB190 S6 WARP PP",
}
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
S6_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_06"
NESTED_SHOT_PATH = "/Game/InfinityStage/KlaraHookin/LS_Void_S6"
MPC_PATH = "/Game/InfinityStage/Effects/S6/MPC_S6Warp"
MATERIAL_PATH = "/Game/InfinityStage/Effects/S6/M_PP_S6Warp"
WORLD_PATH = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
KLARA_HOOKIN_PREFIX = "/Game/InfinityStage/KlaraHookin/"
ALLOWED_NAMED_SAVES = (
    MASTER_PATH,
    S6_PATH,
    MATERIAL_PATH,
    MPC_PATH,
    WORLD_PATH,
)
WARP_ONLY_NAMED_SAVES = (
    S6_PATH,
    MATERIAL_PATH,
    MPC_PATH,
    WORLD_PATH,
)
ALLOWED_MPC_KEY_SEQUENCES = (S6_PATH, MASTER_PATH)
ALLOWED_CAMERA_EDIT_TARGETS = (MASTER_PATH,)


def stable_digest(value):
    blob = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _finite(value, label):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("%s must be finite" % label)
    return number


def normalize_preset(value):
    key = str(value).strip().lower().replace(" ", "_")
    if key not in PRESET_ALIASES:
        raise ValueError("preset must be one of %r" % (PRESETS,))
    return PRESET_ALIASES[key]


def validate_args(raw):
    args = dict(raw)
    mode = str(args.get("mode", "DRY")).upper()
    run = str(args.get("run", "J190-DRY-001"))
    if mode not in ("DRY", "APPLY", "REVERT"):
        raise ValueError("mode must be DRY, APPLY, or REVERT")
    if not RUN_RE.match(run):
        raise ValueError("run must match %s" % RUN_RE.pattern)
    if mode in CONFIRM and args.get("confirm") != CONFIRM[mode]:
        raise ValueError("%s requires exact confirm %r" % (mode, CONFIRM[mode]))
    preset = normalize_preset(args.get("preset", "both"))
    move_in = str(args.get("move_in", "off")).strip().lower()
    if "push_cm" in args:
        raise ValueError("push_cm is obsolete; use move_in=off or move_in=match_nested")
    move_seconds = _finite(args.get("move_seconds", 2.8), "move_seconds")
    ease_fraction = _finite(args.get("ease_fraction", 0.35), "ease_fraction")
    volume_priority = _finite(args.get("volume_priority", 190.0), "volume_priority")
    void_mode = str(args.get("void_mode", "off")).strip().lower()
    if not 0.5 <= move_seconds <= 8.0:
        raise ValueError("move_seconds must be in [0.5, 8]")
    if move_in not in MOVE_IN_MODES:
        raise ValueError("move_in must be one of %r" % (MOVE_IN_MODES,))
    if not 0.1 <= ease_fraction <= 0.9:
        raise ValueError("ease_fraction must be in [0.1, 0.9]")
    if not 1.0 <= volume_priority <= 10000.0:
        raise ValueError("volume_priority must be in [1, 10000]")
    if void_mode not in ("off", "proposal"):
        raise ValueError("void_mode must be off or proposal")
    if mode == "REVERT" and not str(args.get("record", "")):
        raise ValueError("REVERT requires record")
    return {
        "mode": mode,
        "run": run,
        "preset": preset,
        "move_in": move_in,
        "move_seconds": move_seconds,
        "ease_fraction": ease_fraction,
        "volume_priority": volume_priority,
        "void_mode": void_mode,
        "record": str(args.get("record", "")),
    }


def expected_named_saves(move_in, current_master_path=MASTER_PATH):
    mode = str(move_in).strip().lower()
    if mode not in MOVE_IN_MODES:
        raise ValueError("move_in must be one of %r" % (MOVE_IN_MODES,))
    if mode == "off":
        return WARP_ONLY_NAMED_SAVES
    return (current_master_path,) + WARP_ONLY_NAMED_SAVES


def validate_named_saves(paths, require_apply_set=False, current_master_path=MASTER_PATH,
                         move_in="match_nested"):
    rows = tuple(str(path) for path in paths)
    if len(rows) != len(set(rows)):
        raise ValueError("named_saves contains duplicates")
    forbidden = [path for path in rows if path.startswith(KLARA_HOOKIN_PREFIX)]
    if forbidden:
        raise ValueError("named_saves must never include KlaraHookin: %r" % forbidden)
    allowed = (current_master_path,) + tuple(path for path in ALLOWED_NAMED_SAVES if path != MASTER_PATH)
    unknown = sorted(set(rows) - set(allowed))
    if unknown:
        raise ValueError("named_saves outside Job 194 allowlist: %r" % unknown)
    expected = expected_named_saves(move_in, current_master_path=current_master_path)
    if require_apply_set and set(rows) != set(expected):
        raise ValueError("APPLY named_saves must equal the move_in=%s allowlist" % move_in)
    return rows


def validate_mpc_key_sequence(sequence_path):
    path = str(sequence_path)
    if path not in ALLOWED_MPC_KEY_SEQUENCES:
        raise ValueError("MPC keys may exist only in LS_DevScene_06 or the Master, not %s" % path)
    return path


def validate_camera_edit_targets(paths, current_master_path=MASTER_PATH):
    rows = tuple(str(path) for path in paths)
    forbidden = [path for path in rows if path == NESTED_SHOT_PATH or path.startswith(KLARA_HOOKIN_PREFIX)]
    if forbidden:
        raise ValueError("nested-shot camera edits are forbidden: %r" % forbidden)
    unknown = sorted(set(rows) - {current_master_path})
    if unknown:
        raise ValueError("move-in camera edits must target only the P06/Master camera: %r" % unknown)
    return rows


def compile_score(score_document, preset):
    preset = normalize_preset(preset)
    if int(score_document.get("schema", 0)) != 1:
        raise ValueError("warp score schema must be 1")
    source_name = SOURCE_PRESET_NAMES[preset]
    source = score_document.get("presets", {}).get(source_name)
    if not isinstance(source, list) or len(source) < 2:
        raise ValueError("preset %r needs at least two rows" % source_name)
    state = {name: 0.0 for name in PARAMETERS}
    rows = []
    previous = -1.0
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            raise ValueError("score row %d must be an object" % index)
        unknown = sorted(set(item) - ({"time"} | set(PARAMETERS)))
        if unknown:
            raise ValueError("score row %d has unknown fields %r" % (index, unknown))
        second = _finite(item.get("time"), "row %d time" % index)
        if second <= previous:
            raise ValueError("score times must be strictly increasing")
        previous = second
        for name in PARAMETERS:
            if name in item:
                state[name] = _finite(item[name], "row %d %s" % (index, name))
            if name in UNIT_PARAMETERS and not 0.0 <= state[name] <= 1.0:
                raise ValueError("%s must stay in [0, 1]" % name)
        rows.append({"time": second, **state})
    if rows[0]["time"] != 0.0:
        raise ValueError("score must begin at time 0")
    return rows


def score_keys(rows, display_fps):
    fps = _finite(display_fps, "display_fps")
    if fps <= 0.0:
        raise ValueError("display_fps must be positive")
    result = {name: [] for name in PARAMETERS}
    for row in rows:
        frame = int(round(row["time"] * fps))
        for name in PARAMETERS:
            result[name].append([frame, float(row[name])])
    return result


def move_frames(end_tick, tick_rate, move_seconds, ease_fraction):
    end_tick = int(end_tick)
    rate = _finite(tick_rate, "tick_rate")
    span = int(round(_finite(move_seconds, "move_seconds") * rate))
    start = end_tick - span
    middle = start + int(round(span * _finite(ease_fraction, "ease_fraction")))
    if start < 0 or not start < middle < end_tick:
        raise ValueError("invalid camera move frame plan")
    return [start, middle, end_tick]


def move_to_target_keys(frames, start_pose, target_pose, middle_fraction=0.18):
    if len(frames) != 3 or not frames[0] < frames[1] < frames[2]:
        raise ValueError("move-to-target requires three increasing frames")
    fraction = _finite(middle_fraction, "middle_fraction")
    if not 0.0 < fraction < 1.0:
        raise ValueError("middle_fraction must be in (0, 1)")
    result = []
    for frame, alpha in zip(frames, (0.0, fraction, 1.0)):
        transform = {
            "location": [lerp(a, b, alpha) for a, b in
                         zip(start_pose["transform"]["location"], target_pose["transform"]["location"])],
            "rotation": [lerp(a, b, alpha) for a, b in
                         zip(start_pose["transform"]["rotation"], target_pose["transform"]["rotation"])],
            "scale": [lerp(a, b, alpha) for a, b in
                      zip(start_pose["transform"].get("scale", [1.0, 1.0, 1.0]),
                          target_pose["transform"].get("scale", [1.0, 1.0, 1.0]))],
        }
        result.append({
            "frame": int(frame),
            "fraction": alpha,
            "transform": transform,
            "focal_mm": lerp(start_pose["focal_mm"], target_pose["focal_mm"], alpha),
            "focus_cm": lerp(start_pose["focus_cm"], target_pose["focus_cm"], alpha),
        })
    return result


def path_distance_cm(keys):
    total = 0.0
    for left, right in zip(keys, keys[1:]):
        total += math.sqrt(sum((a - b) ** 2 for a, b in
                               zip(left["transform"]["location"], right["transform"]["location"])))
    return total


def lerp(a, b, alpha):
    return float(a) + (float(b) - float(a)) * float(alpha)


def evaluate_score(rows, second):
    second = float(second)
    if second <= rows[0]["time"]:
        return dict(rows[0])
    if second >= rows[-1]["time"]:
        return dict(rows[-1])
    for left, right in zip(rows, rows[1:]):
        if left["time"] <= second <= right["time"]:
            alpha = (second - left["time"]) / (right["time"] - left["time"])
            return {"time": second, **{name: lerp(left[name], right[name], alpha) for name in PARAMETERS}}
    raise AssertionError("unreachable")


def plan_digest(args, rows):
    visible = {key: args[key] for key in (
        "preset", "move_in", "move_seconds", "ease_fraction", "volume_priority", "void_mode",
    )}
    return stable_digest({
        "args": visible,
        "score": rows,
        "ownership_policy": "job194_no_klarahookin_save_or_camera_edit_v1",
    })

