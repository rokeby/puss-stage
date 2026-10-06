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
TR = CFG["envelope"].get("trend")


def trend_mult(f, frames=None):
    """Mirror of the planner's trend multiplier (5 Oct ~16:25): start -> end linearly over [from, to], held outside."""
    if not TR:
        return 1.0
    frames = frames or fr
    a, b = frames[TR["from"]], frames[TR["to"]]
    u = min(1.0, max(0.0, (f - a) / float(b - a)))
    return TR["start"] + (TR["end"] - TR["start"]) * u


# 5 Oct ~16:25: the lamp follows the TRENDED envelope (envelope x trend multiplier)
env_vals = [P.envelope_scale(P.env_at(f / 25.0, rate, env), CFG["envelope"]) * trend_mult(f) for f, _ in env_keys]
r_lamp = P.pearson([v for _, v in env_keys], env_vals)
# 5 Oct: key floor 100 -> 50. The flicker moved to the entry (36.18 s) pushes the auto swivel_end to 59.52 s, so
# phase 3 (swivel_end..walkin_start) is ~26 s = ~65 keys at 10-frame steps; the r test itself is unchanged.
case("FOH L keys follow the envelope in phase 3 (r >= 0.999)", r_lamp >= 0.999 and len(env_keys) > 50, (r_lamp, len(env_keys)))
# 5 Oct ~16:25: the control drops the trend too - a trended 'flat' lamp is a ramp that still correlates with the
# trended envelope (r 0.70 measured), which would hide whether the MUSIC is followed.
flat, _ = plan_with(lambda c: c["envelope"].__setitem__("gain", 0.0) or c["envelope"].pop("trend", None))
flat_keys = [v for f, v, i in flat["lamps"]["FOH L"]["intensity"] if fr["swivel_end"] < f < fr["walkin_start"]]
r_flat = P.pearson(flat_keys, env_vals[:len(flat_keys)])
case("NEG: gain 0 gives a flat lamp that does NOT follow the music (r < 0.5)", r_flat < 0.5, r_flat)
# 5 Oct: the headroom/clip rules are ENVELOPE caps, so they are measured after FOH L's flicker window. The strobe
# flicker (Gary 5 Oct ~15:15) pops up to peak_max x nominal INSIDE that window by design; the planner's own
# 'intensity-cap' rule bounds both (tested in section 9). With the old stutter the window never exceeded idle,
# so this restriction did not change what the test measured before.
fe_L = base["lamps"]["FOH L"]["flicker_end"]
mx = max(v for f, v, i in lamp if f >= fe_L) / 1740.0
cap = CFG["envelope"]["floor"] + (CFG["envelope"]["peak"] - CFG["envelope"]["floor"]) * (1 - CFG["envelope"]["headroom"])
case("headroom: FOH L peak scale <= floor+(peak-floor)*(1-headroom) = %.3f" % cap, mx <= cap + 1e-9, mx)
hot, _ = plan_with(lambda c: c["envelope"].__setitem__("gain", 5.0))
mx_hot = max(v for f, v, i in hot["lamps"]["FOH L"]["intensity"] if f >= fe_L) / 1740.0
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

# ---- 8. house warmers: off for the Opening ONLY (Gary 4 Oct) -> this tool never disables them
# 5 Oct ~16:25: write is now True (the cone rule on the warmers); the ONLY write paths are enabled + inner cone,
# and with mechanism null the warmers still burn (the 'not dark' warning stays).
case("house warmers: default config passes, writes only enabled+inner cone, and the 'not dark' warning is raised",
     not has(base["failures"], "house-warmers") and base["house_warmers"]["write"] is True
     and base["house_warmers"]["write_paths"] == ["enabled", "lighting.inner_cone_angle_degrees"]
     and any("DISABLED in the Show" in w for w in base["house_warmers"]["warnings"]), base["house_warmers"])  # live JSON: Gary's 16:40 takeover
hw, _ = plan_with(lambda c: c["house_warmers"].__setitem__("disable", True))
case("NEG: house_warmers.disable true is refused (would kill them in P01 too)",
     has(hw["failures"], "house-warmers-disable"), hw["failures"])
