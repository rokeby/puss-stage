"""Pure planning helpers for Job 171.  This module deliberately has no Unreal import."""
import hashlib
import json
import re


TOOL = "JOB171_S3_HAIR_FIRE"
TOOL_VERSION = 1
FIGURES = (
    "Shore01_M56", "Shore02_F52", "Shore03_M59",
    "Shore04_F55", "Shore05_M53", "Shore06_F25",
)
FIRE_LABELS = ("S3 Ghost Light Flame", "S3 Fire A", "S3 Fire B", "S3 Fire C")
LIGHT_LABELS = ("S3 Ghost Light", "S3 Fire A Light", "S3 Fire B Light", "S3 Fire C Light")
PARTS = ("hair", "fires")


class PlanError(RuntimeError):
    pass


def selected_parts(value):
    out = list(value or PARTS)
    if not out or len(out) != len(set(out)) or any(x not in PARTS for x in out):
        raise PlanError("PARTS|%r" % out)
    return out


def figure_from_label(label):
    matches = re.findall(r"Shore0[1-6]_[MF]\d\d", str(label))
    if len(matches) != 1 or matches[0] not in FIGURES:
        raise PlanError("FIGURE_LABEL|%s" % label)
    return matches[0]


def target_kind(label):
    text = str(label)
    if re.match(r"^Shore0[1-6]_[MF]\d\d Clam$", text):
        return "shore"
    if re.match(r"^P40 Shore Variant 0[12] \(Shore0[1-6]_[MF]\d\d\)$", text):
        return "p40"
    if re.match(r"^S3 Crowd (0[1-9]|1[0-5]) \(from Shore0[1-6]_[MF]\d\d\)$", text):
        return "crowd"
    if text == "S3 Hangar Float Hold: Shore05_M53 Clam":
        return "hangar"
    return None


def validate_target_labels(labels):
    rows = []
    for label in sorted(labels):
        kind = target_kind(label)
        if kind:
            rows.append({"label": label, "kind": kind, "figure": figure_from_label(label)})
    counts = {kind: sum(row["kind"] == kind for row in rows) for kind in ("shore", "p40", "crowd", "hangar")}
    if len(rows) != 24 or counts != {"shore": 6, "p40": 2, "crowd": 15, "hangar": 1}:
        raise PlanError("TARGET_CENSUS|count=%d|counts=%s" % (len(rows), counts))
    return rows


def palette_for_label(label):
    # Stable across Python versions and runs; guarantees both palettes in any realistic cohort.
    return "grey" if hashlib.sha256(str(label).encode("utf-8")).digest()[0] & 1 else "dark_brown"


def style_for_label(label):
    # StraightBangs is the messier primary; every third actor gets the neater long silhouette.
    return "straight" if hashlib.sha256(("style|" + str(label)).encode("utf-8")).digest()[0] % 3 == 0 else "straight_bangs"


def variation_plan(rows):
    out = [dict(row, palette=palette_for_label(row["label"]), style=style_for_label(row["label"])) for row in rows]
    palettes = {row["palette"] for row in out}
    if palettes != {"dark_brown", "grey"}:
        raise PlanError("PALETTE_COVERAGE|%s" % sorted(palettes))
    styles = {row["style"] for row in out}
    if styles != {"straight", "straight_bangs"}:
        raise PlanError("STYLE_COVERAGE|%s" % sorted(styles))
    return out


def binding_path(figure, style="straight_bangs"):
    if figure not in FIGURES:
        raise PlanError("FIGURE|%s" % figure)
    names = {"straight": "Hair_L_Straight", "straight_bangs": "Hair_L_StraightBangs"}
    if style not in names:
        raise PlanError("STYLE|%s" % style)
    return "/Game/InfinityStage/Generated/Job171Hair/Bindings/%s_%s_Binding" % (names[style], figure)


def plan_fingerprint(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def numeric_diff(expected, actual, tolerance=1.0e-4, path="$"):
    out = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                out.append("%s.%s missing" % (path, key))
            else:
                out.extend(numeric_diff(expected[key], actual[key], tolerance, "%s.%s" % (path, key)))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            out.append("%s length %d != %d" % (path, len(expected), len(actual)))
        for index, (left, right) in enumerate(zip(expected, actual)):
            out.extend(numeric_diff(left, right, tolerance, "%s[%d]" % (path, index)))
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool) and isinstance(actual, (int, float)):
        if abs(float(expected) - float(actual)) > tolerance:
            out.append("%s %.9g != %.9g" % (path, expected, actual))
    elif expected != actual:
        out.append("%s %r != %r" % (path, expected, actual))
    return out

