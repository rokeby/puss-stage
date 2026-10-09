"""Offline positive and negative controls for job 104."""
from __future__ import annotations

import copy
import importlib.util
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("p104_core", os.path.join(HERE, "p104_core.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


class Checks:
    def __init__(self):
        self.positive = 0
        self.negative = 0

    def yes(self, value, label, negative=False):
        if not value:
            raise AssertionError(label)
        if negative:
            self.negative += 1
        else:
            self.positive += 1


K = Checks()


def facts(**changes):
    value = {"into_void_duration_s": C.OLD_TRACK_S, "delivered_wav_duration_s": 125.0,
             "assigned_sound": C.INTO_VOID, "cameron_asset_exists": False, "cameron_duration_s": None,
             "p06_length_s": 110.6, "chain_a_rows": 6, "chain_b_rows": 11,
             "p37_sequence_present": True, "fx_policy_evidence": "distance/view",
             "chandelier_policy_evidence": "owned_sequence_writes=[]"}
    value.update(changes)
    return value


plan = C.build_plan(facts())
K.yes(plan["decision"]["action"] == "IMPORT_AND_SWAP", "old IntoVoid chooses import/swap")
K.yes(plan["decision"]["target_sound"] == C.CAMERON, "Cameron destination")
K.yes(math.isclose(plan["scale"], 125.0 / 110.561125, abs_tol=1e-12), "track scale")
K.yes(plan["chain_a_rows"] == 6 and plan["chain_b_rows"] == 11, "both active chains")
policies = {row["item"]: row["policy"] for row in plan["policies"]}
K.yes(policies["P37 domino dust and slam sequence"] == "SCALE", "P37 scales")
K.yes(policies["P06 FX attachment set"] == "KEEP_ABSOLUTE", "FX stays distance based")
K.yes(policies["Job 85 P06 chandelier staging"] == "KEEP_ABSOLUTE", "chandelier stays spatial")
K.yes(len(plan["plan_sha256"]) == 64, "review hash")

already = C.build_plan(facts(into_void_duration_s=125.0))
K.yes(already["decision"]["action"] == "LENGTHEN_ONLY", "125 s IntoVoid skips import")
swapped = C.build_plan(facts(assigned_sound=C.CAMERON, cameron_asset_exists=True, cameron_duration_s=125.0))
K.yes(swapped["decision"]["action"] == "LENGTHEN_ONLY", "dedupe already imported and swapped")
K.yes(C.scale_frame(2715, plan["scale"]) == round(2715 * plan["scale"]), "frame scale")
rate, offset = C.retime_phase(0.4, 2.0, 50.0, 56.5, plan["scale"])
for old_time in (42.0, 50.0, 58.0):
    old_phase = 2.0 + (old_time - 50.0) * 0.4
    new_phase = offset + (old_time * plan["scale"] - 56.5) * rate
    K.yes(math.isclose(old_phase, new_phase, abs_tol=1e-10), "phase mapping %s" % old_time)


def refused(changes, label):
    try:
        C.build_plan(facts(**changes))
    except C.PlanError:
        K.yes(True, label, negative=True)
    else:
        raise AssertionError(label)


refused({"delivered_wav_duration_s": 124.0}, "refuse non-125 delivery")
refused({"into_void_duration_s": 117.0}, "refuse unknown IntoVoid duration")
refused({"assigned_sound": "/Game/Foreign"}, "refuse foreign rail sound")
refused({"p06_length_s": 126.0}, "refuse wrong starting Passage length")
refused({"chain_a_rows": 0}, "refuse missing chain A")
refused({"chain_b_rows": 0}, "refuse missing chain B")
refused({"p37_sequence_present": False}, "refuse missing P37 sequence")
refused({"assigned_sound": C.CAMERON, "cameron_asset_exists": True, "cameron_duration_s": 110.0},
        "refuse wrong imported Cameron duration")
refused({"cameron_asset_exists": True, "cameron_duration_s": 125.0},
        "refuse orphan Cameron asset before import")

for mode in ("DRY", "APPLY", "REVERT"):
    args = {"mode": mode, "confirm": "%s P06 FULL 125" % mode, "decided_by": C.DECIDED_BY,
            "reviewed_plan_sha256": plan["plan_sha256"] if mode == "APPLY" else ""}
    K.yes(C.validate_args(args) == mode, "%s args" % mode)
bad = {"mode": "APPLY", "confirm": "APPLY P06 FULL 125", "decided_by": C.DECIDED_BY,
       "reviewed_plan_sha256": ""}
try:
    C.validate_args(bad)
except C.PlanError:
    K.yes(True, "unreviewed APPLY refused", negative=True)
else:
    raise AssertionError("unreviewed APPLY refused")

source = open(os.path.join(HERE, "p104_live.py"), "r", encoding="utf-8").read()
for needle in ("guard()", "backup(run", "exclusive=True", "materialize_passage()", "P37_SEQUENCE_READBACK",
               "JOB42_READBACK", "MECHANISM_READBACK", "census() ==", "P104_P06_FULL_125"):
    K.yes(needle in source, "live safety source: " + needle)

print("P104_HARNESS_OK|positive=%d/%d|negative=%d/%d|total=%d" %
      (K.positive, K.positive, K.negative, K.negative, K.positive + K.negative))