hw, _ = plan_with(lambda c: c["house_warmers"].__setitem__("rule", "off"))
case("NEG: a rule other than off_for_opening_only is refused", has(hw["failures"], "house-warmers-rule"), hw["failures"])
hw, _ = plan_with(lambda c: c["house_warmers"].__setitem__("owner", "lighting_scores_apply.py"))
case("NEG: a second owner (lighting_scores) is refused", has(hw["failures"], "house-warmers-owner"), hw["failures"])
hw, _ = plan_with(lambda c: c["house_warmers"].__setitem__("mechanism", "light_drama_strike"))
case("NEG: a Light Drama mechanism is refused (drama cannot run before P01's segment)",
     has(hw["failures"], "house-warmers-mechanism"), hw["failures"])
# Source anchors (declaration-proven): the facts the refusal rests on. If the C++ changes, these fail and the
# mechanism refusal must be revisited.
PASSAGE_CPP = os.path.join(os.path.dirname(SAVED), "Plugins", "InfinityStage", "Source", "InfinityStage", "Private",
                           "InfinityStagePassageActor.cpp")


def drama_gated_by_segment(src):
    gate = src.find("MasterFrame < Passage->SegmentStartFrame || MasterFrame > Passage->SegmentEndFrame")
    drama = src.find("InfinityStageLightDrama::ApplyToLamp(")
    body = src.find("bool AInfinityStagePassageActor::EvaluateMechanismsInternal(")
    return 0 <= body < gate < drama and src.find("return false;", gate) < drama


cpp = open(PASSAGE_CPP, encoding="utf-8", errors="replace").read()
case("SOURCE: drama is applied only after the Passage segment gate (EvaluateMechanismsInternal)",
     drama_gated_by_segment(cpp))
case("NEG: the same check on a copy with the gate removed reports False",
     not drama_gated_by_segment(cpp.replace("MasterFrame < Passage->SegmentStartFrame", "false")))
apply_src = open(os.path.join(HERE, "opening_sequence_apply.py"), encoding="utf-8").read()


def warmer_writes_gated(src):
    """5 Oct ~16:25: the apply tool may now write the warmers, but ONLY through write_warmers(), whose values come
    from the planner model (warmer_targets -> warmers_apply_state / warmers_revert_state): exactly one Enabled
    write, taking the model's value, and no legacy set_warmers helper."""
    return (src.count('set_editor_property("enabled"') == 1
            and 'a.set_editor_property("enabled", bool(t["enabled"]))' in src
            and 'planner["warmer_targets"](cfg' in src and "def set_warmers(" not in src)


case("SOURCE: opening_sequence_apply.py writes warmer Enabled only via write_warmers() from the planner targets",
     warmer_writes_gated(apply_src))
case("NEG: a copy with an extra hard-coded Enabled write is caught",
     not warmer_writes_gated(apply_src + chr(10) + '    a.set_editor_property("enabled", False)' + chr(10)))

# ---- 9. strobe flicker (Gary 5 Oct ~15:15: start on the entry; 'brutal with a bit of that strobe falloff')
FL = CFG["flicker"]
NOM = {fx["name"]: float(fx["nominal_cd"]) for fx in CFG["fixtures"]}


def window_keys(plan, name):
    """[(frame, scale x nominal)] of one lamp's keys inside its own flicker window [start, end] (end = landing)."""
    lp = plan["lamps"][name]
    return [(f, v / NOM[name]) for f, v, _ in lp["intensity"] if lp["flicker_start"] <= f <= lp["flicker_end"]]


def pops_of(wk, floor):
    """Indices of flash pops: a key >= floor that rises from the previous key."""
    return [j for j, (f, v) in enumerate(wk) if v >= floor and (j == 0 or v > wk[j - 1][1])]


def black_between(wk, floor):
    """True if every pair of consecutive pops has a key at exactly 0.0 between them."""
    p = pops_of(wk, floor)
    return len(p) >= 2 and all(any(wk[k][1] == 0.0 for k in range(a + 1, b)) for a, b in zip(p, p[1:]))


