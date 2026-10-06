"""Offline +/- controls for p04_strobe_halo.py's pure plan (no Unreal). Run: python test_p04_strobe_halo.py"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p04_strobe_halo as H  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("  | " + detail) if detail else ""))


def refused(name, fn, needle):
    try:
        fn()
    except H.HaloError as error:
        check(name, needle in str(error), str(error)[:120])
        return
    check(name, False, "not refused")


plan = H.plan_change(dict(H.EXPECTED_5_OCT), dict(H.EXPECTED_5_OCT), dict(H.TARGET))
check("+ 5 Oct strobe -> halo: 20000->3500 cd, 1500->450 cm, ghost 1.0->0.35", plan == H.TARGET, str(plan))
check("+ the lit-fog sphere volume shrinks > 30x (r^3) and the peak > 5x", (1500.0 / 450.0) ** 3 > 30 and 20000 / 3500 > 5)
hand = dict(H.EXPECTED_5_OCT, attenuation_radius_cm=900.0)
refused("- control: a hand-tuned strobe (Gary moved/edited it) is refused until args.expected is updated",
        lambda: H.plan_change(hand, dict(H.EXPECTED_5_OCT), dict(H.TARGET)), "HALO_CURRENT_NOT_EXPECTED")
refused("- control: a 'halo' that is brighter than the wash is refused",
        lambda: H.plan_change(dict(H.EXPECTED_5_OCT), dict(H.EXPECTED_5_OCT), dict(H.TARGET, peak_intensity=25000.0)),
        "HALO_TARGET_OUT_OF_RANGE")
refused("- control: a ghost weight that still washes the frame (0.9) is refused",
        lambda: H.plan_change(dict(H.EXPECTED_5_OCT), dict(H.EXPECTED_5_OCT), dict(H.TARGET, ghost_max_weight=0.9)),
        "HALO_TARGET_OUT_OF_RANGE")
low = dict(H.EXPECTED_5_OCT, peak_intensity=3000.0, attenuation_radius_cm=400.0)
refused("- control: raising a strobe that is already below the target is not a cut",
        lambda: H.plan_change(low, low, dict(H.TARGET)), "HALO_NOT_A_CUT")
print("\n%d checks, %d passed, %d failed" % (len(RESULTS), sum(RESULTS), len(RESULTS) - sum(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
