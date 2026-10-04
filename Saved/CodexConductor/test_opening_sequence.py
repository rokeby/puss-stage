"""Offline harness for the long Opening (opening_sequence_plan.py). System Python, no Unreal.

Every rule has a positive case AND a negative control that must be caught. Exit code 0 only if all pass.
Two controls are anchored on MEASURED live state, not on the planner's own output:
  - curtain sections for today's release (1.9933 s, end 375) must equal the sections read live on 30 Sep
    (opening_hold_at_release_final13.json 'after');
  - the walk-in for today's Opening (end 15.0, ease 1.0, landed 6.3267) must equal the 376 keys keyed live on
    2 Oct (Saved/CodexCameraPilot/walkin_OPENING_record.json).
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import opening_sequence_plan as P  # noqa: E402

WALK = os.path.join(SAVED, "CodexCameraPilot", "walkin_plan.py")
CFG = P.load_json(os.path.join(HERE, "opening_timing.json"))
AN = P.load_json(os.path.join(SAVED, CFG["analysis"]))
RESULTS = []


def case(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  :: " + str(detail)))


def plan_with(mutate=None, markers=None, last=None):
    cfg = copy.deepcopy(CFG)
    if mutate:
        mutate(cfg)
    return P.build_plan(cfg, AN, WALK, markers, last), cfg


def has(fails, prefix):
    return any(f.startswith(prefix) for f in fails)


base, _ = plan_with()
fr, sec = base["frames"], base["seconds"]
print("phase table:", json.dumps(sec))
case("default plan has no failures", base["failures"] == [], base["failures"])

# ---- 1. envelope follows the analysis
rate, inten, rms, dur = P.music_curves(AN)
w = int(round(CFG["envelope"]["smoothing_s"] * rate))
ref = [0.5 * a / max(P.smooth(inten, w)) + 0.5 * b / max(P.smooth(rms, w))
       for a, b in zip(P.smooth(inten, w), P.smooth(rms, w))]
env = base["envelope"]["series"]
r_pos = P.pearson(env, ref)
case("envelope correlates with the smoothed analysis curves (r >= 0.98)", r_pos >= 0.98, r_pos)
shift = int(30 * rate)
r_neg = P.pearson(env, ref[shift:] + ref[:shift])
case("NEG: the analysis shifted by 30 s does NOT match (r < 0.5)", r_neg < 0.5, r_neg)
r_raw = P.pearson(env, inten)
case("envelope still tracks the RAW intensity curve (r >= 0.5)", r_raw >= 0.5, r_raw)
lamp = base["lamps"]["FOH L"]["intensity"]
env_keys = [(f, v) for f, v, i in lamp if fr["swivel_end"] < f < fr["walkin_start"]]
env_vals = [P.envelope_scale(P.env_at(f / 25.0, rate, env), CFG["envelope"]) for f, _ in env_keys]
r_lamp = P.pearson([v for _, v in env_keys], env_vals)
case("FOH L keys follow the envelope in phase 3 (r >= 0.999)", r_lamp >= 0.999 and len(env_keys) > 100, (r_lamp, len(env_keys)))
flat, _ = plan_with(lambda c: c["envelope"].__setitem__("gain", 0.0))
flat_keys = [v for f, v, i in flat["lamps"]["FOH L"]["intensity"] if fr["swivel_end"] < f < fr["walkin_start"]]
r_flat = P.pearson(flat_keys, env_vals[:len(flat_keys)])
case("NEG: gain 0 gives a flat lamp that does NOT follow the music (r < 0.5)", r_flat < 0.5, r_flat)
mx = max(v for f, v, i in lamp) / 1740.0
cap = CFG["envelope"]["floor"] + (CFG["envelope"]["peak"] - CFG["envelope"]["floor"]) * (1 - CFG["envelope"]["headroom"])
case("headroom: FOH L peak scale <= floor+(peak-floor)*(1-headroom) = %.3f" % cap, mx <= cap + 1e-9, mx)
hot, _ = plan_with(lambda c: c["envelope"].__setitem__("gain", 5.0))
mx_hot = max(v for f, v, i in hot["lamps"]["FOH L"]["intensity"]) / 1740.0
case("gain 5 clips at peak scale (<= %.2f), never above" % CFG["envelope"]["peak"], mx_hot <= CFG["envelope"]["peak"] + 1e-9, mx_hot)

# ---- 2. unlit before the music, flicker before swivel
case("unlit: every lamp is 0 before flicker_start", all(v == 0.0 for l in base["lamps"].values()
                                                      for f, v, i in l["intensity"] if f < fr["flicker_start"]))
case("music_start > frame 0 (an unactivated opening exists)", fr["music_start"] >= 1, fr["music_start"])
neg, _ = plan_with(lambda c: c["moments"].__setitem__("music_start", {"value": 0.0}))
case("NEG: music_start 0 is caught (unactivated)", has(neg["failures"], "unactivated"), neg["failures"])
case("flicker ends before the swivel starts", fr["flicker_end"] <= fr["swivel_start"] < fr["swivel_end"])
neg, _ = plan_with(lambda c: c["moments"].__setitem__("swivel_start", {"value": 3.0}))
case("NEG: swivel_start inside the flicker is caught", has(neg["failures"], "flicker-before-swivel"), neg["failures"])
fl = [(f, v) for f, v, i in base["lamps"]["FOH L"]["intensity"] if fr["flicker_start"] <= f <= fr["flicker_end"]]
case("flicker really stutters (>= 4 on/off changes)", sum(1 for a, b in zip(fl, fl[1:]) if (a[1] == 0) != (b[1] == 0)) >= 4, fl[:12])
again, _ = plan_with()
case("deterministic: a second build gives identical lamp keys",
     json.dumps(again["lamps"], sort_keys=True) == json.dumps(base["lamps"], sort_keys=True))
seed2, _ = plan_with(lambda c: c["flicker"].__setitem__("seed", "OTHER"))
case("NEG: a different seed changes the stutter (the determinism check can fail)",
     json.dumps(seed2["lamps"]["FOH L"]["intensity"][:30]) != json.dumps(base["lamps"]["FOH L"]["intensity"][:30]))
rot = base["lamps"]["FOH L"]["rotation"]
case("FOH L swivels from its park to the warmer aim (-19.801, 21.919) at swivel_end",
     rot[-1][0] == fr["swivel_end"] and abs(rot[-1][1] + 19.801) < 1e-9 and abs(rot[-1][2] - 21.919) < 1e-9 and rot[1][1:] == rot[0][1:], rot)

# ---- 3. curtain: after the last swell, inside the final quarter; bake unchanged
fq = 0.75 * base["track_s"]
rel = base["curtain"]["release_s"]
case("release %.3f after last swell %.3f" % (rel, sec["last_swell"]), rel > sec["last_swell"])
case("release %.3f inside the final quarter (>= %.3f)" % (rel, fq), rel >= fq)
case("release lands within half a frame of curtain_release", abs(rel - sec["curtain_release"]) <= 0.5 / 25 + 1e-9,
     (rel, sec["curtain_release"]))
neg, _ = plan_with(lambda c: c["moments"].__setitem__("curtain_release", {"value": 60.0}))
case("NEG: release at 60 s is caught (final quarter + last swell)",
     has(neg["failures"], "release-in-final-quarter") and has(neg["failures"], "release-after-last-swell"), neg["failures"])
neg, _ = plan_with(lambda c: c["moments"].__setitem__("last_swell", {"value": 85.0}) or
                   c["moments"].__setitem__("curtain_release", {"value": 80.0}))
case("NEG: a release before an explicitly later last swell is caught", has(neg["failures"], "release-after-last-swell"),
     neg["failures"])
s = base["curtain"]["sections"]
case("bake unchanged: FALL is 250 frames from offset 23200 ticks, HOLD/PILE one-tick windows",
     s[1][1] - s[1][0] == 250 and s[1][2] == 23200 and s[0][2] == 23200 and s[0][3] == 240799 and s[2][2] == 263999, s)
today, _, _ = P.curtain_sections(1.9933333333333332, 375, CFG, 25.0)
measured = P.load_json(os.path.join(SAVED, "CodexSoftGoods", "opening_hold_at_release_final13.json"))["after"]
case("CONTROL(measured): today's release + end reproduce the live sections of 30 Sep", today == measured, (today, measured))
case("landed = release + 130/30 s (bake frames 480->610)", abs(base["curtain"]["landed_s"] - rel - 130 / 30.0) < 1e-9)
case("curtain has landed before the walk-in starts", base["curtain"]["landed_s"] <= sec["walkin_start"])

# ---- 4. walk-in ends exactly at the new P01 start
wk = base["walkin"]["keys"]
p01_start_s = fr["opening_end"] / 25.0
case("walk-in last key at opening_end = new P01 start %.2f s" % p01_start_s, abs(wk[-1][0] - p01_start_s) < 1e-12, wk[-1])
case("walk-in last key is P01's start pose (0,0,150) at 25 mm / 600 cm",
     wk[-1][1:4] == (0.0, 0.0, 150.0) and wk[-1][7] == 25.0 and wk[-1][8] == 600.0, wk[-1])
case("walk-in keys start at frame 0 (seat hold) and are on the frame grid",
     wk[0][0] == 0.0 and all(abs(k[0] * 25 - round(k[0] * 25)) < 1e-9 for k in wk))
case("walk-in passes Look & camera's check_plan (arrival speed, pile, monotone)", base["walkin"]["failures"] == [],
     base["walkin"]["failures"])
case("Master grows by %.2f s (P01 15.0 -> %.2f)" % (base["master_delta_s"], p01_start_s),
     abs(base["master_delta_s"] - (p01_start_s - 15.0)) < 1e-9)
tamper = copy.deepcopy(base)
tamper["walkin"]["keys"][-1] = (tamper["walkin"]["keys"][-1][0] - 0.04,) + tuple(tamper["walkin"]["keys"][-1][1:])
case("NEG: a walk-in ending one frame early is caught", has(P.validate(tamper, CFG), "walkin-ends-at-p01-start"))
moved, _ = plan_with(lambda c: c["moments"].__setitem__("opening_end", {"value": 100.0}))
case("opening_end moved to 100 s: walk-in follows it exactly", abs(moved["walkin"]["keys"][-1][0] - 100.0) < 1e-12
     and moved["failures"] == [], moved["failures"])
try:
    plan_with(lambda c: c["moments"].__setitem__("walkin_start", {"value": 93.0}))
    case("NEG: a walk shorter than d/v (5.6 s) is refused", False, "no error")
except ValueError as exc:
    case("NEG: a walk shorter than d/v (5.6 s) is refused", "outside" in str(exc), exc)
try:
    plan_with(lambda c: c["moments"].__setitem__("walkin_start", {"value": 84.0}))
    case("NEG: a walk longer than 2d/v (11.2 s) is refused", False, "no error")
except ValueError as exc:
    case("NEG: a walk longer than 2d/v (11.2 s) is refused", "outside" in str(exc), exc)
# control: today's Opening walk (end 15.0, ease 1.0) reproduces the 2 Oct keys exactly
plan_walk, check_plan = P.load_walkin_planner(WALK)
w = CFG["walkin"]
k15, _ = plan_walk(w["seat"], w["target"], w["v_end_cm_s"], 1.0, 15.0, 25.0, w["focal0_mm"], w["focal1_mm"],
                   w["focus0_cm"], w["focus1_cm"], 6.326666666666666, w["pile_edge_cm"])
rec = P.load_json(os.path.join(SAVED, "CodexCameraPilot", "walkin_OPENING_record.json"))["keys"]
same = len(k15) == len(rec) and all(max(abs(a - b) for a, b in zip(x, y)) < 1e-6 for x, y in zip(k15, rec))
case("CONTROL(measured): today's walk plan == the 376 keys keyed live on 2 Oct", same, (len(k15), len(rec)))
comp = P.compress_walk_keys(k15)
case("compression keeps every moving key and the end (%d -> %d keys)" % (len(k15), len(comp)),
     comp[0] == k15[0] and comp[-1] == k15[-1] and all(k in comp for k in k15 if k[1:] != k15[0][1:]))

# ---- 5. manual marker move respected (and conflicts refused)
last = {n: fr[n] for n in P.INPUT_MOMENTS}
markers = P.markers_to_moments(P.marker_list(base))
case("markers round-trip every input moment", all(markers[n] == fr[n] for n in P.INPUT_MOMENTS))
m2 = dict(markers, curtain_release=fr["curtain_release"] + 50)
p2, _ = plan_with(markers=m2, last=last)
case("a marker dragged +50 frames wins over the unchanged JSON", p2["frames"]["curtain_release"] == fr["curtain_release"] + 50
     and p2["sources"]["curtain_release"] == "sequencer" and p2["writeback"] == {"curtain_release": fr["curtain_release"] + 50},
     (p2["frames"]["curtain_release"], p2["sources"]["curtain_release"], p2["writeback"]))
case("the dragged release moves the GC FALL by exactly 50 frames",
     p2["curtain"]["sections"][1][0] - base["curtain"]["sections"][1][0] == 50)
case("other moments unchanged by the drag", all(p2["frames"][n] == fr[n] for n in P.INPUT_MOMENTS if n != "curtain_release"))
p3, _ = plan_with(lambda c: c["moments"].__setitem__("curtain_release", {"value": 76.0}), markers=markers, last=last)
case("a JSON edit with an untouched marker: the JSON wins", p3["frames"]["curtain_release"] == 1900
     and p3["sources"]["curtain_release"] == "json", (p3["frames"]["curtain_release"], p3["sources"]["curtain_release"]))
p4, _ = plan_with(lambda c: c["moments"].__setitem__("curtain_release", {"value": 76.0}), markers=m2, last=last)
case("NEG: marker AND JSON both moved differently -> conflict, refused", has(p4["failures"], "marker-conflict"), p4["failures"])
m5 = {k: v for k, v in markers.items() if k != "swivel_end"}
p5, _ = plan_with(markers=m5, last=last)
case("a deleted marker falls back to the JSON (and is recreated)", p5["frames"]["swivel_end"] == fr["swivel_end"]
     and "missing" in p5["sources"]["swivel_end"])
m6 = dict(markers, walkin_start=fr["walkin_start"] + 25)
p6, _ = plan_with(markers=m6, last=last)
case("dragging walkin_start 1 s later re-solves the ease and still ends at P01 start",
     abs(p6["walkin"]["start_s"] - (sec["walkin_start"] + 1.0)) < 1e-6 and p6["walkin"]["keys"][-1][0] == wk[-1][0]
     and p6["failures"] == [], (p6["walkin"]["start_s"], p6["failures"]))
p7, _ = plan_with(markers=dict(markers, curtain_release=fr["final_quarter"] - 100), last=last)
case("NEG: a marker dragged out of the final quarter is still validated (refused)",
     has(p7["failures"], "release-in-final-quarter"), p7["failures"])
p8, _ = plan_with(markers=dict(markers, music_start=fr["music_start"] + 25), last=last)
case("dragging music_start drags the auto flicker_start with it? NO: flicker_start is its own marker (unchanged)",
     p8["frames"]["flicker_start"] == fr["flicker_start"] and p8["frames"]["music_start"] == fr["music_start"] + 25)

# ---- 6. revert exact (state algebra the live tool mirrors)
orig = {
    "playback_end": 375, "cut_end": 375, "drape_spawn_end": 375,
    "gc_sections": measured,
    "walkin_keys": [list(k) for k in rec],
    "markers": [["Gary note", 120]],
    "rig": {},
    "music_on_opening": False,
}
after = P.apply_to_state(orig, base, CFG)
case("APPLY changes the owned fields", after["playback_end"] == fr["opening_end"] and after["gc_sections"] != orig["gc_sections"]
     and len(after["rig"]) == 3)
case("APPLY keeps a foreign marker", ["Gary note", 120] in after["markers"])
back = P.revert_state(after, orig)
case("REVERT(APPLY(original)) == original exactly", json.dumps(back, sort_keys=True) == json.dumps(orig, sort_keys=True))
reapplied = P.apply_to_state(P.apply_to_state(orig, base, CFG), p2, CFG)
case("re-APPLY over an APPLY then REVERT still returns the original",
     json.dumps(P.revert_state(reapplied, orig), sort_keys=True) == json.dumps(orig, sort_keys=True))
bad_orig = copy.deepcopy(orig)
bad_orig["gc_sections"][0][1] = 50
case("NEG: reverting to a wrong snapshot is detected as different",
     json.dumps(P.revert_state(after, bad_orig), sort_keys=True) != json.dumps(orig, sort_keys=True))
new_marker_state = dict(after, markers=after["markers"] + [["Another note", 900]])
back2 = P.revert_state(new_marker_state, orig)
case("REVERT keeps a marker Gary added after APPLY", ["Another note", 900] in back2["markers"])

# ---- 7. shorter-than-today and music fit
try:
    plan_with(lambda c: c["moments"].__setitem__("opening_end", {"value": 80.0}))
    case("NEG: an Opening shorter than the track is refused", False, "no error")
except ValueError as exc:
    case("NEG: an Opening shorter than the track is refused (FALL/walk cannot fit)", True, exc)
short, _ = plan_with(lambda c: [c["moments"].__setitem__(k, {"value": v}) for k, v in
                                (("opening_end", 92.0), ("walkin_start", 84.0))])
case("NEG: opening_end 92 s (track 96.34 s) fails music-fits", has(short["failures"], "music-fits"), short["failures"])

passed = sum(1 for _, ok in RESULTS if ok)
print("\nRESULT %d/%d passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