def decay_ok(wk, fl):
    """Each pop: held 1 (or 2) frames (CONSTANT keys: a 2-frame hold is ONE key, the next key 2 frames later), then
    2..3 CONSECUTIVE frames each at peak x falloff[k] (+/- jitter), then 0.0 or the landing. Returns (ok, why)."""
    fall, jit = fl["falloff"], fl["falloff_jitter"]
    for j in pops_of(wk, fl["peak_min"] - 1e-9):
        f0, peak = wk[j]
        k = j + 1
        if k < len(wk) and wk[k][0] - f0 not in (1, 2):
            return False, "pop at %d held %d frames (want 1 or 2)" % (f0, wk[k][0] - f0)
        n = 0
        while k < len(wk) - 1 and 0.0 < wk[k][1] < peak and (n == 0 or wk[k][0] == wk[k - 1][0] + 1) and n < len(fall):
            lo, hi = peak * fall[n] * (1 - jit) - 1e-9, peak * fall[n] * (1 + jit) + 1e-9
            if not lo <= wk[k][1] <= hi:
                return False, ("frame %d: %.3f not in falloff[%d] band [%.3f, %.3f]" % (wk[k][0], wk[k][1], n, lo, hi))
            n += 1
            k += 1
        clipped = k == len(wk) - 1 and wk[k][0] == wk[-1][0]   # tail cut by the landing
        if n < fl["falloff_frames_min"] and not clipped:
            return False, "pop at %d decays over %d frames < %d" % (f0, n, fl["falloff_frames_min"])
        if k < len(wk) and wk[k][1] != 0.0 and k != len(wk) - 1:
            return False, "pop at %d is not followed by black (next %.3f)" % (f0, wk[k][1])
    return True, ""


strobe_on = "peak_max" in FL
case("strobe style is active in opening_timing.json (flicker.peak_max present)", strobe_on, sorted(FL))
case("flicker_start = 36.18 s -> frame 904 (the entry 36.1767 s); music_start (frame %d) <= flicker_start" % fr["music_start"],
     fr["flicker_start"] == 904 and fr["music_start"] <= fr["flicker_start"], (fr["flicker_start"], fr["music_start"]))
case("swivel: start = auto next major change 43.84 s (1096); end = JSON 50.0 s (1250, Gary 5 Oct ~15:45 'shorter')",
     fr["swivel_start"] == 1096 and fr["swivel_end"] == 1250 and base["sources"]["swivel_end"] == "json (first apply)"
     and "auto" in base["reasons"]["swivel_start"] and base["reasons"]["swivel_end"] == "json",
     (fr["swivel_start"], fr["swivel_end"], base["reasons"]["swivel_start"], base["reasons"]["swivel_end"]))
case("every lamp's staggered flicker ends before the swivel starts",
     all(l["flicker_end"] <= fr["swivel_start"] for l in base["lamps"].values()),
     {n: l["flicker_end"] for n, l in base["lamps"].items()})
for nm in base["lamps"]:
    wk = window_keys(base, nm)
    case("PEAK: %s reaches > 2x nominal in its flicker (max %.2fx)" % (nm, max(v for _, v in wk)), max(v for _, v in wk) > 2.0)
    case("BLACK: %s is fully 0 between every pair of flashes (%d pops)" % (nm, len(pops_of(wk, FL["peak_min"] - 1e-9))),
         black_between(wk, FL["peak_min"] - 1e-9), wk[:12])
    ok, why = decay_ok(wk, FL)
    case("DECAY: %s every flash falls off peak -> ~1/3 -> ~1/10 (-> ~1/30) on consecutive frames, then black" % nm, ok, why)
    single = [j for j in pops_of(wk, FL["peak_min"] - 1e-9) if j + 1 < len(wk) and wk[j + 1][0] == wk[j][0] + 1]
    case("POPS: %s mostly single-frame (%d of %d)" % (nm, len(single), len(pops_of(wk, FL["peak_min"] - 1e-9))),
         len(single) >= 0.7 * len(pops_of(wk, FL["peak_min"] - 1e-9)))
    pf = [wk[j][0] for j in pops_of(wk, FL["peak_min"] - 1e-9)]
    iv = [b - a for a, b in zip(pf, pf[1:])]
    h_ = len(iv) // 2
    case("DENSER: %s pop intervals shrink (first half mean %.1f > second half mean %.1f frames)"
         % (nm, sum(iv[:h_]) / max(1, h_), sum(iv[h_:]) / max(1, len(iv) - h_)),
         len(iv) >= 4 and sum(iv[:h_]) / h_ > sum(iv[h_:]) / (len(iv) - h_), iv)
    lp = base["lamps"][nm]
    nxt = [(f, v) for f, v, _ in lp["intensity"] if f > lp["flicker_end"]]
    land = [v for f, v, _ in lp["intensity"] if f == lp["flicker_end"]]
    case("LANDING: %s lands ON at idle x nominal at its flicker_end, the same level the next key holds (no step)"
         % nm, land == [FL["idle_level"] * NOM[nm]] and nxt and nxt[0][0] <= fr["swivel_end"]
         and abs(nxt[0][1] - land[0]) < 1e-9, (land, nxt[:1]))
    case("UNLIT: %s is 0 before its own flicker_start" % nm,
         all(v == 0.0 for f, v, _ in lp["intensity"] if f < lp["flicker_start"]))
