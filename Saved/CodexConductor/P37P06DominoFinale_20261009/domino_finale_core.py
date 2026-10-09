"""Pure planning and record-scope rules for the P06 domino finale.

No Unreal import belongs in this module.  The production planner and the offline
harness both use these functions.  Mechanism curve text is delegated to the
checked-in Flat V3 topple core, but selection, timing, chain identity, dust,
sound, and cross-chain guards live here.

Evidence labels used in reports:
  declaration-proven: this source or a checked-in declaration states it.
  measured: an offline operation was run and its output read back.
  inferred: a creative or physical conclusion still needing Unreal/render review.
"""
from __future__ import annotations

import hashlib
import json
import copy
import math
import random
from pathlib import Path


CHAIN_A = "A"
CHAIN_B = "B"
CHAIN_A_RESTYLE = "A_RESTYLE"
SIDES = ("L", "R")
MODES = ("DRY", "APPLY", "REVERT")
CHAIN_MODES = ("contact", "choreographed")
MAX_THICKNESS_CM = 50.0
MIN_HEIGHT_CM = 300.0
MAX_AXIS_DOT = 0.1
MIN_LATERAL_OVERLAP_CM = 100.0
MAX_BOUNCE_DEG = 3.0
MIN_CHAIN_ROWS = 2


class PlanError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise PlanError(message)


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


def confirm_for(mode, chain_id, token=None, apply_run=None):
    mode = str(mode).upper()
    if mode == "DRY":
        return "DRY P06 DOMINO %s" % chain_id
    if mode == "APPLY":
        require(token, "APPLY_TOKEN_MISSING")
        return "APPLY P06 DOMINO %s %s" % (chain_id, token)
    require(apply_run, "REVERT_APPLY_RUN_MISSING")
    return "REVERT P06 DOMINO %s %s" % (chain_id, apply_run)


def validate_args(raw):
    a = {
        "mode": "DRY",
        "chain_id": CHAIN_B,
        "mode_b": "choreographed",
        "side": "R",
        "n": 12,
        "end": "floor",
        "p06_music_s": 110.561125,
        "p33_display_fps": 25.0,
        "slam_s": None,
        "slam_lead_s": 2.0,
        "gravity_exponent": 2.35,
        "fall_s": 1.65,
        "min_fall_s": 1.4,
        "shockwave_delay_s": 0.35,
        "shockwave_jitter_s": 0.08,
        "stagger_s": 0.38,
        "settle_s": 0.62,
        "bounce_deg": 2.0,
        "hesitation_jitter_s": 0.08,
        "bounce_jitter_deg": 0.35,
        "seed": 3706,
        "restyle_chain_a": False,
        "dust_asset": "/Game/KK_S2_Shrine/StarterContent/Particles/P_Ambient_Dust",
        "dust_auto_activate": False,
        "dust_cap": 12,
        "dust_scale": 1.0,
        "slam_dust_scale": 2.25,
        "dust_life_s": 1.25,
        "floor_z_cm": -100.0,
        "slam_sound": "/Game/KK_S2_Shrine/StarterContent/Audio/Collapse01",
        "sequence": "/Game/InfinityStage/Effects/LS_P06_DominoFinale",
        "choreo": "/Game/InfinityStage/Choreo/LS_Choreo_Passage_6",
    }
    a.update(raw or {})
    a["mode"] = str(a["mode"]).upper()
    errors = []
    if a["mode"] not in MODES:
        errors.append("MODE_INVALID")
    if a["chain_id"] not in (CHAIN_B, CHAIN_A_RESTYLE):
        errors.append("CHAIN_ID_INVALID")
    if a["side"] not in SIDES:
        errors.append("SIDE_INVALID")
    if a["chain_id"] == CHAIN_B and a["side"] != "R":
        errors.append("CHAIN_B_MUST_BE_RIGHT")
    if a["mode_b"] not in CHAIN_MODES:
        errors.append("MODE_B_INVALID")
    if not isinstance(a["n"], int) or not (MIN_CHAIN_ROWS <= a["n"] <= 12):
        errors.append("N_OUTSIDE_2_12")
    if a["end"] != "floor":
        errors.append("CHAIN_B_END_MUST_BE_FLOOR")
    for name in ("p06_music_s", "p33_display_fps", "slam_lead_s", "gravity_exponent", "fall_s",
                 "min_fall_s", "shockwave_delay_s", "shockwave_jitter_s", "stagger_s", "settle_s",
                 "bounce_deg", "hesitation_jitter_s", "bounce_jitter_deg", "dust_scale",
                 "slam_dust_scale", "dust_life_s", "floor_z_cm"):
        if not isinstance(a.get(name), (int, float)):
            errors.append("%s_NOT_NUMERIC" % name.upper())
    if isinstance(a.get("gravity_exponent"), (int, float)) and a["gravity_exponent"] <= 1.0:
        errors.append("GRAVITY_EXPONENT_MUST_BE_GT_1")
    if a.get("slam_s") is not None and not isinstance(a.get("slam_s"), (int, float)):
        errors.append("SLAM_S_NOT_NUMERIC_OR_NULL")
    if (isinstance(a.get("fall_s"), (int, float)) and isinstance(a.get("min_fall_s"), (int, float))
            and a["fall_s"] < a["min_fall_s"]):
        errors.append("FALL_BELOW_MINIMUM:%.6f<%.6f" % (a["fall_s"], a["min_fall_s"]))
    if isinstance(a.get("min_fall_s"), (int, float)) and a["min_fall_s"] <= 0.0:
        errors.append("MIN_FALL_MUST_BE_POSITIVE")
    if isinstance(a.get("shockwave_delay_s"), (int, float)) and a["shockwave_delay_s"] < 0.0:
        errors.append("SHOCKWAVE_DELAY_NEGATIVE")
    if isinstance(a.get("shockwave_jitter_s"), (int, float)) and not (0.0 <= a["shockwave_jitter_s"] <= a["shockwave_delay_s"]):
        errors.append("SHOCKWAVE_JITTER_OUTSIDE_DELAY")
    if isinstance(a.get("bounce_deg"), (int, float)) and not (0.0 <= a["bounce_deg"] <= MAX_BOUNCE_DEG):
        errors.append("BOUNCE_OUTSIDE_0_3_DEG")
    if isinstance(a.get("bounce_jitter_deg"), (int, float)) and a["bounce_deg"] + a["bounce_jitter_deg"] > MAX_BOUNCE_DEG:
        errors.append("BOUNCE_PLUS_JITTER_GT_3_DEG")
    if not isinstance(a.get("seed"), int):
        errors.append("SEED_NOT_INT")
    if not isinstance(a.get("restyle_chain_a"), bool):
        errors.append("RESTYLE_CHAIN_A_NOT_BOOL")
    if a.get("dust_auto_activate") is not False:
        errors.append("DUST_AUTO_ACTIVATE_TRUE_REFUSED")
    if not isinstance(a.get("dust_cap"), int) or not (1 <= a["dust_cap"] <= 12):
        errors.append("DUST_CAP_OUTSIDE_1_12")
    for name in ("dust_asset", "slam_sound", "sequence", "choreo"):
        if not str(a.get(name) or "").startswith("/Game/"):
            errors.append("%s_NOT_GAME_PATH" % name.upper())
    if a["mode"] != "DRY" and not str(a.get("decided_by") or "").strip():
        errors.append("DECIDED_BY_REQUIRED")
    return a, errors


