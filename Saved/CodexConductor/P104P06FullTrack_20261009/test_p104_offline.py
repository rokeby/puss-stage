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
K.yes(C.scale_span([None, None], plan["scale"]) == [None, None], "unbounded section stays unbounded")
K.yes(C.scale_span([100, None], plan["scale"])[1] is None, "half-bounded section keeps infinite end")
job42 = {"bee": {"protected_choreo": [
    {"class": "MovieSceneSubTrack", "name": "P06 Domino Finale (P37)",
     "sections": [{"start": 0, "end": 2765, "channels": []}]},
    {"class": "MovieSceneSubTrack", "name": "Unrelated", "sections": [{"start": 0, "end": 2765}]},
]}}
reconciled = C.reconcile_job42_protected_choreo(
    job42, {"subtrack": [[0, 2765]]}, {"subtrack": [[0, 3126]]})
K.yes(reconciled["bee"]["protected_choreo"][0]["sections"][0]["end"] == 3126,
      "P37 protected Choreo bound follows Job 134 subsection retime")
K.yes(job42["bee"]["protected_choreo"][0]["sections"][0]["end"] == 2765,
      "reconciliation does not mutate recorded Job 42 plan")
try:
    C.reconcile_job42_protected_choreo(job42, {"subtrack": [[1, 2765]]}, {"subtrack": [[1, 3126]]})
except C.PlanError as exc:
    K.yes("P37_PROTECTED_SECTION_MATCH_COUNT|0" in str(exc), "missing P37 protected section refused", negative=True)
else:
    raise AssertionError("missing P37 protected section refused")
ambiguous = copy.deepcopy(job42)
ambiguous["bee"]["protected_choreo"].append(copy.deepcopy(job42["bee"]["protected_choreo"][0]))
try:
    C.reconcile_job42_protected_choreo(ambiguous, {"subtrack": [[0, 2765]]}, {"subtrack": [[0, 3126]]})
except C.PlanError as exc:
    K.yes("P37_PROTECTED_SECTION_MATCH_COUNT|2" in str(exc), "ambiguous P37 protected section refused", negative=True)
else:
    raise AssertionError("ambiguous P37 protected section refused")
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

for mode in ("DRY", "APPLY", "REVERT", "RESUME"):
    args = {"mode": mode, "confirm": "%s P06 FULL 125" % mode, "decided_by": C.DECIDED_BY,
            "reviewed_plan_sha256": plan["plan_sha256"] if mode in ("APPLY", "RESUME") else ""}
    K.yes(C.validate_args(args) == mode, "%s args" % mode)
bad = {"mode": "APPLY", "confirm": "APPLY P06 FULL 125", "decided_by": C.DECIDED_BY,
       "reviewed_plan_sha256": ""}
try:
    C.validate_args(bad)
except C.PlanError:
    K.yes(True, "unreviewed APPLY refused", negative=True)
else:
    raise AssertionError("unreviewed APPLY refused")

resume_record = {"tool": "p104", "status": "prepared", "stage": "length_applied",
                 "audio_record": "audio.json", "length_record": "length.json", "plan": plan}
resume_facts = facts(assigned_sound=C.CAMERON, cameron_asset_exists=True,
                     cameron_duration_s=125.0, p06_length_s=125.0)
K.yes(C.validate_resume(resume_record, resume_facts) is plan, "resume exact saved boundary")
recovery_record = copy.deepcopy(resume_record)
recovery_record.update({"stage": "custom_recorded", "before": {"recorded": True},
                        "after": {"recorded": True}, "backup": {"root": "PreP104"}})
K.yes(C.validate_resume(recovery_record, resume_facts) == plan,
      "custom_recorded transaction may reach the live baseline recovery gate")
incomplete_recovery = copy.deepcopy(recovery_record)
incomplete_recovery.pop("before")
try:
    C.validate_resume(incomplete_recovery, resume_facts)
except C.PlanError as exc:
    K.yes("RESUME_CUSTOM_RECOVERY_RECORD_INCOMPLETE" in str(exc),
          "custom_recorded retry without complete recovery evidence refused", negative=True)
else:
    raise AssertionError("incomplete custom recovery refused")
for changes, label in (({"assigned_sound": C.INTO_VOID}, "resume refuses old rail"),
                       ({"p06_length_s": 110.6}, "resume refuses old length"),
                       ({"cameron_duration_s": 124.0}, "resume refuses wrong Walking6 duration")):
    bad_facts = dict(resume_facts, **changes)
    try:
        C.validate_resume(resume_record, bad_facts)
    except C.PlanError:
        K.yes(True, label, negative=True)
    else:
        raise AssertionError(label)

source = open(os.path.join(HERE, "p104_live.py"), "r", encoding="utf-8").read()
for needle in ("guard()", "backup(run", "exclusive=True", "materialize_passage()", "P37_SEQUENCE_READBACK",
               "JOB42_READBACK", "MECHANISM_READBACK", "census() ==", "P104_P06_FULL_125",
               "audio_repeated=0", "section.has_start_frame()", "verify_custom(R",
               "reconcile_job42_protected_choreo", '"JOB42_READBACK|" + ",".join(failures)',
               "verify_custom_retry_baseline", "CUSTOM_RETRY_UNSAVED_MUTATIONS_PRESENT"):
    K.yes(needle in source, "live safety source: " + needle)

print("P104_HARNESS_OK|positive=%d/%d|negative=%d/%d|total=%d" %
      (K.positive, K.positive, K.negative, K.negative, K.positive + K.negative))