# negative controls: each check above must be able to fail
def landing_ok(plan, nm):
    lp = plan["lamps"][nm]
    land = [v for f, v, _ in lp["intensity"] if f == lp["flicker_end"]]
    nxt = [(f, v) for f, v, _ in lp["intensity"] if f > lp["flicker_end"]]
    return land == [FL["idle_level"] * NOM[nm]] and bool(nxt) and abs(nxt[0][1] - land[0]) < 1e-9


tl = copy.deepcopy(base)
tl["lamps"]["FOH L"]["intensity"] = [(f, (0.0 if f == tl["lamps"]["FOH L"]["flicker_end"] else v), i)
                                     for f, v, i in tl["lamps"]["FOH L"]["intensity"]]
case("NEG: a lamp landing at 0 (not idle) at flicker_end fails LANDING", landing_ok(base, "FOH L") and not landing_ok(tl, "FOH L"))
soft = window_keys(plan_with(lambda c: c["flicker"].update(peak_min=0.9, peak_max=1.5))[0], "FOH L")
case("NEG: peak_max 1.5 does NOT reach > 2x", max(v for _, v in soft) <= 1.5 + 1e-9, max(v for _, v in soft))
wk_l = window_keys(base, "FOH L")
no_black = [(f, v if v != 0.0 else 0.05) for f, v in wk_l]
case("NEG: the same keys with every 0.0 lifted to 0.05 fail BLACK", not black_between(no_black, FL["peak_min"] - 1e-9))
slow = window_keys(plan_with(lambda c: c["flicker"].update(falloff=[0.9, 0.8, 0.7]))[0], "FOH L")
case("NEG: a slow falloff [0.9, 0.8, 0.7] fails DECAY against the configured shape", not decay_ok(slow, FL)[0],
     decay_ok(slow, FL))
held = window_keys(plan_with(lambda c: c["flicker"].update(double_pop_chance=1.0))[0], "FOH L")
hp = pops_of(held, FL["peak_min"] - 1e-9)
case("NEG: double_pop_chance 1.0 makes every pop 2 frames (the POPS check would fail)",
     all(j + 1 < len(held) and held[j + 1][0] == held[j][0] + 2 for j in hp[:-1]) and len(hp) >= 4, held[:10])
rev = window_keys(plan_with(lambda c: c["flicker"].update(gap_early_frames=[1, 2], gap_late_frames=[12, 24]))[0], "FOH L")
rp = [rev[j][0] for j in pops_of(rev, FL["peak_min"] - 1e-9)]
riv = [b - a for a, b in zip(rp, rp[1:])]
rh = len(riv) // 2
case("NEG: reversed gaps (dense early, sparse late) fail DENSER", not (sum(riv[:rh]) / max(1, rh) > sum(riv[rh:]) / max(1, len(riv) - rh)), riv)
# OLD CONFIG UNCHANGED: without the new keys flicker_steps must reproduce the pre-5-Oct planner exactly. Hashes were
# MEASURED from the pre-change planner (git HEAD a9e33d6 copy, opening_sequence_plan.py.bak-20261005-1530-preflicker).
OLD_KEYS = ("seed", "idle_level", "on_level_min", "max_step_frames")
old_cfg = copy.deepcopy(CFG)
old_cfg["flicker"] = {k: CFG["flicker"][k] for k in OLD_KEYS}
OLD_HASHES = {("FOH L", 100, 162): "6cd1ceaacaf2005b", ("FOH R", 909, 1000): "f30b13bf1bb7bba4",
              ("Wash C", 922, 1009): "007fb4c0fb4291da"}


def steps_hash(cfg, fx, a, b):
    import hashlib
    return hashlib.sha256(json.dumps(P.flicker_steps(fx, a, b, cfg, cfg["flicker"]["seed"])).encode()).hexdigest()[:16]


case("OLD CONFIG: without the new keys flicker_steps == the pre-change planner (3 measured hashes)",
     all(steps_hash(old_cfg, *k) == v for k, v in OLD_HASHES.items()),
     {k: steps_hash(old_cfg, *k) for k in OLD_HASHES})