def guid_set_from_chain(chain):
    return {str(r["cue_guid"]).upper() for r in ((chain or {}).get("rows") or [])}


def adopt_chain_a(plan, active):
    """Return the read-only identity of the applied 7 Oct chain; never a write plan."""
    require(plan and plan.get("chain"), "CHAIN_A_PLAN_MISSING")
    require(active and active.get("run_id"), "CHAIN_A_ACTIVE_MISSING")
    rows = plan["chain"].get("rows") or []
    require(plan["chain"].get("side") == "L" and len(rows) == 6, "CHAIN_A_NOT_SIX_LEFT")
    return {
        "chain_id": CHAIN_A,
        "adopted_read_only": True,
        "active_run_id": active["run_id"],
        "side": "L",
        "row_guids": [r["cue_guid"] for r in rows],
        "row_labels": [r["label"] for r in rows],
        "creak_s": float(plan["chain"]["timing"]["creak_s"]),
        "final_impact_s": float(plan["chain"]["timing"]["final_impact_s"]),
        "rest_s": float(plan["chain"]["timing"]["rest_s"]),
        "last_row_ahead_cm_at_final_impact": float(
            plan["chain"]["timing"].get("last_row_ahead_cm_at_final_impact", float("nan"))),
        "plan_inputs_hash": plan.get("inputs_hash"),
    }


def overlap_guids(a_rows, b_rows):
    a = {str(r["cue_guid"]).upper() for r in a_rows}
    b = {str(r["cue_guid"]).upper() for r in b_rows}
    return sorted(a & b)


def require_disjoint(chain_a_rows, chain_b_rows):
    overlap = overlap_guids(chain_a_rows, chain_b_rows)
    require(not overlap, "CHAIN_B_OVERLAPS_CHAIN_A_ROWS|%s" % ",".join(overlap))
    return True


def lateral_overlap(a, b):
    return min(float(a["lateral_max_cm"]), float(b["lateral_max_cm"])) - max(
        float(a["lateral_min_cm"]), float(b["lateral_min_cm"]))


def row_reasons(row, side):
    s = (row.get("sides") or {}).get(side)
    out = []
    if not row.get("enabled", True):
        out.append("CUE_DISABLED")
    if not s or not s.get("mesh"):
        return out + ["NO_PANEL"]
    if s.get("materialized") is not True:
        out.append("NOT_MATERIALIZED")
    if s.get("upright") is False:
        out.append("PANEL_NOT_UPRIGHT")
    if s.get("external_curve"):
        out.append("EXTERNAL_CURVE_SET")
    if float(s.get("thickness_cm", 1e9)) > MAX_THICKNESS_CM:
        out.append("TOO_THICK_FOR_SLAB:%.1f" % float(s["thickness_cm"]))
    if float(s.get("height_cm", 0.0)) < MIN_HEIGHT_CM:
        out.append("TOO_SHORT:%.1f" % float(s["height_cm"]))
    if abs(float(s.get("axis_dot_tangent", 1.0))) > MAX_AXIS_DOT:
        out.append("HINGE_AXIS_NOT_LATERAL:%.3f" % float(s["axis_dot_tangent"]))
    return out


def window_reasons(rows, start, n, side, protected_guids=()):
    window = rows[start:start + n]
    out = []
    if len(window) != n:
        return ["PAST_PASSAGE_END"]
    protected = {str(x).upper() for x in protected_guids}
    for row in window:
        if str(row["cue_guid"]).upper() in protected:
            out.append("CHAIN_A_ROW:%s" % row["label"])
        out += ["%s:%s" % (row["label"], reason) for reason in row_reasons(row, side)]
    if out:
        return out
    sm = [r["sides"][side] for r in window]
    for i, (a, b) in enumerate(zip(sm[:-1], sm[1:])):
        gap = float(b["hinge_route_cm"]) - float(a["hinge_route_cm"])
        contact_c = (float(a["thickness_cm"]) + float(b["thickness_cm"])) / 2.0
        if gap <= 0:
            out.append("HINGES_NOT_INCREASING:%d" % i)
        if float(a["height_cm"]) <= gap - contact_c:
            out.append("NO_CONTACT:%d:height=%.1f:gap_minus_c=%.1f" %
                       (i, float(a["height_cm"]), gap - contact_c))
        overlap = lateral_overlap(a, b)
        if overlap < MIN_LATERAL_OVERLAP_CM:
            out.append("LATERAL_OVERLAP:%d:%.1f" % (i, overlap))
    return out


