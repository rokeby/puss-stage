"""Pure planning and validation helpers for P38.

This module deliberately imports no Unreal modules.  The offline harness and the
conductor-run editor tool use the same candidate ranking, wall selection,
seeded handprint planning, and key planning code.
"""
from __future__ import annotations

import hashlib
import json
import math
import random


SCHEMA = "p38_s3_grounding/1"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SCENE = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"


class P38Error(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def confirm_for(operation, mode):
    if mode == "DRY" or operation.endswith("_probe"):
        return "DRY P38 %s" % operation.upper()
    if mode == "APPLY":
        return "APPLY P38 %s" % operation.upper()
    if mode == "VERIFY":
        return "VERIFY P38 %s" % operation.upper()
    if mode == "REVERT":
        return "REVERT P38 %s" % operation.upper()
    raise P38Error("MODE|%s" % mode)


def require_confirm(operation, mode, supplied):
    expected = confirm_for(operation, mode)
    if supplied != expected:
        raise P38Error("CONFIRM_MISSING|%s" % expected)
    return True


def vadd(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def vsub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def vmul(a, s):
    return tuple(float(x) * float(s) for x in a)


def dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = length(a)
    if n <= 1.0e-9:
        raise P38Error("ZERO_VECTOR")
    return vmul(a, 1.0 / n)


def distance_point_aabb(point, centre, extent):
    total = 0.0
    for p, c, e in zip(point, centre, extent):
        d = max(abs(float(p) - float(c)) - float(e), 0.0)
        total += d * d
    return math.sqrt(total)


def select_camera_wall(camera_points, walls, max_distance_cm=250.0, min_margin_cm=100.0):
    """Select the wall followed by the camera path, without assuming a world axis.

    Each wall is {label, centre:[x,y,z], extent:[x,y,z]}.  The winner must be
    near every camera point and separated from the runner-up; ambiguity stops.
    """
    if len(camera_points) < 2:
        raise P38Error("CAMERA_POINTS_LT_2")
    if len(walls) < 2:
        raise P38Error("WALLS_LT_2")
    ranked = []
    for wall in walls:
        distances = [distance_point_aabb(p, wall["centre"], wall["extent"]) for p in camera_points]
        ranked.append({"label": wall["label"], "mean_distance_cm": sum(distances) / len(distances),
                       "max_distance_cm": max(distances), "distances_cm": distances, "wall": wall})
    ranked.sort(key=lambda r: (r["mean_distance_cm"], r["label"]))
    winner = ranked[0]
    margin = ranked[1]["mean_distance_cm"] - winner["mean_distance_cm"]
    if winner["max_distance_cm"] > max_distance_cm:
        raise P38Error("CAMERA_NOT_WALL_FOLLOWING|max=%.3f" % winner["max_distance_cm"])
    if margin < min_margin_cm:
        raise P38Error("CAMERA_WALL_AMBIGUOUS|margin=%.3f" % margin)
    return {"selected": winner["label"], "margin_cm": margin, "ranked": ranked,
            "method": "minimum camera-path distance to actor bounds; no UE axis assumption"}


def _draw(rng, lo, hi):
    """Exactly one RNG draw for one value."""
    u = rng.random()
    return float(lo) + (float(hi) - float(lo)) * u


def _pick(rng, rows):
    u = rng.random()
    return rows[min(len(rows) - 1, int(u * len(rows)))]


def plan_handprint_additions(rows, selected_wall, fraction=0.5, seed=3803,
                             tangent_jitter_cm=35.0, vertical_jitter_cm=24.0):
    if not (0.0 < fraction <= 2.0):
        raise P38Error("HANDPRINT_FRACTION")
    source = sorted((r for r in rows if r.get("wall_label") == selected_wall),
                    key=lambda r: r["label"])
    if not source:
        raise P38Error("HANDPRINT_SOURCE_EMPTY")
    target = int(math.ceil(len(source) * fraction))
    rng = random.Random(int(seed))
    planned = []
    for index in range(1, target + 1):
        src = _pick(rng, source)
        tangent = _draw(rng, -tangent_jitter_cm, tangent_jitter_cm)
        vertical = _draw(rng, -vertical_jitter_cm, vertical_jitter_cm)
        roll = _draw(rng, -9.0, 9.0)
        loc = vadd(src["location"], vadd(vmul(src["wall_tangent"], tangent), (0.0, 0.0, vertical)))
        planned.append({
            "index": index,
            "source_label": src["label"],
            "source_material": src["material"],
            "source_twin_label": src.get("twin_label"),
            "location": [round(x, 4) for x in loc],
            "rotation": [float(src["rotation"][0]), float(src["rotation"][1]),
                         float(src["rotation"][2]) + round(roll, 4)],
            "decal_size": list(src["decal_size"]),
            "scale": list(src.get("scale", [1.0, 1.0, 1.0])),
            "fade_screen_size": float(src.get("fade_screen_size", 0.0)),
            "sort_order": int(src.get("sort_order", 0)),
            "wall_label": selected_wall,
        })
    return {"source_count": len(source), "fraction": fraction, "target_additions": target,
            "seed": seed, "additions": planned, "plan_digest": digest(planned)}


def rank_ground_candidates(observation, thresholds=None):
    """Rank only what the probe observed; missing evidence remains UNCLEAR."""
    t = {"light_below_surface_cm": 2.0, "foot_gap_cm": 8.0, "high_bias": 1.0}
    t.update(thresholds or {})
    candidates = []

    dune = observation.get("dune") or {}
    flags = dune.get("shadow_flags") or {}
    if flags.get("cast_shadow") is False or flags.get("cast_dynamic_shadow") is False:
        candidates.append({"candidate": "dune_shadow_flags", "tier": "measured", "rank": 100,
                           "verdict": "PROVED", "reason": "a required dune shadow flag is false"})
    elif flags.get("cast_shadow") is True and flags.get("cast_dynamic_shadow") is True:
        candidates.append({"candidate": "dune_shadow_flags", "tier": "measured", "rank": 0,
                           "verdict": "REJECTED", "reason": "both required flags read true"})
    else:
        candidates.append({"candidate": "dune_shadow_flags", "tier": "unclear", "rank": 5,
                           "verdict": "UNCLEAR", "reason": "one or more flags were unreadable"})

    for light in observation.get("lights") or []:
        surface = light.get("surface_z_cm")
        z = (light.get("location") or [None, None, None])[2]
        surface_tier = light.get("surface_tier")
        if surface is None or z is None:
            verdict, rank, reason, tier = "UNCLEAR", 20, "surface or light Z unavailable", "unclear"
        else:
            clearance = float(z) - float(surface)
            light["clearance_cm"] = clearance
            if surface_tier != "measured":
                verdict, rank, reason, tier = "UNCLEAR", 30, "only a bounds estimate of dune surface is available", "inferred"
            elif clearance < -t["light_below_surface_cm"]:
                verdict, rank, reason, tier = "PROVED", 95, "light origin is below measured surface", "measured"
            elif clearance <= t["light_below_surface_cm"]:
                verdict, rank, reason, tier = "SUPPORTED", 70, "light origin is at/inside surface tolerance", "measured"
            else:
                verdict, rank, reason, tier = "REJECTED", 0, "light origin is above measured surface", "measured"
        candidates.append({"candidate": "light_origin:%s" % light.get("label", "?"), "tier": tier,
                           "rank": rank, "verdict": verdict, "reason": reason})

    mats = dune.get("materials") or []
    one_sided = [m for m in mats if m.get("two_sided") is False]
    normals = dune.get("normal_samples") or []
    downward = [n for n in normals if n.get("world_normal_z") is not None and n["world_normal_z"] < -0.25]
    if one_sided and downward:
        candidates.append({"candidate": "material_two_sided", "tier": "measured", "rank": 90,
                           "verdict": "PROVED", "reason": "one-sided material and downward sampled normals"})
    elif one_sided and not normals:
        candidates.append({"candidate": "material_two_sided", "tier": "inferred", "rank": 35,
                           "verdict": "UNCLEAR", "reason": "material is one-sided but mesh normals were unavailable"})
    else:
        candidates.append({"candidate": "material_two_sided", "tier": "measured" if mats else "unclear",
                           "rank": 0 if mats else 10, "verdict": "REJECTED" if mats else "UNCLEAR",
                           "reason": "no one-sided+downward-normal proof"})

    gaps = [f.get("foot_gap_cm") for f in observation.get("figures") or []
            if f.get("foot_gap_cm") is not None and f.get("sequence_evaluated") is True
            and f.get("surface_method") == "line_trace_dune"]
    if gaps and max(gaps) > t["foot_gap_cm"]:
        candidates.append({"candidate": "figure_feet", "tier": "measured", "rank": 75,
                           "verdict": "SUPPORTED", "reason": "one or more sampled foot gaps exceed tolerance",
                           "max_gap_cm": max(gaps)})
    else:
        candidates.append({"candidate": "figure_feet", "tier": "measured" if gaps else "unclear",
                           "rank": 0 if gaps else 15, "verdict": "REJECTED" if gaps else "UNCLEAR",
                           "reason": "foot gaps are within tolerance" if gaps else "no sequence-evaluated foot samples"})

    bias_rows = []
    for light in observation.get("lights") or []:
        bias = light.get("shadow_bias")
        slope = light.get("shadow_slope_bias")
        if bias is not None and float(bias) >= t["high_bias"]:
            bias_rows.append((light.get("label"), float(bias), slope))
    candidates.append({"candidate": "shadow_bias", "tier": "measured" if observation.get("lights") else "unclear",
                       "rank": 55 if bias_rows else 5, "verdict": "SUPPORTED" if bias_rows else "UNCLEAR",
                       "reason": "high bias observed" if bias_rows else "bias alone does not prove the rendered fault",
                       "lights": bias_rows})
    candidates.append({"candidate": "vsm_budget", "tier": "unclear", "rank": 10, "verdict": "UNCLEAR",
                       "reason": "read-only editor state cannot prove rendered VSM page exhaustion"})
    candidates.sort(key=lambda c: (-c["rank"], c["candidate"]))
    proved = [c for c in candidates if c["verdict"] == "PROVED"]
    overall = "PROVED:%s" % proved[0]["candidate"] if len(proved) == 1 else "UNCLEAR"
    return {"verdict": overall, "candidates": candidates}


def ground_fix_from_probe(probe, requested):
    ranking = probe.get("ranking") or rank_ground_candidates(probe)
    proved = [c["candidate"] for c in ranking["candidates"] if c["verdict"] == "PROVED"]
    aliases = {"light_z_lift": "light_origin", "material_two_sided_child": "material_two_sided",
               "shadow_bias": "shadow_bias"}
    prefix = aliases.get(requested)
    if prefix is None:
        raise P38Error("GROUND_FIX_KIND|%s" % requested)
    if not any(p == prefix or p.startswith(prefix + ":") for p in proved):
        raise P38Error("GROUND_FIX_NOT_PROVED|%s|proved=%s" % (requested, proved))
    return True


def lid_closed_plan(keys, closed_value=None):
    if len(keys) < 2:
        raise P38Error("LID_KEYS_LT_2")
    ordered = sorted((int(k[0]), float(k[1])) for k in keys)
    if len({k[0] for k in ordered}) != len(ordered):
        raise P38Error("LID_DUPLICATE_TIME")
    closed = ordered[-1][1] if closed_value is None else float(closed_value)
    return {"before": ordered, "after": [(t, closed) for t, _ in ordered], "closed_value": closed,
            "closed_source": "final key" if closed_value is None else "explicit arg"}


def spoiler_keys(playback_start, playback_end, cut_frame):
    a, b, c = int(playback_start), int(playback_end), int(cut_frame)
    if not (a < c < b):
        raise P38Error("SPOILER_CUT_RANGE")
    # House rule: on a bHidden-bound track, the bool channel is VISIBLE.
    return [(a, True), (c, False)]