case("NEG: the strobe config gives different steps for the same windows",
     all(steps_hash(CFG, *k) != v for k, v in OLD_HASHES.items()))
tweak = copy.deepcopy(old_cfg)
tweak["flicker"]["on_level_min"] = 0.56
case("NEG: an old-config change (on_level_min 0.56) breaks the hash (the check can fail)",
     steps_hash(tweak, "FOH L", 100, 162) != OLD_HASHES[("FOH L", 100, 162)])
old_plan = P.build_plan(old_cfg, AN, WALK)
case("OLD CONFIG: the old stutter never exceeds idle in the window and passes validate",
     old_plan["failures"] == [] and max(v for _, v in window_keys(old_plan, "FOH L")) <= FL["idle_level"] + 1e-9,
     old_plan["failures"])
case("deterministic strobe: a rebuild gives identical lamp keys",
     json.dumps(plan_with()[0]["lamps"], sort_keys=True) == json.dumps(base["lamps"], sort_keys=True))
# caps: raised ONLY inside the flicker window
cap_hi, _ = plan_with(lambda c: c["flicker"].update(peak_max=5.0))
case("NEG: peak_max 5.0 is refused (flicker-peak-cap, hard cap %.1fx)" % P.FLICKER_PEAK_HARD_CAP,
     has(cap_hi["failures"], "flicker-peak-cap"), cap_hi["failures"])
tam = copy.deepcopy(base)
lk = tam["lamps"]["FOH L"]["intensity"]
jx = next(j for j, k in enumerate(lk) if k[0] > fr["swivel_end"])
lk[jx] = (lk[jx][0], 3.0 * 1740.0, lk[jx][2])
case("NEG: a 3x key OUTSIDE the flicker window is refused (intensity-cap)", has(P.validate(tam, CFG), "intensity-cap"))
tam2 = copy.deepcopy(old_plan)
lk2 = tam2["lamps"]["FOH L"]["intensity"]
jy = next(j for j, k in enumerate(lk2) if tam2["lamps"]["FOH L"]["flicker_start"] < k[0] < tam2["lamps"]["FOH L"]["flicker_end"])
lk2[jy] = (lk2[jy][0], 3.0 * 1740.0, lk2[jy][2])
case("NEG: with the OLD stutter a 3x key inside the window is still refused (cap raised only for the strobe)",
     has(P.validate(tam2, old_cfg), "intensity-cap"))
late, _ = plan_with(lambda c: c["fixtures"][2].__setitem__("flicker_stagger_s", 25.0))
case("NEG: a Wash C stagger of 25 s (flicker past swivel_end) is refused (flicker-before-envelope)",
     has(late["failures"], "flicker-before-envelope"), late["failures"])
long_, _ = plan_with(lambda c: c["rules"].__setitem__("flicker_s", 8.0))
case("NEG: flicker_s 8 s pushes the auto swivel to 59.5 s; a JSON swivel_start 43.84 s with it is refused",
     has(plan_with(lambda c: c["rules"].__setitem__("flicker_s", 8.0) or
                   c["moments"].__setitem__("swivel_start", {"value": 43.84}))[0]["failures"], "flicker-before-swivel")
     and long_["frames"]["swivel_start"] > 1096)
# record/marker: the JSON change must win cleanly over the last APPLY (record on disk) and its markers
REC = P.load_json(os.path.join(HERE, "opening_sequence_record.json"))
last_rec = REC["last_applied_frames"]
mk_rec = dict(last_rec)                                   # markers exactly where the last APPLY wrote them
pr, _ = plan_with(markers=mk_rec, last=last_rec)
case("RECORD: last APPLY (flicker_start %d) + markers unmoved -> JSON wins, no conflict, flicker_start 904"
     % last_rec["flicker_start"], pr["failures"] == [] and pr["frames"]["flicker_start"] == 904
     and pr["sources"]["flicker_start"] == "json" and pr["writeback"] == {}, (pr["sources"], pr["failures"]))
case("RECORD: flicker_end / swivel_start / swivel_end also move by JSON (auto), music_start unchanged",
     all(pr["sources"][n] == "json" for n in ("flicker_end", "swivel_start", "swivel_end"))
     and pr["sources"]["music_start"] == "unchanged", pr["sources"])
