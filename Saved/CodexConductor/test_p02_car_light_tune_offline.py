"""Offline positive/negative controls for Job 110. No Unreal import or editor access."""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p02_car_light_tune as tune  # noqa: E402


RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append(bool(condition))
    print("%s  %s%s" % ("PASS" if condition else "FAIL", name, ("  | " + detail) if detail else ""))


def refused(name, callback, needle):
    try:
        callback()
    except tune.CarTuneError as error:
        check(name, needle in str(error), str(error))
        return
    check(name, False, "not refused")


current = copy.deepcopy(tune.DEFAULT_EXPECTED)
with open(tune.ARGS, encoding="utf-8") as handle:
    shipped_args = json.load(handle)
check("+ shipped control is DRY, explicitly confirmed, and held for or decided by Gary",
      shipped_args["mode"] == "DRY" and shipped_args["confirm"] == "DRY P02CAR_TUNE"
      and str(shipped_args.get("decision", "")).startswith(("HOLD:", "Gary ")))
target = tune.plan_change(current, copy.deepcopy(tune.DEFAULT_EXPECTED), copy.deepcopy(tune.DEFAULT_TARGET))
check("+ default plan extends the radius and aims at the far wing", target["attenuation_radius_cm"] == 4600.0
      and target["aim_target_local"] == [0.0, -3800.0, 0.0])
t2 = tune.plan_change(current, copy.deepcopy(tune.DEFAULT_EXPECTED), dict(tune.DEFAULT_TARGET, attenuation_radius_cm=10000.0, aim_target_local=None))
check("+ Gary E28: radius 10000 with aim unchanged", t2["attenuation_radius_cm"] == 10000.0 and t2["aim_target_local"] == [0.0, -2400.0, 0.0])
check("+ optional peak and cone remain unchanged", target["peak_intensity"] == 9000.0
      and target["outer_cone_degrees"] == 28.0)
near_cm = 2400.0 - 1416.0
far_cm = 2400.0 + 1416.0
check("+ geometry control: old radius misses far wing; proposal reaches it", 3200.0 < far_cm < 4600.0)
check("+ inverse-square control is approximately 15:1 before the cutoff", 14.5 < (far_cm / near_cm) ** 2 < 15.5)

drifted = copy.deepcopy(current)
drifted["peak_intensity"] = 2500.0
refused("- hand tuning after the evidence snapshot is refused", lambda: tune.plan_change(
    drifted, copy.deepcopy(tune.DEFAULT_EXPECTED), copy.deepcopy(tune.DEFAULT_TARGET)), "P02CAR_CURRENT_NOT_EXPECTED")
short = copy.deepcopy(tune.DEFAULT_TARGET)
short["attenuation_radius_cm"] = 3800.0
refused("- radius that still cannot safely reach the far line is refused", lambda: tune.plan_change(
    current, copy.deepcopy(tune.DEFAULT_EXPECTED), short), "P02CAR_RADIUS_CANNOT_REACH_FAR_WING")
wrong_aim = copy.deepcopy(tune.DEFAULT_TARGET)
wrong_aim["aim_target_local"] = [0.0, -2400.0, 0.0]
refused("- centre aim instead of far-side aim is refused", lambda: tune.plan_change(
    current, copy.deepcopy(tune.DEFAULT_EXPECTED), wrong_aim), "P02CAR_AIM_NOT_AT_FAR_SIDE")
wide = copy.deepcopy(tune.DEFAULT_TARGET)
wide["outer_cone_degrees"] = 85.0
refused("- outer cone beyond the declared UPROPERTY limit is refused", lambda: tune.plan_change(
    current, copy.deepcopy(tune.DEFAULT_EXPECTED), wide), "P02CAR_TARGET_OUT_OF_RANGE")

print("\n%d checks, %d passed, %d failed" % (len(RESULTS), sum(RESULTS), len(RESULTS) - sum(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
