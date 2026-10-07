"""Offline harness for puss_shadow_spot.py pure logic. Each check has a + control (must pass) and, where it can be
fooled, a - control (a deliberately wrong input the same check must reject). Run: python test_puss_shadow_spot_offline.py
Writes test_puss_shadow_spot_offline_report.json (the offline DRY cue list with show times)."""
import ast
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
M = runpy.run_path(os.path.join(HERE, "puss_shadow_spot.py"), run_name="pss_offline")
FAILS = []
COUNT = [0]


def check(label, cond):
    COUNT[0] += 1
    if not cond:
        FAILS.append(label)
    print(("ok   " if cond else "FAIL ") + label)


def raises(fn, *a, **k):
    try:
        fn(*a, **k)
    except M["SpotError"]:
        return True
    return False


with open(os.path.join(HERE, "puss_shadow_spot_args.json"), encoding="utf-8") as h:
    RAW = json.load(h)
ARGS = M["check_args"](dict(RAW, mode="DRY"))

# --- syntax
for name in ("puss_shadow_spot.py", "puss_shadow_spot_run.py", "test_puss_shadow_spot_offline.py"):
    with open(os.path.join(HERE, name), encoding="utf-8") as h:
        ast.parse(h.read())
check("ast.parse all three files", True)

# --- args / confirm
check("+ DRY needs no confirm", ARGS["mode"] == "DRY")
check("- APPLY without confirm refused", raises(M["check_args"], dict(RAW, mode="APPLY")))
check("+ APPLY with confirm accepted", M["check_args"](dict(RAW, mode="APPLY", confirm="APPLY PUSSSHADOWSPOT"))["mode"] == "APPLY")
check("- light in front of the cat refused", raises(M["check_args"], dict(RAW, light_x_cm=-100.0)))
check("- unknown geometry source refused", raises(M["check_args"], dict(RAW, geometry_source="guess")))
check("+ default geometry source is Gary's reference", ARGS["geometry_source"] == "reference"
      and ARGS["reference_label"] == "PussFollowSpot")

# --- envelope mirrors the C++ (InfinityStage.ShadowSpot.Envelope table)
cue = {"passage_s": 10.0, "attack_s": 0.5, "hold_s": 3.0, "release_s": 1.0, "intensity_cd": 15000.0}
table = [(9.99, 0.0), (10.0, 0.0), (10.25, 0.5), (10.5, 1.0), (12.0, 1.0), (13.5, 1.0), (14.0, 0.5), (14.5, 0.0), (20.0, 0.0)]
check("+ envelope matches the C++ test table", all(abs(M["envelope"]([cue], t)[0] - w) < 1e-9 for t, w in table))
lin = lambda t: min(1.0, max(0.0, (t - 10.0) / 0.5))  # noqa: E731
check("- a linear attack would not match smoothstep at 10.125", abs(M["envelope"]([cue], 10.125)[0] - lin(10.125)) > 0.05)
w, i = M["envelope"]([cue, dict(cue, passage_s=13.0, intensity_cd=30000.0)], 13.6)
check("+ overlap takes the brightest", w == 1.0 and abs(i - 30000.0) < 1e-6)
hard = dict(cue, attack_s=0.0, release_s=0.0, passage_s=1.0)
check("+ zero attack/release is a hard cut, finite", M["envelope"]([hard], 1.0)[0] == 1.0 and M["envelope"]([hard], 4.0)[0] == 0.0)
check("+ scrub-safe: same time, same answer after a jump",
      M["envelope"]([cue], 10.1) == (M["envelope"]([cue], 14.2), M["envelope"]([cue], 10.1))[1])

# --- geometry
g = M["spot_geometry"](180.0, 200.0, ARGS)
H = g["light_floor_height_cm"]
check("+ target tip honoured (shadow of cat top lands 400 cm ahead)", abs(M["tip_ahead"](H, 200.0, ARGS) - 400.0) < 0.5)
check("- a light at the old default height (rig+250 -> 430) gives a shorter tip",
      M["tip_ahead"](430.0, 200.0, ARGS) < 300.0)
check("+ offset z is relative to the eye", abs(g["offset"][2] - (H - 180.0)) < 0.01)
check("+ pitch aims down", -45.0 < g["pitch_deg"] < -10.0)
check("- light below the cat top casts no ground tip", M["tip_ahead"](190.0, 200.0, ARGS) is None)
check("- grazing light (10 cm behind the cat) refused", raises(M["spot_geometry"], 180.0, 200.0, dict(ARGS, light_x_cm=-210.0, target_tip_ahead_cm=1200.0)))
check("+ same tip with the light 400 cm behind is accepted", not raises(M["spot_geometry"], 180.0, 200.0, dict(ARGS, target_tip_ahead_cm=1200.0)))

# --- reference re-basing and implied tip (Gary's PussFollowSpot)
ref = [-450.0, -180.0, 120.0]
reb = M["rebase_reference"](ref, 180.0, 150.0)
check("+ re-based light keeps its height above the floor", abs((reb[2] + 150.0) - (ref[2] + 180.0)) < 1e-9)
check("- un-rebased offset would drop the light 30 cm on P01", abs((ref[2] + 150.0) - (ref[2] + 180.0)) > 1.0)
tip = M["implied_tip"](ref, [-200.0, 0.0], 180.0, 200.0)
k = 300.0 / 100.0
check("+ implied tip is the ray through the cat top", abs(tip["x_ahead_cm"] - (-450.0 + 250.0 * k)) < 0.1
      and abs(tip["y_cm"] - (-180.0 + 180.0 * k)) < 0.1)
