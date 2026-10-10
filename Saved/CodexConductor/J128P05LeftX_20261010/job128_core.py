"""Pure planning/verification for Job 128. No Unreal dependency."""
from __future__ import annotations

import copy
import hashlib
import json
import math

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
COUNT = 93
MAGNITUDE_CM = 20.0
CHOSEN_SIGN = -1.0  # left is 20 cm toward camera/route -X relative to right


class GateError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise GateError(message)


def finite3(value, label):
    require(len(value) == 3 and all(math.isfinite(float(x)) for x in value), "NONFINITE_" + label)
    return [float(x) for x in value]


def target_left_x(right_x, sign=CHOSEN_SIGN, magnitude=MAGNITUDE_CM):
    right_x, sign, magnitude = float(right_x), float(sign), float(magnitude)
    require(all(math.isfinite(x) for x in (right_x, sign, magnitude)), "NONFINITE_TARGET")
    require(sign in (-1.0, 1.0), "SIGN_INVALID")
    require(abs(magnitude - MAGNITUDE_CM) < 1e-9, "MAGNITUDE_INVALID")
    return right_x + sign * magnitude


def add(a, b):
    return [float(a[i]) + float(b[i]) for i in range(3)]


def scale(v, s):
    return [float(x) * float(s) for x in v]


def dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def normalized(v, label="VECTOR"):
    v = finite3(v, label)
    n = math.sqrt(dot(v, v))
    require(n > 0.999 and n < 1.001, "UNIT_%s|norm=%.9f" % (label, n))
    return [x / n for x in v]


def pair_forward(left_inward, world_up=(0.0, 0.0, 1.0)):
    """Left inward is pair-local +Y. +Y cross +Z gives pair-local +X."""
    inward = normalized(left_inward, "LEFT_INWARD")
    forward = cross(inward, world_up)
    n = math.sqrt(dot(forward, forward))
    require(n > 0.999, "P05_PAIR_NOT_LEVEL")
    return [x / n for x in forward]


def shifted_box(box, delta):
    delta = finite3(delta, "DELTA")
    return {"min": add(box["min"], delta), "max": add(box["max"], delta)}


def aabb_gap(left, right):
    """Euclidean separation of two closed AABBs; zero means touching/overlap."""
    sep = []
    for i in range(3):
        a0, a1 = float(left["min"][i]), float(left["max"][i])
        b0, b1 = float(right["min"][i]), float(right["max"][i])
        require(a0 <= a1 and b0 <= b1, "BOX_INVERTED")
        sep.append(max(0.0, b0 - a1, a0 - b1))
    return math.sqrt(dot(sep, sep))


def transform_after(before, delta):
    result = copy.deepcopy(before)
    result["location"] = add(result["location"], delta)
    return result


def plan_row(row, sign=CHOSEN_SIGN):
    """Plan one row from live-authority values and materialized geometry."""
    required = {"cue_index", "cue_guid", "cue_label", "left_local", "right_local",
                "left_world_transform", "right_world_transform", "left_box", "right_box",
                "left_inward", "right_inward"}
    require(not (required - set(row)), "ROW_KEYS_MISSING")
    require(str(row["cue_label"]).startswith("P05 Wing "), "ROW_NOT_P05")
    left_in = normalized(row["left_inward"], "LEFT_INWARD")
    right_in = normalized(row["right_inward"], "RIGHT_INWARD")
    require(dot(left_in, right_in) < -0.999, "INWARD_NOT_OPPOSED")
    forward = pair_forward(left_in)
    old_lx = float(row["left_local"]["location"][0])
    right_x = float(row["right_local"]["location"][0])
    new_lx = target_left_x(right_x, sign)
    delta_x = new_lx - old_lx
    delta_world = scale(forward, delta_x)
    before_gap = aabb_gap(row["left_box"], row["right_box"])
    after_box = shifted_box(row["left_box"], delta_world)
    after_gap = aabb_gap(after_box, row["right_box"])
    return {
        "cue_index": int(row["cue_index"]), "cue_guid": str(row["cue_guid"]),
        "cue_label": str(row["cue_label"]), "sign": float(sign),
        "before_left_local_x_cm": old_lx, "right_local_x_cm": right_x,
        "after_left_local_x_cm": new_lx, "delta_local_x_cm": delta_x,
        "pair_forward_world": forward, "delta_world_cm": delta_world,
        "before_left_world_transform": copy.deepcopy(row["left_world_transform"]),
        "after_left_world_transform": transform_after(row["left_world_transform"], delta_world),
        "right_world_transform": copy.deepcopy(row["right_world_transform"]),
        "before_left_world_bounds": copy.deepcopy(row["left_box"]),
        "after_left_world_bounds": after_box,
        "right_world_bounds": copy.deepcopy(row["right_box"]),
        "gap_before_cm": before_gap, "gap_after_cm": after_gap,
    }


