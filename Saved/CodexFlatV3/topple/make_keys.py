"""MAKE KEYS (offline, system Python + numpy): DRY measurements -> topple_plan.json (STILL + CHAIN) for APPLY.

  python make_keys.py --slam-s 37 [--n 6] [--end braced|floor] [--candidate auto|<k>] [--side L|R]
                      [--lead-min-m 25] [--lead-max-m 35] [--keeper <ordinal>|none] [--parts still,chain]
  python make_keys.py --lead-m 30 --candidate <k> ...          (time by camera lead instead of slam time)
  python make_keys.py --parts still                              (STILL only, no chain)

Inputs: topple_measurements.json (topple_apply.py DRY, live). Solver: topple_chain.py (N slabs, measured per-row
heights, per-gap spacing and contact thickness; extends the 7 Oct topple_solver.py). Sunset: the daylight timeline in
Saved/CodexConductor/p06_sunset_dry.json [meas, the 7 Oct sunset DRY] -- reported only, never gates.

Window choice (--candidate auto): every DRY-eligible window of n consecutive rows (either side, or --side) is solved;
for --slam-s the creak is placed so the chain's FINAL impact lands at slam-s, which fixes the camera lead at the creak;
windows whose lead lies in [lead-min, lead-max] are ranked by |lead - mid|, then by frame share at the final impact.
None in range -> gates fail (NO_WINDOW_FOR_SLAM) and the table shows, per window, the lead at slam-s and the slam time
a mid-range lead would give.
End: "braced" (default) = the last slab stops on the next same-side row, held static by STILL; "floor" = it falls
flat THROUGH the standing panels within its height (needs ack_next_row_intersection at APPLY).
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SUNSET_DRY = os.path.join(PROJECT, "Saved", "CodexConductor", "p06_sunset_dry.json")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # @dataclass needs its module registered (offline process only)
    spec.loader.exec_module(mod)
    return mod


core = _load("topple_core_mk", os.path.join(HERE, "topple_core.py"))
tc = _load("topple_chain_mk", os.path.join(HERE, "topple_chain.py"))
SOLVER = tc.SOLVER
MAX_FIT_ERR_DEG = 0.5
_CACHE = {}


def solve_window(win, end):
    rows = list(zip(win["heights_cm"], win["hinge_route_cm"], win["thickness_cm"]))
    brace = None
    if end == "braced":
        b = win.get("brace")
        core.require(b is not None and b.get("reached"), "BRACED_END_IMPOSSIBLE: no next same-side row in reach")
        core.require(not b.get("problem"), "BRACE_PROBLEM: %s" % b.get("problem"))
        brace = {"hinge_m": b["hinge_route_cm"] / 100.0, "thickness_m": b["thickness_cm"] / 100.0}
    key = (tuple((round(h, 1), round(x - rows[0][1], 1), round(t, 1)) for h, x, t in rows),
           None if brace is None else (round(brace["hinge_m"] * 100 - rows[0][1], 1), round(brace["thickness_m"], 3)))
    if key not in _CACHE:
        _CACHE[key] = tc.run_chain([h / 100.0 for h, _, _ in rows], [x / 100.0 for _, x, _ in rows],
                                   [t / 100.0 for _, _, t in rows], brace)
    return _CACHE[key]


def window_eval(meas, win, end, slam_s=None, lead_cm=None, sunset=None):
    inputs = core.inputs_for(meas, win, None)
    res = solve_window(win, end)
    if slam_s is not None:
        creak = core.creak_for_slam(inputs, slam_s, res["final_impact_s"])
    else:
        creak = core.creak_for_lead(inputs, lead_cm)
    tm = core.timing(inputs, res["rows"], res["t_end"], creak, res["events"])
    tick = float(inputs["tick"])
    law = {"points": [tuple(p) for p in inputs["law_points"]]}
    cam_m = lambda t: core.distance_at_frame(law, creak + t * tick) / 100.0
    hinge_m = [h / 100.0 for h in win["hinge_route_cm"]]
    heights_m = [h / 100.0 for h in win["heights_cm"]]
    inner = [x / 100.0 for x in win["lateral_inner_cm"]]
    width = [x / 100.0 for x in win["lateral_width_cm"]]
    t_imp = res["final_impact_s"]
    at = tc.coverage(res, hinge_m, heights_m, inner, width, cam_m, t_imp, t_imp)
    fall = tc.coverage(res, hinge_m, heights_m, inner, width, cam_m, 1.55, t_imp, step=0.25)
    tm["frame_share_at_final_impact"] = round(at[0][2], 4) if at else 0.0
    tm["mean_frame_share_release_to_final_impact"] = round(sum(x[2] for x in fall) / max(1, len(fall)), 4)
    tm["chain_inner_edge_m"] = min(inner)
    if sunset:
        for name in ("creak", "final_impact", "rest"):
            s = tm.get(name + "_s")
            if s is not None:
                tm["daylight_at_" + name] = round(core.daylight_at(sunset, s), 3)
    return inputs, res, tm


def build(meas, slam_s=None, lead_cm=None, candidate="auto", n=core.N_ROWS, end="braced", side=None,
          lead_min_cm=2500.0, lead_max_cm=3500.0, keeper="default", parts=("still", "chain"), sunset=None):
    core.require(meas.get("dry_ok") is True, "DRY_NOT_OK")
    probe = meas.get("api_probe") or {}
    core.require(probe.get("pass") is True, "API_PROBE_NOT_PASSED: %s" % probe.get("failures"))
    parts = tuple(p for p in ("still", "chain") if p in parts)
    core.require(parts, "NO_PARTS")
    rows, tick = meas["rows"], float(meas["tick"])
    by = {r["cue_guid"]: r for r in rows}
    if keeper == "default":
        k = core.default_keeper(rows, tick)
        keeper_guid = k["cue_guid"] if k else None
    elif keeper in (None, "none"):
        keeper_guid = None
    else:
        keeper_guid = rows[int(keeper)]["cue_guid"]
    refusals, table, chosen = [], [], None
    mod = meas["modulation"]
    for flag, why in (("wing_modulation", "WING_MODULATION_AUTHORED"), ("speed_shaped", "CAMERA_SPEED_SHAPED"),
                      ("longitudinal_offset", "CAMERA_LONGITUDINAL_OFFSET_AUTHORED")):
        if mod.get(flag):
            refusals.append("%s: %s" % (why, mod.get(flag)))
    chain = None
    if "chain" in parts:
        core.require((slam_s is None) != (lead_cm is None), "GIVE_ONE_OF --slam-s | --lead-m")
        wins, counts = core.eligible_windows(rows, n, keeper_guid)
        if side:
            wins = [w for w in wins if w["side"] == side]
        if end == "braced":
            wins = [w for w in wins if w.get("brace") and w["brace"].get("reached") and not w["brace"].get("problem")]
        if candidate != "auto":
            wins = [w for w in wins if w["start_ordinal"] == int(candidate)]
            core.require(wins, "CANDIDATE_NOT_ELIGIBLE: %s (side %s, end %s)" % (candidate, side, end))
        mid = (lead_min_cm + lead_max_cm) / 2.0
        for w in wins:
            inputs, res, tm = window_eval(meas, w, end, slam_s, lead_cm, sunset)
            lead = tm["lead_cm_at_creak"]
            row = {"side": w["side"], "start_ordinal": w["start_ordinal"], "labels": w["labels"],
                   "lead_m_at_creak": round(lead / 100.0, 2), "creak_s": round(tm["creak_s"], 2),
                   "final_impact_s": round(tm.get("final_impact_s", float("nan")), 2),
                   "frame_share_at_final_impact": tm["frame_share_at_final_impact"],
                   "refusals": tm["refusals"]}
            if slam_s is not None:   # what a mid-range lead would give for this window
                creak_mid = core.creak_for_lead(inputs, mid) if inputs["rows"][0]["hinge_route_cm"] >= mid else None
                row["final_impact_s_at_mid_lead"] = None if creak_mid is None else round(
                    creak_mid / tick + res["final_impact_s"], 2)
            table.append(row)
            in_range = lead_min_cm <= lead <= lead_max_cm or candidate != "auto" or lead_cm is not None
            if in_range and not tm["refusals"]:
                score = (abs(lead - mid), -tm["frame_share_at_final_impact"])
                if chosen is None or score < chosen[0]:
                    chosen = (score, w, inputs, res, tm)
        if chosen is None:
            refusals.append("NO_WINDOW_FOR_SLAM: no eligible %d-row window (end=%s) has a creak lead in [%.0f, %.0f] m "
                            "for a final impact at %s s -- see table" % (n, end, lead_min_cm / 100, lead_max_cm / 100,
                                                                         slam_s))
        else:
            _, w, inputs, res, tm = chosen
            prow = []
            for k, (r, s, t) in enumerate(zip(inputs["rows"], res["rows"], tm["rows"])):
                if s["fit_max_err_deg"] > MAX_FIT_ERR_DEG:
                    refusals.append("FIT_ERROR row %d %.2f deg" % (k, s["fit_max_err_deg"]))
                keys = core.plan_keys(s["keys"])
                other = "R" if w["side"] == "L" else "L"
                prow.append({"fall_order": k, "cue_guid": r["cue_guid"], "show_index": r["show_index"],
                             "label": r["label"], "side": w["side"], "has_top": r["has_top"], "action": "chain",
                             "set": {"kind": "TOPPLE", "playback_mode": "ONE_SHOT", "phase_origin": "PASS_FRAME",
                                     "cycle_rate_hz": t["CycleRateHz"], "phase_offset_cycles": t["PhaseOffsetCycles"],
                                     "max_angle_deg": core.MAX_ANGLE_DEG,
                                     "top_follows_mechanism": False if r["has_top"] else None},
                             "keys": keys, "curve_text": core.curve_text(keys),
                             "other_side": other, "other_keys": core.flat_keys(),
                             "other_curve_text": core.curve_text(core.flat_keys()),
                             "samples": [[ph, core.hermite(keys, ph)] for ph in core.sample_phases(keys)],
                             "timing": t, "final_deg": s["final_deg"], "fit_max_err_deg": s["fit_max_err_deg"]})
            chain = {"side": w["side"], "start_ordinal": w["start_ordinal"], "n": n, "end": end, "rows": prow,
                     "brace": w.get("brace"), "next_row_hits": w["floor_end_hits"] if end == "floor" else [],
                     "events": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in e.items()}
                                for e in res["events"]],
                     "t_end_s": res["t_end"], "gaps_m": res["gaps_m"], "contact_c_m": res["contact_c_m"],
                     "contact_deg": res["contact_deg"], "timing": tm, "flags": w["flags"]}
            refusals += tm["refusals"]
    chain_guids = [r["cue_guid"] for r in chain["rows"]] if chain else []
    still, still_ref = (core.still_plan(rows, keeper_guid, set(chain_guids)) if "still" in parts else ([], []))
    refusals += still_ref
    inputs = core.inputs_for(meas, ({"side": chain["side"], "cue_guids": chain_guids, "brace": chain["brace"]}
                                    if chain else None), keeper_guid)
    h = core.inputs_hash(inputs)
    with open(SOLVER, "rb") as fh:
        solver_sha = hashlib.sha256(fh.read()).hexdigest()
    keeper_row = by.get(keeper_guid)
    doc = {"tool": "make_keys.py", "made": datetime.datetime.now().isoformat(timespec="seconds"),
           "dry_run_id": meas["run_id"], "parts": list(parts), "inputs": inputs, "inputs_hash": h,
           "confirm_token": core.confirm_token(parts, chain["side"] if chain else None, chain_guids, h),
           "keeper": None if keeper_row is None else {
               "cue_guid": keeper_guid, "label": keeper_row["label"], "ordinal": keeper_row["ordinal"],
               "pass_s": round(keeper_row["pass_frame"] / tick, 2), "station_cm": round(keeper_row["station_cm"], 1),
               "mechanism": keeper_row["mechanism"],
               "meshes": [keeper_row["sides"][s].get("mesh") for s in core.SIDES]},
           "still": still, "still_counts": {a: sum(1 for x in still if x["action"] == a)
                                            for a in ("still", "already_still", "keep", "chain")},
           "chain": chain, "window_table": table, "solver": {"path": SOLVER, "sha256": solver_sha,
                                                             "extension": os.path.join(HERE, "topple_chain.py")},
           "request": {"slam_s": slam_s, "lead_cm": lead_cm, "n": n, "end": end, "side": side,
                       "candidate": candidate, "lead_range_cm": [lead_min_cm, lead_max_cm]},
           "refusals": refusals, "gates_ok": not refusals}
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--measurements", default=os.path.join(HERE, "topple_measurements.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "topple_plan.json"))
    ap.add_argument("--slam-s", type=float, default=None)
    ap.add_argument("--lead-m", type=float, default=None)
    ap.add_argument("--n", type=int, default=core.N_ROWS)
    ap.add_argument("--end", choices=("braced", "floor"), default="braced")
    ap.add_argument("--candidate", default="auto")
    ap.add_argument("--side", choices=("L", "R"), default=None)
    ap.add_argument("--lead-min-m", type=float, default=25.0)
    ap.add_argument("--lead-max-m", type=float, default=35.0)
    ap.add_argument("--keeper", default="default")
    ap.add_argument("--parts", default="still,chain")
    a = ap.parse_args(argv)
    with open(a.measurements, "r", encoding="utf-8") as fh:
        meas = json.load(fh)
    sunset = None
    if os.path.exists(SUNSET_DRY):
        with open(SUNSET_DRY, "r", encoding="utf-8") as fh:
            sunset = json.load(fh).get("timeline")
    doc = build(meas, a.slam_s, None if a.lead_m is None else a.lead_m * 100.0, a.candidate, a.n, a.end, a.side,
                a.lead_min_m * 100.0, a.lead_max_m * 100.0, a.keeper, tuple(a.parts.split(",")), sunset)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print("TOPPLE_PLAN|out=%s|parts=%s|gates_ok=%s|still=%s" % (a.out, "+".join(doc["parts"]), doc["gates_ok"],
                                                                doc["still_counts"]))
    if doc["keeper"]:
        print("  keeper: %s (ordinal %d, camera passes %.1f s) %s" % (doc["keeper"]["label"], doc["keeper"]["ordinal"],
                                                                     doc["keeper"]["pass_s"], doc["keeper"]["meshes"]))
    for r in doc["window_table"]:
        print("  window %s%02d lead %6.1f m creak %6.2f s impact %6.2f s share %.3f%s %s" % (
            r["side"], r["start_ordinal"], r["lead_m_at_creak"], r["creak_s"], r["final_impact_s"],
            r["frame_share_at_final_impact"],
            "" if r.get("final_impact_s_at_mid_lead") is None else " (mid-lead impact %.2f s)" % r["final_impact_s_at_mid_lead"],
            r["refusals"] or ""))
    c = doc["chain"]
    if c:
        tm = c["timing"]
        print("  CHAIN %s rows %s, end=%s brace=%s" % (c["side"], ",".join(r["label"] for r in c["rows"]), c["end"],
                                                       (c["brace"] or {}).get("label")))
        print("  creak %.2f s (lead %.1f m), final %s %.2f s, rest %.2f s; daylight creak/impact/rest %s/%s/%s" % (
            tm["creak_s"], tm["lead_cm_at_creak"] / 100, tm.get("final_impact_type"), tm.get("final_impact_s", -1),
            tm["rest_s"], tm.get("daylight_at_creak"), tm.get("daylight_at_final_impact"), tm.get("daylight_at_rest")))
        print("  at the final impact: row0 %.1f m ahead, last row %.1f m ahead, summed per-slab frame share %.3f (mean %.3f in fall; overlaps count twice)" % (
            tm["row0_ahead_cm_at_final_impact"] / 100, tm["last_row_ahead_cm_at_final_impact"] / 100,
            tm["frame_share_at_final_impact"], tm["mean_frame_share_release_to_final_impact"]))
        for r in c["rows"]:
            print("    %s rate=%.6f Hz offset=%.4f cycles keys=%d fit=%.2f deg final=%.1f deg" % (
                r["label"], r["set"]["cycle_rate_hz"], r["set"]["phase_offset_cycles"], len(r["keys"]),
                r["fit_max_err_deg"], r["final_deg"]))
        for x in c["next_row_hits"]:
            print("  FLOOR END HITS: %s" % x)
    for x in doc["refusals"]:
        print("  REFUSAL: " + x)
    print('APPLY args: {"mode": "APPLY", "confirm": "APPLY TOPPLE %s", "decided_by": "<Gary ...>"%s}' % (
        doc["confirm_token"], ', "ack_next_row_intersection": true' if c and c["next_row_hits"] else ""))
    return 0 if doc["gates_ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
