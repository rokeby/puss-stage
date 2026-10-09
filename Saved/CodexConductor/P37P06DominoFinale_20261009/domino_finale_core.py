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
import math
import random
from pathlib import Path


CHAIN_A = "A"
CHAIN_B = "B"
CHAIN_A_RESTYLE = "A_RESTYLE"
SIDES = ("L", "R")
MODES = ("DRY", "APPLY", "REVERT")
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
        "side": "R",
        "n": 12,
        "end": "floor",
        "slam_s": 122.0,
        "end_margin_s": 2.0,
        "gravity_exponent": 2.35,
        "fall_s": 1.65,
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
    if not isinstance(a["n"], int) or not (MIN_CHAIN_ROWS <= a["n"] <= 12):
        errors.append("N_OUTSIDE_2_12")
    if a["end"] != "floor":
        errors.append("CHAIN_B_END_MUST_BE_FLOOR")
    for name in ("slam_s", "end_margin_s", "gravity_exponent", "fall_s", "stagger_s", "settle_s",
                 "bounce_deg", "hesitation_jitter_s", "bounce_jitter_deg", "dust_scale",
                 "slam_dust_scale", "dust_life_s", "floor_z_cm"):
        if not isinstance(a.get(name), (int, float)):
            errors.append("%s_NOT_NUMERIC" % name.upper())
    if isinstance(a.get("gravity_exponent"), (int, float)) and a["gravity_exponent"] <= 1.0:
        errors.append("GRAVITY_EXPONENT_MUST_BE_GT_1")
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