def plan_rows(rows, sign=CHOSEN_SIGN, expected_count=COUNT):
    require(len(rows) == expected_count, "P05_COUNT|expected=%d|actual=%d" % (expected_count, len(rows)))
    plans = [plan_row(row, sign) for row in rows]
    ids = [(r["cue_index"], r["cue_guid"]) for r in plans]
    require(len(set(ids)) == len(ids) and len({x[1] for x in ids}) == len(ids), "P05_IDENTITY_DUPLICATE")
    return {
        "sign": float(sign), "relation": "left_local_x = right_local_x %s 20 cm" % ("-" if sign < 0 else "+"),
        "rows": plans, "row_count": len(plans),
        "minimum_gap_before_cm": min(x["gap_before_cm"] for x in plans),
        "minimum_gap_after_cm": min(x["gap_after_cm"] for x in plans),
        "overlap_count_before": sum(x["gap_before_cm"] <= 1e-6 for x in plans),
        "overlap_count_after": sum(x["gap_after_cm"] <= 1e-6 for x in plans),
    }


def choose_sign(rows):
    minus, plus = plan_rows(rows, -1.0), plan_rows(rows, 1.0)
    # Recorded P05 cue 124 makes minus decisive. Current geometry can become
    # symmetric after later mesh swaps, so a live tie does not erase that sign
    # evidence; live geometry is the safety gate that -20 actually clears all.
    require(minus["overlap_count_after"] == 0, "CHOSEN_SIGN_STILL_OVERLAPS|count=%d" %
            minus["overlap_count_after"])
    require(minus["minimum_gap_after_cm"] > minus["minimum_gap_before_cm"] + 1e-4,
            "MIN_GAP_NOT_IMPROVED")
    return {"chosen": minus, "rejected": plus}


def stable_hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def confirm_token(plan):
    return stable_hash(plan)[:16]


def x_only_changed(before, after, tolerance=1e-6):
    check = copy.deepcopy(after)
    check["location"][0] = before["location"][0]
    return check == before and abs(float(after["location"][0]) - float(before["location"][0])) > tolerance


def untouched_refusals(before, after):
    """The explicit right-wing and other-passage acceptance boundary."""
    out = []
    if after.get("p05_right_sha256") != before.get("p05_right_sha256"):
        out.append("RIGHT_WINGS_CHANGED")
    if after.get("non_p05_show_sha256") != before.get("non_p05_show_sha256"):
        out.append("OTHER_PASSAGES_SHOW_CHANGED")
    if after.get("other_passage_refs_sha256") != before.get("other_passage_refs_sha256"):
        out.append("OTHER_PASSAGES_LEVEL_CHANGED")
    return out


def recorded_sign_evidence():
    """Measured 2 Oct probe values for the sign-discriminating P05 cue 124."""
    left = {"min": [1234.0, 319359.7, -100.0], "max": [1253.8, 320141.1, 420.0]}
    right = {"min": [1245.0, 320080.0, 100.0], "max": [1255.0, 320420.0, 300.0]}
    minus = aabb_gap(shifted_box(left, [-20.0, 0.0, 0.0]), right)
    plus = aabb_gap(shifted_box(left, [20.0, 0.0, 0.0]), right)
    return {"cue_index": 124, "before_cm": aabb_gap(left, right),
            "minus_20_cm": minus, "plus_20_cm": plus,
            "source": "Saved/CodexFlatV3/probe_c2_world_out.json"}
