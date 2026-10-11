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
    move_seconds = _finite(args.get("move_seconds", 2.8), "move_seconds")
    push_cm = _finite(args.get("push_cm", 240.0), "push_cm")
    ease_fraction = _finite(args.get("ease_fraction", 0.35), "ease_fraction")
    volume_priority = _finite(args.get("volume_priority", 190.0), "volume_priority")
    void_mode = str(args.get("void_mode", "off")).strip().lower()
    if not 0.5 <= move_seconds <= 8.0:
        raise ValueError("move_seconds must be in [0.5, 8]")
    if not 10.0 <= push_cm <= 800.0:
        raise ValueError("push_cm must be in [10, 800]")
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
        "move_seconds": move_seconds,
        "push_cm": push_cm,
        "ease_fraction": ease_fraction,
        "volume_priority": volume_priority,
        "void_mode": void_mode,
        "record": str(args.get("record", "")),
    }


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
        "preset", "move_seconds", "push_cm", "ease_fraction", "volume_priority", "void_mode",
    )}
    return stable_digest({"args": visible, "score": rows})