l208 = dict(last_rec, flicker_start=208)
p208, _ = plan_with(markers=dict(mk_rec, flicker_start=208), last=l208)
case("RECORD: had the last APPLY left flicker_start at 208 with the marker at 208, the JSON still wins",
     p208["frames"]["flicker_start"] == 904 and p208["sources"]["flicker_start"] == "json" and not p208["conflicts"])
pdr, _ = plan_with(markers=dict(mk_rec, flicker_start=last_rec["flicker_start"] + 30), last=last_rec)
case("NEG: if Gary dragged OPN flicker_start since the last APPLY, the JSON change is a CONFLICT (refused)",
     has(pdr["failures"], "marker-conflict"), pdr["failures"])

# ---- 10. land dim, rise slowly with the swivel (Gary 5 Oct ~15:45); swivel 43.84-50 s
ENV = CFG["envelope"]


def per_frame(keys, f0, f1):
    """Evaluate [(frame, value, interp)] per frame on [f0, f1] the way Sequencer does: a key's interp governs the
    segment AFTER it (constant holds, linear blends to the next key)."""
    out = []
    for f in range(f0, f1 + 1):
        v = 0.0
        for j, (kf, kv, ki) in enumerate(keys):
            if kf > f:
                break
            v = kv
            if ki == "linear" and j + 1 < len(keys) and keys[j + 1][0] > f:
                nf, nv = keys[j + 1][0], keys[j + 1][1]
                v = kv + (nv - kv) * (f - kf) / float(nf - kf)
        out.append(v)
    return out


RISE_CAP = 0.01        # x nominal per frame (= 0.25x per second at 25 fps): 'rise slowly', no step


def max_rise(plan, nm):
    lp = plan["lamps"][nm]
    vals = per_frame(lp["intensity"], lp["flicker_end"], plan["frames"]["opening_end"])
    return max(b - a for a, b in zip(vals, vals[1:])) / lp["nominal_cd"]


for nm in base["lamps"]:
    mr = max_rise(base, nm)
    case("RISE: %s max per-frame rise after its flicker_end = %.4fx nominal <= %.3fx (no step)" % (nm, mr, RISE_CAP),
         mr <= RISE_CAP, mr)
lp = base["lamps"]["FOH L"]
vals = per_frame(lp["intensity"], lp["flicker_end"], fr["swivel_end"])
idle_cd = FL["idle_level"] * 1740.0
case("RISE: FOH L holds the dim landing until swivel_start, then rises monotonically to swivel_end",
     all(abs(v - idle_cd) < 1e-9 for v in vals[:fr["swivel_start"] - lp["flicker_end"] + 1])
     and all(b >= a - 1e-9 for a, b in zip(vals, vals[1:])) and vals[-1] > idle_cd * 1.4, (vals[0], vals[-1]))
env_lvl = 1740.0 * P.envelope_scale(P.env_at(fr["swivel_end"] / 25.0, rate, env), ENV) * trend_mult(fr["swivel_end"])
case("RISE: FOH L arrives at the envelope's own level at swivel_end (%.1f cd)" % env_lvl,
     abs(vals[-1] - env_lvl) < 1e-6, (vals[-1], env_lvl))
old_rise, _ = plan_with(lambda c: c["envelope"].pop("rise_from"))
mr_old = max_rise(old_rise, "FOH L")
case("NEG: without rise_from (old: idle held to swivel_end, then a 10-frame ramp) the rise check FAILS (%.4fx/frame)"
     % mr_old, mr_old > RISE_CAP, mr_old)
case("OLD rise: without rise_from FOH L still holds idle exactly to swivel_end (backward compatible)",
     [v for f, v, i in old_rise["lamps"]["FOH L"]["intensity"] if f == fr["swivel_end"]] == [idle_cd])
# record: the explicit swivel_end must win cleanly over the last APPLY (1096) with its marker unmoved
case("RECORD: swivel_end JSON 1250 wins over last APPLY %d (marker unmoved), no conflict" % last_rec["swivel_end"],
     pr["frames"]["swivel_end"] == 1250 and pr["sources"]["swivel_end"] == "json" and not pr["conflicts"])
pse, _ = plan_with(markers=dict(mk_rec, swivel_end=last_rec["swivel_end"] + 25), last=last_rec)
case("NEG: a swivel_end marker dragged since the last APPLY + the JSON change -> CONFLICT (refused)",
     has(pse["failures"], "marker-conflict"), pse["failures"])