def suffix_diagnostics(rows, desired_n, side, protected_guids=()):
    """Test decreasing suffixes ending at the last row; Gary asked for a chain to the Passage end."""
    table = []
    for n in range(min(desired_n, len(rows)), 0, -1):
        start = len(rows) - n
        reasons = window_reasons(rows, start, n, side, protected_guids)
        table.append({
            "n": n,
            "start_ordinal": start,
            "first": rows[start]["label"],
            "last": rows[-1]["label"],
            "cue_guids": [r["cue_guid"] for r in rows[start:]],
            "reasons": reasons,
            "eligible": not reasons,
        })
    return table


def choose_suffix(rows, desired_n, side, protected_guids=()):
    table = suffix_diagnostics(rows, desired_n, side, protected_guids)
    valid = [r for r in table if r["eligible"]]
    chosen = valid[0] if valid else None
    if chosen and chosen["n"] < MIN_CHAIN_ROWS:
        return None, table, "ONLY_%d_CONTACTABLE_SUFFIX_ROW; domino requires at least %d" % (
            chosen["n"], MIN_CHAIN_ROWS)
    if chosen is None:
        return None, table, "NO_CONTACTABLE_SUFFIX"
    return chosen, table, None


def _round_positive(value):
    return int(math.floor(float(value) + 0.5))


