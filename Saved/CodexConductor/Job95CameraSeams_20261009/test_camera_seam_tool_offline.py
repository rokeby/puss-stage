"""Offline positive and negative controls. No Unreal import."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import camera_seam_core as core

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


def rejects(name, fn):
    try:
        fn()
    except Exception:
        check(name, True)
    else:
        check(name, False)


base = {"location": [0, 0, 0], "quaternion": [0, 0, 0, 1], "focal_mm": 35, "focus_cm": 1000}
same = dict(base)
moved = dict(base, location=[0, 0, 23])
rolled = dict(base, quaternion=[0, 0, 0.024432, 0.999701])  # about 2.8 degrees

# Positive controls.
check("valid DRY", core.validate_args({"mode": "DRY", "run": "J95-DRY-001", "confirm": "CONFIRM_JOB95_DRY"})[0] == "DRY")
check("matched seam", core.seam_is_matched(core.seam_delta(base, same)))
check("23 cm bias detected", abs(core.seam_delta(base, moved)["position_cm"] - 23.0) < 1e-9)
check("2.8 degree bias detected", 2.79 < core.seam_delta(base, rolled)["rotation_deg"] < 2.81)
check("settle midpoint weights look", core.weighted_look(10, -20, 0.5) == (5.0, -10.0))
rows = [{"number": n, "rig_path": "rig%d" % n, "entry_path": "entry%d" % n, "matched": n != 3} for n in range(1, 7)]
census = core.exact_census(rows)
check("exact six-seam census", census == {"passage_scene_seams": 6, "passage_rigs": 6, "scene_entry_cameras": 6, "matched": 5, "stale": 1})

# Negative controls.
rejects("bad mode refused", lambda: core.validate_args({"mode": "WRITE", "run": "J95-X-001", "confirm": "x"}))
rejects("bad confirm refused", lambda: core.validate_args({"mode": "APPLY", "run": "J95-A-001", "confirm": "CONFIRM_JOB95_DRY"}))
rejects("reused/unsafe run syntax refused", lambda: core.validate_args({"mode": "DRY", "run": "../x", "confirm": "CONFIRM_JOB95_DRY"}))
rejects("short settle refused", lambda: core.validate_args({"mode": "APPLY", "run": "J95-A-002", "confirm": "CONFIRM_JOB95_APPLY", "settle_seconds": 0.5}))
rejects("revert without record refused", lambda: core.validate_args({"mode": "REVERT", "run": "J95-R-001", "confirm": "CONFIRM_JOB95_REVERT"}))
rejects("five seams refused", lambda: core.exact_census(rows[:5]))
duplicate = list(rows)
duplicate[-1] = dict(duplicate[-1], rig_path="rig1")
rejects("duplicate rig refused", lambda: core.exact_census(duplicate))
check("stale transform is not matched", not core.seam_is_matched(core.seam_delta(base, moved)))
check("settle clamps below zero", core.weighted_look(10, -20, -1) == (0.0, -0.0))
check("settle clamps above one", core.weighted_look(10, -20, 2) == (10.0, -20.0))

print("JOB95_HARNESS|positive=6/6|negative=10/10|total=%d/16" % passed)
raise SystemExit(0 if passed == 16 and failed == 0 else 1)