def seeded_draws(seed, n, hesitation_max_s, bounce_deg, bounce_jitter_deg):
    """Stable draw order: for each row, hesitation first and bounce second, exactly one draw per value."""
    rng = random.Random(int(seed))
    out = []
    for i in range(n):
        hesitation = rng.random() * float(hesitation_max_s)
        bounce = float(bounce_deg) + (rng.random() * 2.0 - 1.0) * float(bounce_jitter_deg)
        bounce = max(0.0, min(MAX_BOUNCE_DEG, bounce))
        out.append({"row": i, "hesitation_s": round(hesitation, 6), "bounce_deg": round(bounce, 6)})
    return out


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
    draws = seeded_draws(args["seed"], n, args["hesitation_jitter_s"], args["bounce_deg"],
                         args["bounce_jitter_deg"])
    gaps = [float(args["stagger_s"]) + draws[i]["hesitation_s"] for i in range(1, n)]
    relative_impacts = [float(args["fall_s"])]
    for gap in gaps:
        relative_impacts.append(relative_impacts[-1] + gap)
    creak_s = float(args["slam_s"]) - relative_impacts[-1]
    impacts_s = [creak_s + x for x in relative_impacts]
    rest_s = float(args["slam_s"]) + float(args["settle_s"])
    passage_end_s = float(measurements["law"]["segment_end"]) / tick
    finish_limit_s = passage_end_s - float(args["end_margin_s"])
    refusals = []
    if rest_s > finish_limit_s + 1e-9:
        refusals.append("CHAIN_FINISH_AFTER_END_MINUS_MARGIN:%.6f>%.6f" % (rest_s, finish_limit_s))
    plan_rows = []
    for i, (row, impact_s, draw) in enumerate(zip(window, impacts_s, draws)):
        start_s = impact_s - float(args["fall_s"])
        duration_s = float(args["fall_s"]) + float(args["settle_s"])
        rate = 1.0 / duration_s
        raw_keys = gravity_solver_keys(args["fall_s"], args["settle_s"], draw["bounce_deg"],
                                       args["gravity_exponent"])
        keys = topple_core.plan_keys(raw_keys)
        other = "L" if args["side"] == "R" else "R"
        phase_offset = (float(row["pass_frame"]) / tick - start_s) * rate
        plan_rows.append({
            "fall_order": i,
            "cue_guid": row["cue_guid"],
            "show_index": row["show_index"],
            "label": row["label"],
            "side": args["side"],
            "has_top": bool(row["has_top"]),
            "action": "chain",
            "set": {"kind": "TOPPLE", "playback_mode": "ONE_SHOT", "phase_origin": "PASS_FRAME",
                    "cycle_rate_hz": rate, "phase_offset_cycles": phase_offset, "max_angle_deg": -90.0,
                    "top_follows_mechanism": False if row["has_top"] else None},
            "keys": keys,
            "curve_text": topple_core.curve_text(keys),
            "other_side": other,
            "other_keys": topple_core.flat_keys(),
            "other_curve_text": topple_core.curve_text(topple_core.flat_keys()),
            "samples": [[ph, topple_core.hermite(keys, ph)] for ph in topple_core.sample_phases(keys)],
            "timing": {"start_s": start_s, "impact_s": impact_s, "rest_s": impact_s + float(args["settle_s"]),
                       "pass_frame_rel": row["pass_frame"], "CycleRateHz": rate,
                       "PhaseOffsetCycles": phase_offset},
            "final_deg": -90.0,
            "fit_max_err_deg": 0.0,
            "draw": draw,
        })
    win_for_hash = {"side": args["side"], "cue_guids": [r["cue_guid"] for r in window], "brace": None}
    inputs = topple_core.inputs_for(measurements, win_for_hash, None)
    camera_at_slam = topple_core.distance_at_frame(measurements["law"], float(args["slam_s"]) * tick)
    last_hinge = float(window[-1]["sides"][args["side"]]["hinge_route_cm"])
    chain = {
        "chain_id": CHAIN_B,
        "side": args["side"],
        "start_ordinal": chosen["start_ordinal"],
        "n": n,
        "end": "floor",
        "brace": None,
        "next_row_hits": [],
        "rows": plan_rows,
        "events": ([{"type": "domino", "slab": i, "hits": i + 1,
                     "t": impacts_s[i] - creak_s} for i in range(n - 1)] +
                   [{"type": "floor", "slab": n - 1, "t": impacts_s[-1] - creak_s, "n": 1},
                    {"type": "rest", "slab": n - 1, "t": rest_s - creak_s}]),
        "t_end_s": rest_s - creak_s,
        "timing": {"creak_s": creak_s, "first_impact_s": impacts_s[0],
                   "final_impact_s": impacts_s[-1], "rest_s": rest_s,
                   "segment_end_s": passage_end_s, "finish_limit_s": finish_limit_s,
                   "camera_cm_at_final_impact": camera_at_slam,
                   "last_row_ahead_cm_at_final_impact": last_hinge - camera_at_slam,
                   "refusals": refusals},
        "flags": [],
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
    draws = seeded_draws(args["seed"] + 1, len(source["rows"]), args["hesitation_jitter_s"],
                         args["bounce_deg"], args["bounce_jitter_deg"])
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


def p33_forecast(measurements, chain_a_plan, chain_b, target_length_s=110.6):
    old_len = float(measurements["law"]["segment_end"]) / float(measurements["tick"])
    scale = float(target_length_s) / old_len
    by_guid = {r["cue_guid"]: r for r in measurements["rows"]}
    impacts_a = _chain_a_impact_times(chain_a_plan)
    shifted_a = []
    for row, impact in zip(chain_a_plan["chain"]["rows"], impacts_a):
        pass_s = float(by_guid[row["cue_guid"]]["pass_frame"]) / float(measurements["tick"])
        delta = pass_s * (scale - 1.0)
        shifted_a.append({"label": row["label"], "old_impact_s": impact,
                          "predicted_impact_s_if_phase_fields_unchanged": impact + delta,
                          "shift_s": delta})
    b_slam = None if not chain_b else float(chain_b["timing"]["final_impact_s"])
    return {
        "authority": "P33 proportionally scales LeadIn/intervals/Tail; Choreo keys keep seconds from Passage start",
        "old_length_s": old_len,
        "target_length_s": float(target_length_s),
        "timing_scale": scale,
        "chain_a": shifted_a,
        "chain_a_consequence": "row-specific PassFrame shifts fracture the contact timing unless A is re-solved after P33",
        "chain_b_slam_s": b_slam,
        "chain_b_past_new_end": b_slam is not None and b_slam > float(target_length_s),
        "chain_b_consequence": ("122 s slam/dust/sound would be past the 110.6 s P06 end" if b_slam is not None
                                else "blocked plan remains blocked; any 122 s candidate would be past the new end"),
        "choreo_consequence": "dust and slam audio remain at their authored P06-relative seconds and would desynchronise",
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


def build_plan(measurements, chain_a_plan, chain_a_active, asset_inventory, raw_args, topple_core):
    args, errors = validate_args(raw_args)
    require(measurements.get("dry_ok") is True, "TOPPLE_MEASUREMENTS_NOT_DRY_OK")
    adopted_a = adopt_chain_a(chain_a_plan, chain_a_active)
    protected = adopted_a["row_guids"]
    chosen, suffix_table, reduction = choose_suffix(measurements["rows"], args["n"], args["side"], protected)
    blockers = list(errors)
    chain_b = None
    dust = []
    inputs = None
    inputs_hash = None
    if chosen is None:
        blockers.append("CHAIN_B_SUFFIX_REFUSED|%s" % reduction)
    else:
        chain_b, inputs, inputs_hash, dust, timing_refusals = build_chain_b(measurements, chosen, args, topple_core)
        blockers += timing_refusals
        require_disjoint(chain_a_plan["chain"]["rows"], chain_b["rows"])
    tick = float(measurements["tick"])
    camera_at_candidate_slam = topple_core.distance_at_frame(measurements["law"], args["slam_s"] * tick)
    final_hinge = float(measurements["rows"][-1]["sides"][args["side"]]["hinge_route_cm"])
    candidate_slam = {"time_s": args["slam_s"], "camera_cm": camera_at_candidate_slam,
                      "last_row_hinge_cm": final_hinge,
                      "last_row_ahead_cm": final_hinge - camera_at_candidate_slam,
                      "finish_limit_s": float(measurements["law"]["segment_end"]) / tick - args["end_margin_s"]}
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
        restyle = restyle_chain_a(chain_a_plan, measurements, args, topple_core)
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
        "p33_forecast": p33_forecast(measurements, chain_a_plan, chain_b),
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
