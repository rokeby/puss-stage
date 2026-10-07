"""Offline harness for p05_cat_height.py pure key maths. Each check has a + control (must pass) and a - control
(a deliberately wrong input that the same check must reject). Run: python test_p05_cat_height_offline.py"""
import ast
import json
import math
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
M = runpy.run_path(os.path.join(HERE, "p05_cat_height.py"), run_name="p05_offline")
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
    except M["P05Error"]:
        return True
    return False


TICK = 24000.0
# P05 segment from PSTILLS-P05-20261006-063953-morning manifest (measured 6 Oct)
S, E = 34120705, 38593432
plan = M["plan_keys"](S, E, TICK, 180.0, 90.0, 1.5)
B = plan["blend_ticks"]
ev = M["eval_keys"]

# --- ast
for name in ("p05_cat_height.py", "p05_cat_height_run.py", "test_p05_cat_height_offline.py"):
    with open(os.path.join(HERE, name), encoding="utf-8") as h:
        ast.parse(h.read())
check("ast.parse all three files", True)

# --- z scaling
check("+ delta = -90, scale 0.5", plan["delta_cm"] == -90.0 and plan["scale"] == 0.5)
check("+ interior eye = 90", 180.0 + ev(plan["height_keys"], (S + E) // 2) == 90.0)
check("- interior eye != 180 (a no-op plan would pass this wrongly)", 180.0 + ev(plan["height_keys"], (S + E) // 2) != 180.0)
p2 = M["plan_keys"](S, E, TICK, 180.0, 120.0, 1.5)
check("+ target arg honoured (120 -> delta -60)", p2["delta_cm"] == -60.0)
check("- wrong delta rejected", p2["delta_cm"] != -30.0)

# --- blend
check("+ endpoints unchanged (offset 0 at S and E)", ev(plan["height_keys"], S) == 0.0 and ev(plan["height_keys"], E) == 0.0)
check("+ blend ticks = 1.5 s", B == 36000)
check("+ half-way through ramp = half delta", abs(ev(plan["height_keys"], S + B // 2) + 45.0) < 1e-9)
q = ev(plan["height_keys"], S + B // 4)
check("+ quarter = smoothstep(0.25)*delta", abs(q - (-90.0 * 0.15625)) < 1e-9)
check("- linear ramp value rejected by smoothstep check", abs(q - (-90.0 * 0.25)) > 1.0)
# slope continuity at ramp ends (flat tangents): finite difference ~0 at S, S+B, E-B, E
for t in (S, S + B, E - B, E):
    d = (ev(plan["height_keys"], t + 1) - ev(plan["height_keys"], t - 1)) / 2.0
    check("+ zero slope at tick %d" % t, abs(d) < 1e-3)
# negative control: an auto-tangent (Catmull-like) curve would have slope at S+B; model a linear ramp
lin = lambda t: -90.0 * min(1.0, max(0.0, (t - S) / float(B)))
check("- linear ramp has a slope kink at S+B (would pop)", abs((lin(S + B) - lin(S + B - 100)) / 100.0) > 1e-3)
mx = max(abs(ev(plan["height_keys"], t + 1) - ev(plan["height_keys"], t)) for t in range(S, S + B, 97))
check("+ max per-tick change bounded (<= 1.5*delta/B)", mx <= 1.5 * 90.0 / B + 1e-9)
check("- too-short segment refused", raises(M["plan_keys"], S, S + int(3.5 * TICK), TICK, 180.0, 90.0, 1.5))
check("+ minimal segment accepted", not raises(M["plan_keys"], S, S + int(4.0 * TICK), TICK, 180.0, 90.0, 1.5))

# --- pitch add (hidden; default 0)
check("+ default plan has no pitch keys", plan["pitch_keys"] == [] and plan["pitch_up_deg"] == 0.0)
pp = M["plan_keys"](S, E, TICK, 180.0, 90.0, 1.5, 6.0)
pose = (100.0, 320000.0, 180.0, 0.0, 0.0, 0.0)
want = M["expected_pose"](pose, pp, (S + E) // 2)
check("+ pitch add 6 deg in interior", want[3] == 6.0 and want[2] == 90.0)
check("+ pitch 0 at endpoints", M["expected_pose"](pose, pp, E)[3] == 0.0)
check("- default args do not carry pitch", "pitch_up_deg" not in json.load(open(os.path.join(HERE, "p05_cat_height_args.json"))))
check("+ pitch moves cat: -200 cm figure offset, +6 deg -> ~-20.9 cm",
      abs(M["pitch_cat_shift_cm"]((-200.0, 0.0, 0.0), 6.0) + 20.905) < 0.01)
check("+ pitch 0 moves cat 0", M["pitch_cat_shift_cm"]((-200.0, 0.0, 0.0), 0.0) == 0.0)

# --- cat compensation
check("+ static: cat offset -175.88 -> -85.88", abs(M["cat_offset_after"](-175.883635, -90.0, "static_interior") + 85.883635) < 1e-9)
check("+ static: cat grounded in interior", M["cat_float_cm"](plan, (S + E) // 2, "static_interior") == 0.0)
check("+ static: cat floats 90 at endpoints (known cost)", M["cat_float_cm"](plan, S, "static_interior") == 90.0)
check("- none: cat sunk 90 in interior", M["cat_float_cm"](plan, (S + E) // 2, "none") == -90.0)

# --- expected pose / tolerance
got = (100.0, 320000.0, 90.0 + 0.01, 0.0, 0.0, 0.0)
d = M["pose_diff"](M["expected_pose"](pose, plan, (S + E) // 2), got)
check("+ read-back within tol", d["pos"] <= M["POS_TOL_CM"])
d = M["pose_diff"](M["expected_pose"](pose, plan, (S + E) // 2), (100.0, 320000.0, 180.0, 0.0, 0.0, 0.0))
check("- un-applied pose fails read-back", d["pos"] > M["POS_TOL_CM"])
check("+ yaw wrap 359.999 vs -0.001", M["pose_diff"]((0, 0, 0, 0, 359.999, 0), (0, 0, 0, 0, -0.001, 0))["rot"] < 1e-6)

# --- refusals
clean = {M["HEIGHT_CH"]: {"keys": [], "default": 0.0}, M["PITCH_CH"]: {"keys": [], "default": 0.0},
         M["LOOKAHEAD_CH"]: {"keys": [], "default": None}}
check("+ clean channels: no refusal", M["channel_refusals"](clean, 0.0) == [])
keyed = dict(clean); keyed[M["HEIGHT_CH"]] = {"keys": [[S, 5.0]], "default": 0.0}
check("- pre-keyed height refused", any("HEIGHT_ALREADY_KEYED" in r for r in M["channel_refusals"](keyed, 0.0)))
la = dict(clean); la[M["LOOKAHEAD_CH"]] = {"keys": [], "default": 500.0}
check("- look-ahead refused", any("LOOKAHEAD" in r for r in M["channel_refusals"](la, 0.0)))
check("- missing channel refused", any("CHANNEL_MISSING" in r for r in M["channel_refusals"]({}, 0.0)))

# --- revert exactness
before_poses = {str(t): (1.0 * t % 1000, 320000.0, 180.0, 0.0, 0.0, 0.0) for t in M["sample_ticks"](plan)}
record = {"plan": plan, "before": {"height": {"keys": [], "default": 0.0}, "cat_offset_z": -175.883635,
                                   "poses": before_poses}, "after_cat_offset_z": -85.883635}
applied = {"keys": [list(k) for k in plan["height_keys"]], "default": 0.0}
check("+ no drift right after apply", M["revert_drift"](record, applied, -85.883635) == [])
edited = {"keys": [list(k) for k in plan["height_keys"]], "default": 0.0}; edited["keys"][1][1] = -80.0
check("- hand-edited key is drift", M["revert_drift"](record, edited, -85.883635) != [])
check("- cat edited is drift", M["revert_drift"](record, applied, -100.0) != [])
check("+ exact revert passes", M["revert_exact"](record, {"keys": [], "default": 0.0}, -175.883635, before_poses) == [])
check("- leftover key fails revert", M["revert_exact"](record, {"keys": [[S, 0.0]], "default": 0.0}, -175.883635, before_poses) != [])
check("- cat 1e-3 off fails revert", M["revert_exact"](record, {"keys": [], "default": 0.0}, -175.882635, before_poses) != [])
bad_poses = dict(before_poses); k0 = sorted(bad_poses)[0]; bad_poses[k0] = (0, 320000.0, 180.1, 0, 0, 0)
check("- pose 0.1 cm off fails revert", M["revert_exact"](record, {"keys": [], "default": 0.0}, -175.883635, bad_poses) != [])

# --- args
check("+ DRY args ok", M["check_args"]({"mode": "DRY"})["target_eye_cm"] == 90.0)
check("- APPLY without confirm refused", raises(M["check_args"], {"mode": "APPLY"}))
check("+ APPLY with confirm ok", M["check_args"]({"mode": "APPLY", "confirm": "APPLY P05CATHEIGHT"})["mode"] == "APPLY")
check("- bad cat_mode refused", raises(M["check_args"], {"mode": "DRY", "cat_mode": "float"}))
check("- NaN target refused", raises(M["check_args"], {"mode": "DRY", "target_eye_cm": float("nan")}))

print("\n%d checks, %d failed" % (COUNT[0], len(FAILS)))
sys.exit(1 if FAILS else 0)