check("+ a high-left light throws the shadow forward-RIGHT", tip["y_cm"] > 0.0 and tip["x_ahead_cm"] > 0.0)
check("- light under the cat top has no tip", M["implied_tip"]([-450.0, 0.0, 10.0], [-200.0, 0.0], 180.0, 200.0) is None)
fake_ref = {"offset": ref, "rotation": [-20.0, 15.0, 0.0], "eye_cm": 180.0, "cat_rel_xy": [-200.0, 0.0],
            "light": {"intensity": 8.0}}
an = M["load_json"](ARGS["passages"]["Passage 3"]["analysis"], ROOT)
pr = M["plan_passage"]("Passage 3", an, None, 0.0, 180.0, 200.0, ARGS, fake_ref)
check("+ reference plan uses the reference offset/rotation and intensity",
      pr["geometry"]["source"] == "reference" and pr["geometry"]["rotation"] == [-20.0, 15.0, 0.0]
      and all(c["intensity_cd"] == 8.0 for c in pr["cues"]))
pc = M["plan_passage"]("Passage 3", an, None, 0.0, 180.0, 200.0, ARGS)
check("- computed plan does not silently use the reference", pc["geometry"]["source"] == "computed"
      and pc["cues"][0]["intensity_cd"] == ARGS["intensity_cd"])

# --- cue choice
p01 = M["load_json"](ARGS["passages"]["Passage 1"]["analysis"], ROOT)
notes = M["load_json"](ARGS["passages"]["Passage 1"]["notes"], ROOT)
c01 = M["choose_cues"](p01, notes, 0.0, ARGS)
check("+ P01 (73.5 s) gets 2 cues", len(c01) == 2)
check("+ P01 first cue snapped to the notable note 11.604", abs(c01[0]["song_moment_s"] - 11.604) < 1e-9
      and abs(c01[0]["passage_s"] - 11.104) < 1e-9)
check("- the drop into silence at 46.16 (strength 1.0) is not chosen", all(abs(c["song_change_s"] - 46.1613) > 1e-3 for c in c01))
check("+ cues >= 20 s apart", abs(c01[1]["song_moment_s"] - c01[0]["song_moment_s"]) >= 20.0)
c01o = M["choose_cues"](p01, notes, 2.0, ARGS)
check("+ music offset shifts passage seconds back", abs(c01o[0]["passage_s"] - (c01[0]["passage_s"] - 2.0)) < 1e-9)
p02 = M["load_json"](ARGS["passages"]["Passage 2"]["analysis"], ROOT)
check("+ short music (P02 45.5 s) gets 1 cue", len(M["choose_cues"](p02, None, 0.0, ARGS)) == 1)
check("- an early change (P01 3.16 s) is not chosen", all(c["song_change_s"] > 6.0 for c in c01))
for c in c01:
    end = c["passage_s"] + c["attack_s"] + c["hold_s"] + c["release_s"]
    check("+ P01 cue %.2f ends before music end - margin" % c["passage_s"], end <= p01["durationSeconds"] - ARGS["end_margin_s"])

# --- record rows / revert comparison
rows = M["cue_rows"](pc)
check("+ cue rows use FInfinityShadowSpotCue property names", set(rows[0]) == {
    "passage_seconds", "attack_seconds", "hold_seconds", "release_seconds", "intensity", "label"})
check("+ same_rows equal", M["same_rows"](rows, json.loads(json.dumps(rows))))
bad = json.loads(json.dumps(rows))
bad[0]["passage_seconds"] += 0.5
check("- same_rows catches a moved cue", not M["same_rows"](rows, bad))

# --- C++ patch sanity (text): names the tool writes exist in the patch
patch = open(os.path.join(ROOT, "Scripts", "patches", "2026-10-07_PS_puss_shadow_spot.patch"), encoding="utf-8").read()
for name in ("TArray<FInfinityShadowSpotCue> ShadowSpotCues", "FVector ShadowSpotOffset", "FRotator ShadowSpotRotation",
             "double PassageSeconds", "double AttackSeconds", "double HoldSeconds", "double ReleaseSeconds",
             "float Intensity", "FString Label", "double CurrentShadowSpotWeight"):
    check("+ patch declares " + name, name in patch)
check("- patch does not force candelas (reference units copy as is)", "SetIntensityUnits" not in patch)

# --- offline DRY report
plans = M["offline_plan"](ARGS, ROOT)
report = {"inferred": "offline: eye/cat top/music offset/passage starts assumed (see each plan's 'inferred')",
          "provenance": RAW.get("offline_provenance"), "plans": plans}
with open(os.path.join(HERE, "test_puss_shadow_spot_offline_report.json"), "w", encoding="utf-8") as h:
    json.dump(report, h, indent=1)
check("+ offline DRY: every passage has 1-2 cues with show times",
      all(1 <= len(p["cues"]) <= 2 and p["show_times"] and len(p["show_times"]) == len(p["cues"]) for p in plans))

print("\n%d checks, %d failed" % (COUNT[0], len(FAILS)))
for f in FAILS:
    print("FAILED: " + f)
sys.exit(1 if FAILS else 0)