def project_post_p33(measurements, music_s, display_fps):
    """Mirror P33's per-field scaling and display-frame ceiling without mutating the measured input."""
    out = copy.deepcopy(measurements)
    tick = int(round(float(measurements["tick"])))
    fps = float(display_fps)
    require(tick > 0 and fps > 0.0, "P33_RATE_INVALID")
    ticks_per_display = tick / fps
    require(abs(ticks_per_display - round(ticks_per_display)) < 1e-9, "P33_NONINTEGRAL_TICKS_PER_FRAME")
    ticks_per_display = int(round(ticks_per_display))
    raw_target = int(math.ceil(float(music_s) * tick - 1e-9))
    target = -((-raw_target) // ticks_per_display) * ticks_per_display
    old_end = int(measurements["law"]["segment_end"])
    require(old_end > 0, "P33_OLD_END_NONPOSITIVE")
    scale = target / float(old_end)
    old_pass = [int(r["pass_frame"]) for r in measurements["rows"]]
    require(old_pass and old_pass == sorted(old_pass), "P33_PASS_FRAMES_NOT_ORDERED")
    lead = old_pass[0]
    intervals = [b - a for a, b in zip(old_pass[:-1], old_pass[1:])]
    new_pass = [_round_positive(lead * scale)]
    for interval in intervals:
        new_pass.append(new_pass[-1] + max(1, _round_positive(interval * scale)))
    require(new_pass[-1] <= target, "P33_PROJECTED_LAST_ROW_AFTER_END")
    law = measurements["law"]["points"]
    require(len(law) == len(old_pass) + 2, "P33_LAW_ROW_COUNT_MISMATCH")
    for row, frame in zip(out["rows"], new_pass):
        row["pass_frame"] = frame
    out["law"]["points"] = ([[0, float(law[0][1])]] +
                              [[frame, float(point[1])] for frame, point in zip(new_pass, law[1:-1])] +
                              [[target, float(law[-1][1])]])
    out["law"]["segment_end"] = target
    out["p33_projection"] = {
        "selected_music_s": float(music_s),
        "display_fps": fps,
        "old_segment_end_ticks": old_end,
        "old_segment_end_s": old_end / float(tick),
        "target_ticks_before_display_rounding": raw_target,
        "post_p33_segment_end_ticks": target,
        "post_p33_segment_end_s": target / float(tick),
        "scale": scale,
        "method": "P33_PER_FIELD_SCALE_WITH_WHOLE_DISPLAY_FRAME_CEILING",
    }
    return out


def seeded_draws(seed, n, shockwave_jitter_s, bounce_deg, bounce_jitter_deg):
    """Stable order: one bounce draw per row and one signed delay-jitter draw per transition."""
    rng = random.Random(int(seed))
    out = []
    for i in range(n):
        delay_jitter = None if i == 0 else (rng.random() * 2.0 - 1.0) * float(shockwave_jitter_s)
        bounce = float(bounce_deg) + (rng.random() * 2.0 - 1.0) * float(bounce_jitter_deg)
        bounce = max(0.0, min(MAX_BOUNCE_DEG, bounce))
        out.append({"row": i,
                    "shockwave_jitter_s": None if delay_jitter is None else round(delay_jitter, 6),
                    "bounce_deg": round(bounce, 6)})
    return out


def choreographed_times(n, args, passage_end_s):
    slam_limit_s = float(passage_end_s) - float(args["slam_lead_s"])
    slam_s = slam_limit_s if args.get("slam_s") is None else float(args["slam_s"])
    draws = seeded_draws(args["seed"], n, args["shockwave_jitter_s"], args["bounce_deg"],
                         args["bounce_jitter_deg"])
    impacts = [0.0] * n
    creaks = [0.0] * n
    impacts[-1] = slam_s
    creaks[-1] = impacts[-1] - float(args["fall_s"])
    for i in range(n - 1, 0, -1):
        delay = float(args["shockwave_delay_s"]) + float(draws[i]["shockwave_jitter_s"])
        impacts[i - 1] = creaks[i] - delay
        creaks[i - 1] = impacts[i - 1] - float(args["fall_s"])
    refusals = []
    if slam_s > slam_limit_s + 1e-9:
        refusals.append("SLAM_AFTER_END_MINUS_LEAD:%.6f>%.6f" % (slam_s, slam_limit_s))
    if slam_s < 0.0:
        refusals.append("SLAM_BEFORE_PASSAGE_START:%.6f" % slam_s)
    if creaks[0] < -1e-9:
        refusals.append("CHAIN_START_BEFORE_PASSAGE:%.6f" % creaks[0])
    rest_s = slam_s + float(args["settle_s"])
    if rest_s > float(passage_end_s) + 1e-9:
        refusals.append("CHAIN_REST_AFTER_PASSAGE_END:%.6f>%.6f" % (rest_s, passage_end_s))
    return {"draws": draws, "creaks_s": creaks, "impacts_s": impacts,
            "slam_s": slam_s, "slam_limit_s": slam_limit_s, "rest_s": rest_s,
            "refusals": refusals}


def choreographed_row_reasons(row, side):
    """Eligibility without contact/thickness assumptions: each panel is independently cued."""
    reasons = [x for x in row_reasons(row, side) if not x.startswith("TOO_THICK_FOR_SLAB")]
    s = (row.get("sides") or {}).get(side) or {}
    if float(s.get("thickness_cm", 0.0)) <= 0.0:
        reasons.append("THICKNESS_NONPOSITIVE")
    return reasons


def fall_sweep_refusals(rows, start, n, side, timing, topple_core):
    """Conservative route/lateral footprint test for a -route fall; already-fallen chain rows are excluded."""
    chosen = rows[start:start + n]
    failures = []
    audits = []
    for i, row in enumerate(chosen):
        s = row["sides"][side]
        hinge = float(s["hinge_route_cm"])
        height = float(s["height_cm"])
        half_t = float(s["thickness_cm"]) / 2.0
        sweep_min, sweep_max = hinge - height - half_t, hinge + half_t
        camera = topple_core.distance_at_frame(
            timing["law"], float(timing["impacts_s"][i]) * float(timing["tick"]))
        row_failures = []
        if camera <= hinge + 1e-6:
            row_failures.append("CAMERA_NOT_AHEAD_FOR_DOWNSTAGE_FALL:camera=%.3f:hinge=%.3f" % (camera, hinge))
        # Earlier selected rows have already fallen. Every other same-side panel is still standing.
        fallen_guids = {r["cue_guid"] for r in chosen[:i]}
        for standing in rows:
            if standing["cue_guid"] == row["cue_guid"] or standing["cue_guid"] in fallen_guids:
                continue
            other = (standing.get("sides") or {}).get(side)
            if not other or not other.get("mesh") or other.get("upright") is False:
                continue
            if lateral_overlap(s, other) <= 0.0:
                continue
            other_hinge = float(other["hinge_route_cm"])
            other_half = float(other["thickness_cm"]) / 2.0
            if other_hinge + other_half >= sweep_min - 1e-6 and other_hinge - other_half <= sweep_max + 1e-6:
                row_failures.append("FALL_SWEEP_INTERSECTS_STANDING_PANEL:%s" % standing["label"])
        audits.append({"label": row["label"], "cue_guid": row["cue_guid"], "fall_order": i,
                       "direction": "DOWNSTAGE_NEGATIVE_ROUTE_AWAY_FROM_CAMERA",
                       "sweep_route_cm": [round(sweep_min, 3), round(sweep_max, 3)],
                       "camera_cm_at_impact": round(camera, 6), "hinge_route_cm": round(hinge, 6),
                       "standing_panel_intersections": row_failures})
        failures += ["%s:%s" % (row["label"], reason) for reason in row_failures]
    return failures, audits


def choose_choreographed_suffix(measurements, desired_n, side, protected_guids, args, topple_core):
    rows = measurements["rows"]
    passage_end_s = float(measurements["law"]["segment_end"]) / float(measurements["tick"])
    protected = {str(x).upper() for x in protected_guids}
    table = []
    for n in range(min(desired_n, len(rows)), 0, -1):
        start = len(rows) - n
        window = rows[start:]
        reasons = []
        for row in window:
            if str(row["cue_guid"]).upper() in protected:
                reasons.append("CHAIN_A_ROW:%s" % row["label"])
            reasons += ["%s:%s" % (row["label"], reason) for reason in choreographed_row_reasons(row, side)]
        timing = choreographed_times(n, args, passage_end_s)
        reasons += timing["refusals"]
        sweep_timing = {"law": measurements["law"], "tick": measurements["tick"],
                        "impacts_s": timing["impacts_s"]}
        sweep_reasons, audits = fall_sweep_refusals(rows, start, n, side, sweep_timing, topple_core)
        reasons += sweep_reasons
        table.append({"n": n, "start_ordinal": start, "first": rows[start]["label"],
                      "last": rows[-1]["label"], "cue_guids": [r["cue_guid"] for r in window],
                      "mode_b": "choreographed", "timing": timing, "fall_sweep_audit": audits,
                      "reasons": reasons, "eligible": not reasons})
    chosen = next((row for row in table if row["eligible"]), None)
    if chosen is None:
        return None, table, "NO_CHOREOGRAPHED_SUFFIX_FITS"
    reduction = None if chosen["n"] == min(desired_n, len(rows)) else "REDUCED_TO_%d_TO_FIT_WITHOUT_SQUEEZING" % chosen["n"]
    return chosen, table, reduction


def gravity_solver_keys(fall_s, settle_s, bounce_deg, exponent):
    """Normalised curve: late acceleration to floor, one rebound, then settle."""
    duration = float(fall_s) + float(settle_s)
    impact_phase = float(fall_s) / duration
    rebound_phase = min(0.995, impact_phase + float(settle_s) * 0.42 / duration)
    keys = []
    for u in (0.0, 0.34, 0.70, 1.0):
        phase = impact_phase * u
        value = u ** float(exponent)
        tangent = 0.0 if u == 0.0 else float(exponent) * u ** (float(exponent) - 1.0) / impact_phase
        keys.append({"phase": phase, "value": value, "arrive_tangent": tangent,
                     "leave_tangent": tangent if u < 1.0 else 0.0})
    keys.append({"phase": rebound_phase, "value": 1.0 - float(bounce_deg) / 90.0,
                 "arrive_tangent": 0.0, "leave_tangent": 0.0})
    keys.append({"phase": 1.0, "value": 1.0, "arrive_tangent": 0.0, "leave_tangent": 0.0})
    return keys


def _route_tangent(window, index, side):
    here = window[index]["sides"][side]["hinge_world"]
    other = (window[index + 1]["sides"][side]["hinge_world"] if index + 1 < len(window)
             else window[index - 1]["sides"][side]["hinge_world"])
    sign = 1.0 if index + 1 < len(window) else -1.0
    dx, dy = sign * (float(other[0]) - float(here[0])), sign * (float(other[1]) - float(here[1]))
    length = max(1e-9, math.hypot(dx, dy))
    return dx / length, dy / length


def dust_rows(window, side, impacts_s, args, chain_id):
    require(len(window) == len(impacts_s), "DUST_IMPACT_COUNT")
    require(len(window) <= int(args["dust_cap"]), "DUST_CAP_EXCEEDED")
    out = []
    for i, (row, impact) in enumerate(zip(window, impacts_s)):
        s = row["sides"][side]
        hinge = [float(x) for x in s["hinge_world"]]
        tx, ty = _route_tangent(window, i, side) if len(window) > 1 else (1.0, 0.0)
        height = float(s["height_cm"])
        scale = float(args["slam_dust_scale"] if i == len(window) - 1 and chain_id == CHAIN_B else args["dust_scale"])
        out.append({
            "owner": "P37_DOMINO_%s" % chain_id,
            "label": "P06 Domino %s Dust %02d %s" % (chain_id, i + 1, row["label"]),
            "cue_guid": row["cue_guid"],
            "impact_s": round(float(impact), 6),
            "end_s": round(float(impact) + float(args["dust_life_s"]), 6),
            "location_cm": [round(hinge[0] + tx * height, 3), round(hinge[1] + ty * height, 3),
                            round(float(args["floor_z_cm"]), 3)],
            "asset": args["dust_asset"],
            "auto_activate": False,
            "cast_shadow": False,
            "light_count": 0,
            "scale": scale,
            "slam_scaled": i == len(window) - 1 and chain_id == CHAIN_B,
        })
    return out


def _chain_rows(measurements, chosen):
    start, n = int(chosen["start_ordinal"]), int(chosen["n"])
    return measurements["rows"][start:start + n]


def build_chain_b(measurements, chosen, args, topple_core):
    window = _chain_rows(measurements, chosen)
    n = len(window)
    tick = float(measurements["tick"])
    passage_end_s = float(measurements["law"]["segment_end"]) / tick
    if args["mode_b"] == "choreographed":
        schedule = choreographed_times(n, args, passage_end_s)
        draws = schedule["draws"]
        creaks_s = schedule["creaks_s"]
        impacts_s = schedule["impacts_s"]
        rest_s = schedule["rest_s"]
        slam_s = schedule["slam_s"]
        slam_limit_s = schedule["slam_limit_s"]
        refusals = list(schedule["refusals"])
    else:
        rng = random.Random(int(args["seed"]))
        draws = []
        for i in range(n):
            hesitation = rng.random() * float(args["hesitation_jitter_s"])
            bounce = float(args["bounce_deg"]) + (rng.random() * 2.0 - 1.0) * float(args["bounce_jitter_deg"])
            draws.append({"row": i, "hesitation_s": round(hesitation, 6),
                          "bounce_deg": round(max(0.0, min(MAX_BOUNCE_DEG, bounce)), 6)})
        gaps = [float(args["stagger_s"]) + draws[i]["hesitation_s"] for i in range(1, n)]
        relative_impacts = [float(args["fall_s"])]
        for gap in gaps:
            relative_impacts.append(relative_impacts[-1] + gap)
        slam_limit_s = passage_end_s - float(args["slam_lead_s"])
        slam_s = slam_limit_s if args.get("slam_s") is None else float(args["slam_s"])
        first_creak = slam_s - relative_impacts[-1]
        impacts_s = [first_creak + x for x in relative_impacts]
        creaks_s = [impact - float(args["fall_s"]) for impact in impacts_s]
        rest_s = slam_s + float(args["settle_s"])
        refusals = []
        if slam_s > slam_limit_s + 1e-9:
            refusals.append("SLAM_AFTER_END_MINUS_LEAD:%.6f>%.6f" % (slam_s, slam_limit_s))
        if creaks_s[0] < -1e-9:
            refusals.append("CHAIN_START_BEFORE_PASSAGE:%.6f" % creaks_s[0])
        if rest_s > passage_end_s + 1e-9:
            refusals.append("CHAIN_REST_AFTER_PASSAGE_END:%.6f>%.6f" % (rest_s, passage_end_s))
    plan_rows = []
    for i, (row, creak_s, impact_s, draw) in enumerate(zip(window, creaks_s, impacts_s, draws)):
        start_s = creak_s
        duration_s = float(args["fall_s"]) + float(args["settle_s"])
        rate = 1.0 / duration_s
        raw_keys = gravity_solver_keys(args["fall_s"], args["settle_s"], draw["bounce_deg"],
                                       args["gravity_exponent"])
        keys = topple_core.plan_keys(raw_keys)
        other = "L" if args["side"] == "R" else "R"
        phase_offset = (float(row["pass_frame"]) / tick - start_s) * rate
        camera_cm = topple_core.distance_at_frame(measurements["law"], impact_s * tick)
        hinge_cm = float(row["sides"][args["side"]]["hinge_route_cm"])
        plan_rows.append({
            "fall_order": i,
            "cue_guid": row["cue_guid"],
            "show_index": row["show_index"],
            "label": row["label"],
            "side": args["side"],
            "has_top": bool(row["has_top"]),
            "action": "chain",
            "chain_mode": args["mode_b"],
            "fall_direction": "DOWNSTAGE_NEGATIVE_ROUTE_AWAY_FROM_CAMERA",
            "set": {"kind": "TOPPLE", "playback_mode": "ONE_SHOT", "phase_origin": "PASS_FRAME",
                    "cycle_rate_hz": rate, "phase_offset_cycles": phase_offset, "max_angle_deg": -90.0,
                    "top_follows_mechanism": False if row["has_top"] else None},
            "keys": keys,
            "curve_text": topple_core.curve_text(keys),
            "other_side": other,
            "other_keys": topple_core.flat_keys(),
            "other_curve_text": topple_core.curve_text(topple_core.flat_keys()),
            "samples": [[ph, topple_core.hermite(keys, ph)] for ph in topple_core.sample_phases(keys)],
            "timing": {"creak_s": creak_s, "start_s": start_s, "impact_s": impact_s,
                       "shockwave_from_previous_s": (None if i == 0 else
                           creak_s - impacts_s[i - 1]),
                       "rest_s": impact_s + float(args["settle_s"]),
                       "pass_frame_rel": row["pass_frame"], "CycleRateHz": rate,
                       "PhaseOffsetCycles": phase_offset, "camera_cm_at_impact": camera_cm,
                       "hinge_route_cm": hinge_cm, "row_ahead_of_camera_cm": hinge_cm - camera_cm},
            "final_deg": -90.0,
            "fit_max_err_deg": 0.0,
            "draw": draw,
        })
    win_for_hash = {"side": args["side"], "cue_guids": [r["cue_guid"] for r in window], "brace": None}
    inputs = topple_core.inputs_for(measurements, win_for_hash, None)
    camera_at_slam = topple_core.distance_at_frame(measurements["law"], slam_s * tick)
    last_hinge = float(window[-1]["sides"][args["side"]]["hinge_route_cm"])
    chain = {
        "chain_id": CHAIN_B,
        "mode_b": args["mode_b"],
        "side": args["side"],
        "start_ordinal": chosen["start_ordinal"],
        "n": n,
        "end": "floor",
        "brace": None,
        "next_row_hits": [],
        "rows": plan_rows,
        "events": ([{"type": "shockwave", "source_slab": i, "triggers_slab": i + 1,
                     "impact_s": impacts_s[i], "next_creak_s": creaks_s[i + 1],
                     "delay_s": creaks_s[i + 1] - impacts_s[i]} for i in range(n - 1)] +
                   [{"type": "floor", "slab": n - 1, "impact_s": impacts_s[-1], "n": 1},
                    {"type": "rest", "slab": n - 1, "rest_s": rest_s}]),
        "t_end_s": rest_s - creaks_s[0],
        "timing": {"creak_s": creaks_s[0], "first_impact_s": impacts_s[0],
                    "final_impact_s": impacts_s[-1], "rest_s": rest_s,
                    "segment_end_s": passage_end_s, "slam_limit_s": slam_limit_s,
                    "camera_cm_at_final_impact": camera_at_slam,
                    "last_row_ahead_cm_at_final_impact": last_hinge - camera_at_slam,
                    "refusals": refusals},
        "fall_sweep_audit": chosen.get("fall_sweep_audit") or [],
        "flags": ["NO_CONTACT_ELIGIBILITY"] if args["mode_b"] == "choreographed" else [],
    }
    dust = dust_rows(window, args["side"], impacts_s, args, CHAIN_B)
    return chain, inputs, topple_core.inputs_hash(inputs), dust, refusals


def _chain_a_impact_times(chain_a_plan):
    c = chain_a_plan["chain"]
    creak = float(c["timing"]["creak_s"])
    impacts = [None] * len(c["rows"])
    for event in c.get("events") or []:
        if event.get("type") == "domino":
            impacts[int(event["slab"])] = creak + float(event["t"])
        elif (event.get("type") in ("wall", "floor") and int(event.get("slab", -1)) == len(impacts) - 1
              and impacts[-1] is None):
            impacts[-1] = creak + float(event["t"])
    final = float(c["timing"]["final_impact_s"])
    return [final if x is None else x for x in impacts]


def restyle_chain_a(chain_a_plan, measurements, args, topple_core):
    """Opt-in curve-only restyle; its APPLY record is separate and restores the already-applied A state."""
    source = chain_a_plan["chain"]
    by_guid = {r["cue_guid"]: r for r in measurements["rows"]}
    impacts = _chain_a_impact_times(chain_a_plan)
    tick = float(measurements["tick"])
    rng = random.Random(int(args["seed"]) + 1)
    draws = []
    for i in range(len(source["rows"])):
        hesitation = rng.random() * float(args["hesitation_jitter_s"])
        bounce = float(args["bounce_deg"]) + (rng.random() * 2.0 - 1.0) * float(args["bounce_jitter_deg"])
        draws.append({"row": i, "hesitation_s": round(hesitation, 6),
                      "bounce_deg": round(max(0.0, min(MAX_BOUNCE_DEG, bounce)), 6)})
    rows = []
    for i, (old, impact, draw) in enumerate(zip(source["rows"], impacts, draws)):
        row = by_guid[old["cue_guid"]]
        old_start = float(old.get("timing", {}).get("start_s", old.get("start_s", 0.0)))
        absolute_start = float(source["timing"]["creak_s"]) + old_start + draw["hesitation_s"]
        fall = max(0.25, float(impact) - absolute_start)
        duration = fall + float(args["settle_s"])
        keys = topple_core.plan_keys(gravity_solver_keys(fall, args["settle_s"], draw["bounce_deg"],
                                                         args["gravity_exponent"]))
        rate = 1.0 / duration
        side = source["side"]
        other = "R" if side == "L" else "L"
        rows.append(dict(old, action="chain", side=side, other_side=other, keys=keys,
                         curve_text=topple_core.curve_text(keys), other_keys=topple_core.flat_keys(),
                         other_curve_text=topple_core.curve_text(topple_core.flat_keys()),
                         samples=[[p, topple_core.hermite(keys, p)] for p in topple_core.sample_phases(keys)],
                         set={"kind": "TOPPLE", "playback_mode": "ONE_SHOT", "phase_origin": "PASS_FRAME",
                              "cycle_rate_hz": rate,
                              "phase_offset_cycles": (float(row["pass_frame"]) / tick - absolute_start) * rate,
                              "max_angle_deg": -90.0,
                              "top_follows_mechanism": False if row["has_top"] else None},
                         timing={"start_s": absolute_start, "impact_s": impact,
                                 "rest_s": impact + float(args["settle_s"])}, draw=draw,
                         final_deg=-90.0, fit_max_err_deg=0.0))
    return {"chain_id": CHAIN_A_RESTYLE, "side": source["side"], "start_ordinal": source["start_ordinal"],
            "n": len(rows), "end": source["end"], "brace": source.get("brace"), "rows": rows,
            "timing": dict(source["timing"], restyled=True), "events": source.get("events") or []}


def p33_forecast(measurements, projected_measurements, chain_a_plan, chain_b):
    old_len = float(measurements["law"]["segment_end"]) / float(measurements["tick"])
    new_len = float(projected_measurements["law"]["segment_end"]) / float(projected_measurements["tick"])
    scale = new_len / old_len
    by_guid = {r["cue_guid"]: r for r in measurements["rows"]}
    projected_by_guid = {r["cue_guid"]: r for r in projected_measurements["rows"]}
    impacts_a = _chain_a_impact_times(chain_a_plan)
    shifted_a = []
    for row, impact in zip(chain_a_plan["chain"]["rows"], impacts_a):
        pass_s = float(by_guid[row["cue_guid"]]["pass_frame"]) / float(measurements["tick"])
        projected_pass_s = (float(projected_by_guid[row["cue_guid"]]["pass_frame"]) /
                            float(projected_measurements["tick"]))
        delta = projected_pass_s - pass_s
        shifted_a.append({"label": row["label"], "old_impact_s": impact,
                          "post_p33_impact_s_if_mechanism_untouched": impact + delta,
                          "old_pass_s": pass_s, "post_p33_pass_s": projected_pass_s,
                          "shift_s": delta})
    b_slam = None if not chain_b else float(chain_b["timing"]["final_impact_s"])
    return {
        "authority": "P33 per-field scales LeadIn/intervals/Tail and rounds the Passage end to a display frame; mechanism phase fields are unchanged",
        "old_length_s": old_len,
        "selected_music_s": projected_measurements["p33_projection"]["selected_music_s"],
        "target_length_s": new_len,
        "timing_scale": scale,
        "chain_a": shifted_a,
        "chain_a_consequence": "B APPLY does not edit A; these are A's projected post-P33 impacts with its existing mechanism fields",
        "chain_b_slam_s": b_slam,
        "chain_b_past_new_end": b_slam is not None and b_slam > new_len,
        "chain_b_consequence": "B is solved directly on the projected post-P33 law; APPLY's input hash must match that saved law",
    }


def registry_entry(chain_id, apply_run, row_guids, after_hashes, originals_path, fx_record=None):
    require(chain_id in (CHAIN_B, CHAIN_A_RESTYLE), "REGISTRY_CHAIN_ID")
    require(len(row_guids) == len(set(row_guids)), "REGISTRY_DUPLICATE_GUID")
    return {"schema": 1, "chain_id": chain_id, "apply_run": apply_run,
            "row_guids": list(row_guids), "after_hashes": dict(after_hashes),
            "originals": originals_path, "fx_record": fx_record}


def active_record_name(chain_id):
    require(chain_id in (CHAIN_B, CHAIN_A_RESTYLE), "ACTIVE_RECORD_CHAIN_ID")
    return "domino_chain_%s_ACTIVE.json" % chain_id


def revert_scope(state, registry):
    """Pure field-scoped revert used by the harness: only the named chain's rows may change."""
    before = json.loads(json.dumps(state, sort_keys=True))
    target = registry["chain_id"]
    require(target in state["chains"], "CHAIN_NOT_ACTIVE")
    restored = state["chains"][target]["original_rows"]
    for guid, value in restored.items():
        state["rows"][guid] = value
    state["chains"][target]["active"] = False
    return before, state


def apply_scope(state, chain_id, replacement_rows):
    """Pure harness model of a field-scoped APPLY; rows outside chain_id are immutable."""
    require(chain_id == CHAIN_B, "APPLY_SCOPE_ONLY_CHAIN_B")
    before = json.loads(json.dumps(state, sort_keys=True))
    require(chain_id in state["chains"], "CHAIN_NOT_REGISTERED")
    for guid, value in replacement_rows.items():
        require(guid in state["chains"][chain_id]["original_rows"], "APPLY_ROW_OUTSIDE_CHAIN_B:%s" % guid)
        state["rows"][guid] = value
    state["chains"][chain_id]["active"] = True
    return before, state


def build_plan(measurements, chain_a_plan, chain_a_active, asset_inventory, raw_args, topple_core):
    args, errors = validate_args(raw_args)
    require(measurements.get("dry_ok") is True, "TOPPLE_MEASUREMENTS_NOT_DRY_OK")
    projected = project_post_p33(measurements, args["p06_music_s"], args["p33_display_fps"])
    passage_end_s = float(projected["law"]["segment_end"]) / float(projected["tick"])
    args = dict(args)
    if args.get("slam_s") is None:
        args["slam_s"] = passage_end_s - float(args["slam_lead_s"])
        args["slam_source"] = "POST_P33_END_MINUS_SLAM_LEAD"
    else:
        args["slam_source"] = "EXPLICIT"
    adopted_a = adopt_chain_a(chain_a_plan, chain_a_active)
    protected = adopted_a["row_guids"]
    if args["mode_b"] == "choreographed":
        chosen, suffix_table, reduction = choose_choreographed_suffix(
            projected, args["n"], args["side"], protected, args, topple_core)
    else:
        chosen, suffix_table, reduction = choose_suffix(projected["rows"], args["n"], args["side"], protected)
    blockers = list(errors)
    chain_b = None
    dust = []
    inputs = None
    inputs_hash = None
    if chosen is None:
        blockers.append("CHAIN_B_SUFFIX_REFUSED|%s" % reduction)
        blockers += list((suffix_table[0].get("reasons") if suffix_table else []) or [])
    else:
        chain_b, inputs, inputs_hash, dust, timing_refusals = build_chain_b(projected, chosen, args, topple_core)
        blockers += timing_refusals
        require_disjoint(chain_a_plan["chain"]["rows"], chain_b["rows"])
    tick = float(projected["tick"])
    camera_at_candidate_slam = topple_core.distance_at_frame(projected["law"], args["slam_s"] * tick)
    final_hinge = float(projected["rows"][-1]["sides"][args["side"]]["hinge_route_cm"])
    candidate_slam = {"time_s": args["slam_s"], "camera_cm": camera_at_candidate_slam,
                      "last_row_hinge_cm": final_hinge,
                      "last_row_ahead_cm": final_hinge - camera_at_candidate_slam,
                      "latest_allowed_s": passage_end_s - args["slam_lead_s"]}
    if len(dust) > args["dust_cap"]:
        blockers.append("DUST_CAP_EXCEEDED")
    if any(x.get("auto_activate") is not False for x in dust):
        blockers.append("DUST_AUTO_ACTIVATE_TRUE_REFUSED")
    sounds = (asset_inventory or {}).get("sound_candidates") or []
    chosen_sound = next((x for x in sounds if x.get("asset") == args["slam_sound"]), None)
    if chosen_sound is None:
        blockers.append("SLAM_SOUND_NOT_IN_INVENTORY")
    dust_rows_inventory = ((asset_inventory or {}).get("dust_candidates") or [])
    dust_assets = {x.get("asset") for x in dust_rows_inventory}
    if args["dust_asset"] not in dust_assets:
        blockers.append("DUST_ASSET_NOT_IN_INVENTORY")
    chosen_dust = next((x for x in dust_rows_inventory if x.get("asset") == args["dust_asset"]), None)
    if chosen_dust and chosen_dust.get("particle_light_module_strings"):
        blockers.append("DUST_ASSET_HAS_PARTICLE_LIGHT_MODULE")
    restyle = None
    restyle_legacy = None
    restyle_token = None
    if args["restyle_chain_a"]:
        restyle = restyle_chain_a(chain_a_plan, projected, args, topple_core)
        restyle_window = {"side": restyle["side"],
                          "cue_guids": [r["cue_guid"] for r in restyle["rows"]],
                          "brace": restyle.get("brace")}
        restyle_inputs = topple_core.inputs_for(measurements, restyle_window, None)
        restyle_hash = topple_core.inputs_hash(restyle_inputs)
        restyle_token = canonical_sha({"chain_id": CHAIN_A_RESTYLE, "chain": restyle,
                                       "inputs_hash": restyle_hash})[:12]
        restyle_legacy = {"parts": ["chain"], "still": [], "keeper": None,
                          "chain": restyle, "inputs": restyle_inputs, "inputs_hash": restyle_hash,
                          "gates_ok": True, "refusals": []}
    payload = {"chain_a": adopted_a, "chain_b": chain_b, "restyle_chain_a": restyle,
               "dust": dust, "sound": chosen_sound, "args": args}
    token = canonical_sha(payload)[:12]
    plan = {
        "schema": 1,
        "tool": "make_domino_finale_plan.py",
        "chain_ids": {"existing": CHAIN_A, "new": CHAIN_B,
                      "optional_restyle": CHAIN_A_RESTYLE},
        "args": args,
        "post_p33_projection": projected["p33_projection"],
        "chain_a": adopted_a,
        "chain_b": chain_b,
        "chain_a_restyle": restyle,
        "chain_a_restyle_plan": restyle_legacy,
        "chain_a_restyle_confirm": (None if restyle_token is None else
                                    confirm_for("APPLY", CHAIN_A_RESTYLE, token=restyle_token)),
        "suffix_diagnostics": suffix_table,
        "requested_rows": args["n"],
        "selected_rows": 0 if chain_b is None else chain_b["n"],
        "reduction_reason": reduction,
        "candidate_slam": candidate_slam,
        "dust_bursts": dust,
        "slam_sound": chosen_sound,
        "dust_asset_inventory": chosen_dust,
        "inputs": inputs,
        "inputs_hash": inputs_hash,
        "parts": ["chain"],
        "still": [],
        "timing_table": ([] if chain_b is None else [{"fall_order": row["fall_order"], "label": row["label"],
                           "creak_s": row["timing"]["creak_s"], "impact_s": row["timing"]["impact_s"],
                           "shockwave_from_previous_s": row["timing"]["shockwave_from_previous_s"],
                           "camera_cm_at_impact": row["timing"]["camera_cm_at_impact"],
                           "row_ahead_of_camera_cm": row["timing"]["row_ahead_of_camera_cm"]}
                          for row in chain_b["rows"]]),
        "p33_forecast": p33_forecast(measurements, projected, chain_a_plan, chain_b),
        "blockers": blockers,
        "gates_ok": not blockers,
        "apply_ready": not blockers,
        "confirm_token": token,
        "apply_confirm": confirm_for("APPLY", CHAIN_B, token=token),
        "proof_limits": [
            "offline planning only; no Unreal saved read-back",
            "no rendered dust, motion, or sound acceptance",
            "asset class and sequence APIs must pass live DRY before APPLY",
        ],
    }
    return plan