# ---- 11. rig takeover (Gary 5 Oct ~16:25): warmers, cones, the FOH rise to the curtain
# Warmer state model on attachment_state()-shaped dicts. Values MEASURED 4 Oct (light_guid_audit_20261004-121338.json):
# enabled, 1740 cd, outer 33, inner 20.
def warmer_state(label):
    return {"guid": label, "label": label, "kind": "InfinityAttachmentKind.LIGHT", "enabled": True,
            "lighting": {"intensity": 1740.0, "outer_cone_angle_degrees": 33.0, "inner_cone_angle_degrees": 20.0,
                         "temperature_kelvin": 2800.0, "drama": {"strike_on_approach": False}},
            "trigger_distance_cm": 800.0}


W0 = {lab: warmer_state(lab) for lab in CFG["house_warmers"]["labels"]}
live0 = {lab: {"enabled": st["enabled"], "inner": st["lighting"]["inner_cone_angle_degrees"],
               "outer": st["lighting"]["outer_cone_angle_degrees"]} for lab, st in W0.items()}
# The live JSON now carries Gary's takeover (16:40); the "default" cases model the unset state explicitly.
CFG0 = json.loads(json.dumps(CFG))
CFG0["house_warmers"]["cone"] = CFG0["house_warmers"].get("cone") or CFG0["house_warmers"]["cone_parked"]  # live JSON parks it (6 Oct)
CFG0["house_warmers"]["mechanism"] = None
CFG0["house_warmers"]["p01_without_warmers_confirmed_by"] = None
tg, tf = P.warmer_targets(CFG0, live0)
case("WARMER CONE: targets inner = outer - 3 = 30 on both warmers, Enabled untouched (mechanism null)",
     tf == [] and all(t == {"enabled": True, "inner_cone_angle_degrees": 30.0} for t in tg.values()) and len(tg) == 2,
     (tg, tf))
W1 = P.warmers_apply_state(W0, tg)
ch1 = P.warmers_changed_paths(W0, W1)
case("WARMER CONE: the model changes ONLY lighting.inner_cone_angle_degrees on the two warmers",
     sorted(ch1) == sorted("%s:lighting.inner_cone_angle_degrees" % lab for lab in W0), ch1)
case("REVERT exact: warmers_revert_state(apply(original)) == original", P.warmers_revert_state(W1, W0) == W0)
tampered = {lab: dict(st, lighting=dict(st["lighting"], inner_cone_angle_degrees=21.0)) for lab, st in W0.items()}
case("NEG: REVERT to a tampered snapshot (inner 21) is detected", P.warmers_revert_state(W1, tampered) != W0)
W1x = json.loads(json.dumps(W1))
W1x[CFG["house_warmers"]["labels"][0]]["lighting"]["intensity"] = 0.0
allowed = {"%s:%s" % (lab, ".".join(p)) for lab in W0 for p in P.WARMER_WRITE_PATHS}
case("NEG: a write that also touched intensity falls outside WARMER_WRITE_PATHS (apply refuses it)",
     bool(set(P.warmers_changed_paths(W0, W1x)) - allowed))
_, tf35 = P.warmer_targets(CFG0, {lab: dict(v, outer=35.0) for lab, v in live0.items()})
case("NEG: a live outer cone of 35 (not the expected 33) refuses the cone write",
     any("warmers-outer" in f for f in tf35), tf35)
case("WARMERS (default): mechanism null -> warmers stay ENABLED and the planner warns the Opening is NOT dark",
     all(t["enabled"] for t in tg.values()) and any("NOT dark" in w for w in plan_with(
         lambda c: c["house_warmers"].update({"mechanism": None, "p01_without_warmers_confirmed_by": None}))[0]["house_warmers"]["warnings"]))
nc, _ = plan_with(lambda c: c["house_warmers"].update({"mechanism": "disable_show_attachment",
                                                       "p01_without_warmers_confirmed_by": None}))
case("NEG: rig takeover (disable_show_attachment) WITHOUT p01_without_warmers_confirmed_by is refused",
     has(nc["failures"], "house-warmers-p01"), nc["failures"])


def takeover(c):
    c["house_warmers"]["mechanism"] = "disable_show_attachment"
    c["house_warmers"]["p01_without_warmers_confirmed_by"] = "TEST ONLY"
    c["house_warmers"]["cone"] = c["house_warmers"].get("cone") or c["house_warmers"]["cone_parked"]  # model the cone rule (parked live, 6 Oct)


tk, tkc = plan_with(takeover)
def takeover_live(c):
    takeover(c)
    c["house_warmers"]["cone"] = None
