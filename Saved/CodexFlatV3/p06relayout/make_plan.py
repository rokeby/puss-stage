"""OFFLINE planner (system Python + numpy + matplotlib): the 7 Oct P06 relayout from the recorded topple DRY.

  python make_plan.py [--slam-s 37] [--out relayout_plan_offline.json] [--png p06_relayout_contact_sheet.png]

Inputs [meas]: ../topple/topple_measurements.json (DRY TOPPLE-20261007-024310, the pre-STILL live P06),
Saved/CodexConductor/p06_sunset_dry.json (daylight timeline). Asset existence is SIMULATED from the realism build
reports (relayout_core.DESIGNS "built"); the live DRY resolves against the editor instead.

It then proves, offline, that the existing topple tool will find the chain window on the planned layout: it builds a
synthetic topple measurement (relayout_core.synth_topple_rows) and runs topple_core.eligible_windows and
make_keys.build exactly as topple's own DRY/make_keys would, for both height readings the live DRY may make.
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TOPPLE = os.path.join(PROJECT, "Saved", "CodexFlatV3", "topple")
SUNSET = os.path.join(PROJECT, "Saved", "CodexConductor", "p06_sunset_dry.json")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rc = _load("relayout_core_offline", os.path.join(HERE, "relayout_core.py"))
tcore = _load("topple_core_rl", os.path.join(TOPPLE, "topple_core.py"))
mk = _load("make_keys_rl", os.path.join(TOPPLE, "make_keys.py"))


def sim_exists(path):
    name = path.rsplit("/", 1)[-1]
    for key, d in rc.DESIGNS.items():
        for v in d["built"]:
            if d["side"] and name == rc.asset_name(key, d["side"], v) and path.startswith(rc.DEFAULT_MESH_ROOTS[v]):
                return True
    return False


def rows_from_meas(meas):
    return [{"cue_guid": r["cue_guid"], "label": r["label"], "show_index": r["show_index"], "enabled": r["enabled"],
             "interval_ticks": r["interval_ticks"], "gap_cm": r["gap_cm"], "L_mesh": r["sides"]["L"]["mesh"],
             "R_mesh": r["sides"]["R"]["mesh"], "text_outside_mechanism_sha": "offline"} for r in meas["rows"]]


def settings_from_meas(meas):
    pts = meas["law"]["points"]
    return {"lead_in_frames": int(pts[1][0]), "lead_in_distance_cm": float(pts[1][1]),
            "tail_frames": int(pts[-1][0] - pts[-2][0]), "tail_distance_cm": float(pts[-1][1] - pts[-2][1]),
            "first_cue_guid": meas["rows"][0]["cue_guid"], "last_cue_guid": meas["rows"][-1]["cue_guid"]}


def topple_check(meas, plan, slam_s, height_mode, sunset):
    syn = rc.synth_topple_rows(meas, plan, height_mode)
    syn["dry_ok"] = True
    syn["api_probe"] = {"pass": True}
    keeper_ord = next(r["new_ordinal"] for r in plan["rows"] if r["role"] == "keeper")
    chain0 = next(r["new_ordinal"] for r in plan["rows"] if r["role"] == "chain1")
    wins, counts = tcore.eligible_windows(syn["rows"], 6, syn["rows"][keeper_ord]["cue_guid"])
    res = {"height_mode": height_mode, "eligible_windows": [(w["side"], w["start_ordinal"]) for w in wins],
           "refusal_counts": counts, "keeper_ordinal": keeper_ord, "chain_start_ordinal": chain0}
    default_keeper = tcore.default_keeper(syn["rows"], syn["tick"])
    res["default_keeper_would_be"] = None if default_keeper is None else default_keeper["label"]
    out = {}
    for label, cand in (("explicit", str(chain0)), ("auto", "auto")):
        try:
            doc = mk.build(syn, slam_s=slam_s, candidate=cand, side="L", keeper=str(keeper_ord),
                           parts=("still", "chain"), sunset=sunset)
        except Exception as exc:  # noqa: BLE001
            out[label] = {"error": "%s: %s" % (type(exc).__name__, exc)}
            continue
        c = doc["chain"] or {}
        tm = c.get("timing") or {}
        out[label] = {"gates_ok": doc["gates_ok"], "refusals": doc["refusals"], "start_ordinal": c.get("start_ordinal"),
                      "labels": [r["label"] for r in c.get("rows", [])], "brace": (c.get("brace") or {}).get("label"),
                      "brace_detail": c.get("brace"), "contact_deg": [round(x, 1) for x in c.get("contact_deg", [])],
                      "gaps_m": [round(x, 3) for x in c.get("gaps_m", [])],
                      "creak_s": tm.get("creak_s"), "lead_m": None if tm.get("lead_cm_at_creak") is None else tm["lead_cm_at_creak"] / 100.0,
                      "final_impact_s": tm.get("final_impact_s"), "final_impact_type": tm.get("final_impact_type"),
                      "rest_s": tm.get("rest_s"), "daylight": [tm.get("daylight_at_creak"), tm.get("daylight_at_final_impact"),
                                                               tm.get("daylight_at_rest")],
                      "camera_cm_at_final_impact": tm.get("camera_cm_at_final_impact"),
                      "frame_share_at_final_impact": tm.get("frame_share_at_final_impact"),
                      "fit_err_deg": [r["fit_max_err_deg"] for r in c.get("rows", [])],
                      "events": [e for e in c.get("events", []) if e["type"] in ("release", "domino", "wall", "rest", "floor")],
                      "still_counts": doc["still_counts"], "window_table_top": sorted(
                          doc["window_table"], key=lambda w: abs(w["lead_m_at_creak"] - 30))[:4]}
    # default keeper trap: what make_keys does WITHOUT --keeper
    try:
        d2 = mk.build(syn, slam_s=slam_s, candidate=str(chain0), side="L", keeper="default", parts=("still", "chain"),
                      sunset=sunset)
        out["default_keeper"] = {"gates_ok": d2["gates_ok"], "refusals": d2["refusals"][:3],
                                 "keeper": (d2["keeper"] or {}).get("label")}
    except Exception as exc:  # noqa: BLE001
        out["default_keeper"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
    res["make_keys"] = out
    return res, syn


def contact_sheet(plan, check, sunset, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, (ax, axd) = plt.subplots(2, 1, figsize=(26, 11), gridspec_kw={"height_ratios": [5, 1.2]}, sharex=True)
    t_of = lambda cm: cm / rc.SPEED_CM_S
    # sunset bands (P06 seconds -> route metres at 2.5 m/s: camera position)
    for t0, t1, col, lab in ((0, 21.85, "#fff4c2", "full day"), (21.85, 37.0, "#ffd9a0", "sunset fade"),
                             (37.0, 52.1, "#c9b2d6", "dusk (below horizon)"), (52.1, 126.0, "#9a9aa8", "dark")):
        for a in (ax, axd):
            a.axvspan(t0 * 2.5, min(t1, 109.0 + 17) * 2.5, color=col, alpha=0.45, lw=0)
        ax.text((t0 + 0.4) * 2.5, 1460, lab, fontsize=9, color="#333")
    colours = {"swap": "#2b6cb0", "keep": "#888888"}
    for r in plan["rows"]:
        x = r["station_cm"] / 100.0
        for side, sgn in (("L", -1), ("R", 1)):
            s = r["sides"][side]
            mesh = s.get("mesh") or "?"
            name = mesh.rsplit("/", 1)[-1].replace("SM_FlatV3_P06_real_", "").replace("SM_FlatV3_P02_IND_", "IND ")
            col = colours.get(s["action"], "red")
            if rc.is_ind(mesh):
                col = "#b7791f"
            if r["role"] in rc.CHAIN_ROLES and side == "L":
                col = "#c53030"
            if r["role"] == "keeper":
                col = "#2f855a"
            ax.add_patch(Rectangle((x - 0.25, sgn * 450 if sgn > 0 else -450 - 500), 0.5, 500, color=col))
            ax.text(x, sgn * 1000 if sgn > 0 else -1000, name[:26], rotation=90, fontsize=6.5,
                    ha="center", va="bottom" if sgn > 0 else "top")
        ax.text(x, 0, "%d\n%.1fs" % (r["new_ordinal"] + 1, r["pass_s"]), ha="center", va="center", fontsize=6.5)
    mkx = check["make_keys"].get("explicit", {})
    if mkx.get("creak_s") is not None:
        cr, fi, re_ = mkx["creak_s"], mkx["final_impact_s"], mkx["rest_s"]
        for t, lab, c in ((cr, "creak (camera here)", "#c53030"), (fi, "FINAL SLAM (camera here)", "#9b2c2c"),
                          (re_, "rest", "#742a2a")):
            ax.axvline(t * 2.5, color=c, ls="--", lw=1)
            ax.text(t * 2.5 + 0.3, -1400 if lab.startswith("creak") else (-1300 if "SLAM" in lab else -1200),
                    "%s %.1f s" % (lab, t), color=c, fontsize=8)
        ax.annotate("", xy=(plan["rows"][mkx["start_ordinal"] + 5]["station_cm"] / 100 + 3, -1230),
                    xytext=(plan["rows"][mkx["start_ordinal"]]["station_cm"] / 100, -1230),
                    arrowprops={"arrowstyle": "->", "color": "#c53030", "lw": 2})
        ax.text(plan["rows"][mkx["start_ordinal"]]["station_cm"] / 100, -1160, "6-slab chain falls AWAY (L)",
                color="#c53030", fontsize=8)
    for r in plan["dropped"]:
        pass
    ax.set_ylim(-1500, 1550)
    ax.set_ylabel("lateral (cm, L negative)")
    ax.set_title("P06 relayout: %d -> %d rows, duration %.1f s unchanged; red = chain slabs, amber = IND fence/shutter "
                 "(kept), green = keeper (Wing 045, untouched), blue = V3 realism swap, grey = kept panel"
                 % (plan["count_old"], plan["count_new"], plan["duration_s"]), fontsize=11)
    if sunset:
        xs = [p["t"] * 2.5 for p in sunset]
        axd.plot(xs, [p["daylight"] for p in sunset], color="#c05621")
        axd.set_ylabel("daylight")
    axd.set_xlabel("camera route distance (m) = P06 seconds x 2.5 (lead-in: first 2.5 m in 1 s)")
    ticks = list(range(0, 281, 20))
    axd.set_xticks(ticks)
    axd.set_xticklabels(["%d m / %.0f s" % (m, m / 2.5) for m in ticks], fontsize=8)
    ax.set_xlim(-2, 280)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slam-s", type=float, default=37.0)
    ap.add_argument("--out", default=os.path.join(HERE, "relayout_plan_offline.json"))
    ap.add_argument("--png", default=os.path.join(HERE, "p06_relayout_contact_sheet.png"))
    a = ap.parse_args(argv)
    with open(os.path.join(TOPPLE, "topple_measurements.json"), "r", encoding="utf-8") as fh:
        meas = json.load(fh)
    sunset = None
    if os.path.exists(SUNSET):
        with open(SUNSET, "r", encoding="utf-8") as fh:
            sunset = json.load(fh).get("timeline")
    plan = rc.build_plan(rows_from_meas(meas), settings_from_meas(meas), exists=sim_exists)
    checks = {}
    for hm in ("socket", "bounds"):
        checks[hm], syn = topple_check(meas, plan, a.slam_s, hm, sunset)
    plan["topple_offline_check"] = checks
    plan["source_measurement_run"] = meas["run_id"]
    plan["slam_target_s"] = a.slam_s
    plan["gates_ok"] = not plan["refusals"]
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1)
    contact_sheet(plan, checks["socket"], sunset, a.png)
    print("P06_RELAYOUT_OFFLINE_PLAN|rows %d->%d|gates_ok=%s|law_dev=%.4f cm|duration=%.3f s|out=%s" % (
        plan["count_old"], plan["count_new"], plan["gates_ok"], plan["camera_law_max_dev_cm"], plan["duration_s"], a.out))
    for x in plan["refusals"]:
        print("  REFUSAL " + x)
    for r in plan["rows"]:
        print("  %2d %-10s %6d cm %6.2f s %-38s L:%-6s %-44s R:%-6s %s" % (
            r["new_ordinal"] + 1, r["role"], r["station_cm"], r["pass_s"], r["label"][:38], r["sides"]["L"]["action"],
            (r["sides"]["L"].get("mesh") or "").rsplit("/", 1)[-1][:44], r["sides"]["R"]["action"],
            (r["sides"]["R"].get("mesh") or "").rsplit("/", 1)[-1][:44]))
    for hm, c in checks.items():
        print("  TOPPLE CHECK (%s heights): eligible windows %s keeper ord %d (default keeper would be %s)" % (
            hm, c["eligible_windows"], c["keeper_ordinal"], c["default_keeper_would_be"]))
        for k, v in c["make_keys"].items():
            print("    %s: %s" % (k, json.dumps({kk: v.get(kk) for kk in ("gates_ok", "refusals", "start_ordinal", "brace",
                                                                         "contact_deg", "creak_s", "lead_m", "final_impact_s",
                                                                         "final_impact_type", "rest_s", "daylight", "error",
                                                                         "keeper")})))
    return 0 if plan["gates_ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