tl, tlc = plan_with(takeover_live)
tgl, tfl = P.warmer_targets(tlc, live0)
case("WARMERS OFF, cone parked (live 6 Oct): Enabled False, inner cone untouched (20)",
     tfl == [] and all(t == {"enabled": False, "inner_cone_angle_degrees": 20.0} for t in tgl.values()), (tfl, tgl))

tgo, tfo = P.warmer_targets(tkc, live0)
Wo = P.warmers_apply_state(W0, tgo)
case("WARMERS OFF (confirmed takeover): plan passes, both warmers Enabled False + inner 30, only allowed paths",
     tk["failures"] == [] and tfo == []
     and all(not st["enabled"] and st["lighting"]["inner_cone_angle_degrees"] == 30.0 for st in Wo.values())
     and not set(P.warmers_changed_paths(W0, Wo)) - allowed, (tk["failures"], tgo))
case("REVERT exact (takeover): Enabled and cone come back to the snapshot", P.warmers_revert_state(Wo, W0) == W0)
case("NEG: the 'not dark' warning is gone only under the takeover (the check can tell the two apart)",
     not any("NOT dark" in w for w in tk["house_warmers"]["warnings"]))
# cones on the rig
case("CONE: FOH L/R inner = 33 - 3 = 30 and Wash C 30 - 3 = 27 (cone_rule passes)",
     P.cone_check(CFG) == [] and [(fx["name"], fx["inner_cone_deg"]) for fx in CFG["fixtures"] if fx["enabled"]]
     == [("FOH L", 30.0), ("FOH R", 30.0), ("Wash C", 27.0)])
cc, _ = plan_with(lambda c: c["fixtures"][0].__setitem__("inner_cone_deg", 20.0))
case("NEG: FOH L back at inner 20 is refused (cone-rule)", has(cc["failures"], "cone-rule"), cc["failures"])


def maxima_to_release(plan, nm):
    lp = plan["lamps"][nm]
    a, b = plan["frames"]["swivel_end"], plan["frames"]["curtain_release"]
    v = per_frame(lp["intensity"], a, b)
    mx = [(a + i, v[i]) for i in range(1, len(v) - 1) if v[i] >= v[i - 1] and v[i] > v[i + 1]]
    return mx, v


for nm in base["lamps"]:
    mx, v = maxima_to_release(base, nm)
    peak_i = max(range(len(v)), key=lambda i: v[i])
    case("TREND: %s local maxima rise to the release %s and the peak is within 1 s of the release"
         % (nm, [round(x / base["lamps"][nm]["nominal_cd"], 3) for _, x in mx]),
         all(b[1] > a[1] for a, b in zip(mx, mx[1:])) and len(v) - 1 - peak_i <= 25
         and all(x < v[peak_i] for _, x in mx), (mx, peak_i, len(v)))
nt, _ = plan_with(lambda c: c["envelope"].pop("trend"))
mxn, _ = maxima_to_release(nt, "FOH L")
case("NEG: without the trend FOH L's maxima do NOT rise to the release %s"
     % [round(x / 1740.0, 3) for _, x in mxn], not all(b[1] > a[1] for a, b in zip(mxn, mxn[1:])))
rel = fr["curtain_release"]
case("TREND: the multiplier is %.2f at swivel_end and %.2f at the release (then held)"
     % (trend_mult(fr["swivel_end"]), trend_mult(rel)), abs(trend_mult(fr["swivel_end"]) - TR["start"]) < 1e-12
     and abs(trend_mult(rel) - TR["end"]) < 1e-12 and trend_mult(rel + 100) == TR["end"])
bad_tr, _ = plan_with(lambda c: c["envelope"]["trend"].__setitem__("start", 1.2))
case("NEG: a falling trend (start 1.2 > end 1.0) is refused (trend-rises)", has(bad_tr["failures"], "trend-rises"),
     bad_tr["failures"])
lpL = base["lamps"]["FOH L"]
wk_end = per_frame(lpL["intensity"], fr["walkin_start"], fr["opening_end"])
case("AFTER THE CURTAIN: FOH L ends where the walk-in takes it (%.1f cd at opening_end = end_light_level x nominal)"
     % wk_end[-1], abs(wk_end[-1] - CFG["walkin"]["end_light_level"] * 1740.0) < 1e-9)

passed = sum(1 for _, ok in RESULTS if ok)
print("\nRESULT %d/%d passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
