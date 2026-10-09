"""Offline positive/negative harness for P79.  No Unreal or Blender imports."""

import copy
import json
import os
import tempfile

import nap_interlude as n


S4 = "11111111111111111111111111111111"
I4 = "44444444444444444444444444444444"
P05 = "55555555555555555555555555555555"
MINTED_NAP = "79797979797979797979797979797979"


def fixture():
    segments = [
        {"guid": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "label": "Passage 4", "type": "WingPair",
         "start": 0, "end": 1000, "first_show_index": 0},
        {"guid": S4, "label": "Scene 4", "type": "Scene",
         "start": 1000, "end": 2000, "first_show_index": 40},
        {"guid": I4, "label": "Interaction 4", "type": "Sequence",
         "start": 2000, "end": 2400, "first_show_index": 41},
        {"guid": P05, "label": "Passage 05", "type": "WingPair",
         "start": 2400, "end": 3400, "first_show_index": 42},
        {"guid": "EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE", "label": "Scene 5", "type": "Scene",
         "start": 3400, "end": 4100, "first_show_index": 70},
    ]
    keys = {
        "P04": {"section_start_tick": 0, "channels": {"Camera.Speed": [[100, 1.0], [900, 1.0]]}},
        "P05": {"section_start_tick": 2400, "channels": {"Camera.Speed": [[2500, 1.0], [3300, 0.8]]}},
    }
    return {"segments": segments, "passage_keys": keys, "asset_exists": False,
            "actor_labels": ["Existing Actor"], "tick_resolution": 25.0}


def args(expected=True):
    return {"expected_interaction4_guid": I4 if expected else "",
            "expected_passage5_guid": P05 if expected else "",
            "loop_seconds": 20.0, "wake_tail_seconds": 1.0,
            "breath_period_seconds": 4.0, "breath_amplitude_cm": 1.5}


class FakeBackend(object):
    def __init__(self):
        self.original = fixture()
        self.state = copy.deepcopy(self.original)
        self.dirty = {"content": [], "maps": []}
        self.logs = []
        self.args = None
        self.cues = []

    def log(self, text):
        self.logs.append(text)

    def stop(self, text):
        self.logs.append(text)

    def census(self):
        return copy.deepcopy(self.dirty)

    def preflight(self, params, unused_mode):
        self.args = params
        if self.dirty != {"content": [], "maps": []}:
            raise n.PlanError("DIRTY")

    def inspect(self, params, plan=None):
        if plan is None:
            return copy.deepcopy(self.state)
        return {"segments": copy.deepcopy(self.state["segments"]),
                "passage_keys": copy.deepcopy(self.state["passage_keys"]),
                "markers": copy.deepcopy(self.state["markers"]),
                "breathing_z_keys": copy.deepcopy(self.state["breathing_z_keys"]),
                "owned_actor_labels": copy.deepcopy(self.state["owned_actor_labels"]),
                "sequence_package": params["sequence_package"],
                "camera_cut_range": [0, plan["total_frames"]],
                "asset_exists": True, "actor_labels": list(self.state["owned_actor_labels"]),
                "tick_resolution": 25.0}

    def backup(self, run, packages, prefix="PreNapInterlude"):
        return {"root": "%s-%s" % (prefix, run), "files": list(packages)}

    def apply(self, plan, params):
        cue = FakeInfinityShowCue(MINTED_NAP)
        cue.set_editor_property("type", "Sequence")
        cue.set_editor_property("label", n.MASTER_CUE_LABEL)
        cue.set_editor_property("enabled", True)
        self.cues.insert(plan["nap"]["show_index"], cue)
        minted = cue.get_editor_property("cue_guid")
        nap = dict(plan["nap"], guid=minted)
        self.state["segments"] = n.expected_segments(
            plan["segments_before"], plan["anchors"]["interaction4_segment_index"],
            nap, plan["delta_ticks"])
        shifted = copy.deepcopy(plan["passage_keys_before"])
        for row in shifted.values():
            if row["section_start_tick"] >= plan["downstream_threshold_tick"]:
                row["section_start_tick"] += plan["delta_ticks"]
                for keys in row["channels"].values():
                    for key in keys:
                        key[0] += plan["delta_ticks"]
        self.state["passage_keys"] = shifted
        self.state.update({"markers": copy.deepcopy(plan["markers"]),
                           "breathing_z_keys": copy.deepcopy(plan["breathing_z_keys"]),
                           "owned_actor_labels": copy.deepcopy(plan["actor_labels"]),
                           "asset_exists": True, "actor_labels": copy.deepcopy(plan["actor_labels"])})
        self.dirty = {"content": sorted([x for x in plan["named_packages"] if x != params["level_package"]]),
                      "maps": [params["level_package"]]}
        return {"minted_nap_cue_guid": minted, "nap_label": cue.get_editor_property("label")}

    def save(self, packages):
        self.dirty = {"content": [], "maps": []}
        return list(packages)

    def revert(self, record, params):
        wanted = record["plan"]["nap"]
        exact = [cue for cue in self.cues
                 if cue.get_editor_property("cue_guid") == wanted["guid"] and
                 cue.get_editor_property("label") == n.MASTER_CUE_LABEL]
        related = [cue for cue in self.cues
                   if cue.get_editor_property("cue_guid") == wanted["guid"] or
                   cue.get_editor_property("label") == n.MASTER_CUE_LABEL]
        if len(exact) != 1 or len(related) != 1:
            raise n.PlanError("REVERT_NAP_IDENTITY_DRIFT")
        self.cues = [cue for cue in self.cues if cue not in exact]
        self.state = copy.deepcopy(self.original)
        archive = "/Game/InfinityStage/Dev/Sequences/_Reverted/LS_Nap_BatteryChange_%s" % record["run_id"]
        self.dirty = {"content": sorted([params["show_package"], params["master_package"], archive]),
                      "maps": [params["level_package"]]}
        return {"archived_sequence": archive}


class FakeInfinityShowCue(object):
    """UE 5.8-shaped cue: construction mints GUID and callers cannot set it."""
    def __init__(self, minted_guid):
        self._values = {"cue_guid": minted_guid}

    def get_editor_property(self, name):
        return self._values[name]

    def set_editor_property(self, name, value):
        if name == "cue_guid":
            raise n.PlanError("FAKE_CUE_GUID_READ_ONLY")
        self._values[name] = value


class Counts(object):
    def __init__(self):
        self.pos = self.neg = self.checks = 0

    def check(self, condition, label):
        self.checks += 1
        if not condition:
            raise AssertionError(label)

    def positive(self):
        self.pos += 1

    def negative(self):
        self.neg += 1


def refused(fn, token, counts):
    try:
        fn()
    except (n.PlanError, n.Stop) as exc:
        counts.check(token in str(exc), "refusal %s not in %s" % (token, exc))
        counts.negative()
        return
    raise AssertionError("expected refusal " + token)


def main():
    c = Counts()
    plan = n.build_plan(fixture(), args())
    c.check(plan["anchors"]["interaction4_guid"] == I4, "I4 anchor")
    c.check(plan["anchors"]["passage5_guid"] == P05, "P05 anchor")
    c.check(plan["anchors"]["interaction4_end_tick"] == plan["anchors"]["passage5_start_tick"] == 2400,
            "I4 end / P05 start boundary")
    c.check([row["label"] for row in plan["segments_expected_after"]] ==
            ["Passage 4", "Scene 4", "Interaction 4", n.MASTER_CUE_LABEL, "Passage 05", "Scene 5"],
            "S4 I4 Nap P05 placement")
    c.check(plan["loop_frames"] == 500 and plan["wake_tail_frames"] == 25, "length")
    c.check(plan["markers"][0][1] == n.MARK_VAMP_START and plan["markers"][1][1] == n.MARK_VAMP_END, "vamp markers")
    wake = n.parse_go_marker(plan["markers"][2][1])
    c.check(plan["markers"][2][0] == plan["loop_frames"] and wake == ("45", n.MASTER_CUE_LABEL, 0),
            "single GO 45 PASS at vamp end with exact label")
    c.check(sum(1 for unused_frame, label in plan["markers"] if n.parse_go_marker(label)) == 1,
            "single GO marker")
    c.check(not n.seam_failures(plan["breathing_z_keys"], plan["loop_frames"]), "seam")
    c.check(plan["nap"]["guid"] is None, "DRY has no invented Nap GUID")
    c.check(plan["fallback_job"]["segment_identity"] ==
            {"label": n.MASTER_CUE_LABEL, "guid": None}, "DRY fallback identity awaits mint")
    c.positive()

    with tempfile.TemporaryDirectory() as root:
        backend = FakeBackend()
        dry_raw = {"mode": "DRY", "run_id": "NAP-DRY", "confirm": "DRY NAP NAP-DRY", "params": args(False)}
        n.main(dry_raw, backend, root)
        c.check(any(x.startswith("P79_NAP_DRY_OK") for x in backend.logs), "dry marker")
        apply_raw = {"mode": "APPLY", "run_id": "NAP-APPLY", "confirm": "APPLY NAP NAP-APPLY", "params": args(True)}
        rec = n.main(apply_raw, backend, root)
        c.check(rec["status"] == "saved_readback_verified", "apply status")
        c.check(rec["minted_nap_cue_guid"] == MINTED_NAP, "minted GUID recorded")
        persisted = n.read_json(os.path.join(root, "nap_interlude_record_NAP-APPLY.json"))
        c.check(persisted["minted_nap_cue_guid"] == MINTED_NAP, "minted GUID persisted")
        c.check(rec["plan"]["nap"] == {"guid": MINTED_NAP, "label": n.MASTER_CUE_LABEL,
                                       "show_index": 42}, "minted identity in plan")
        c.check(rec["plan"]["fallback_job"]["segment_identity"] ==
                {"label": n.MASTER_CUE_LABEL, "guid": MINTED_NAP}, "fallback uses minted identity")
        fallback = n.read_json(rec["fallback_job"])
        c.check(fallback["segment_identity"] ==
                {"label": n.MASTER_CUE_LABEL, "guid": MINTED_NAP}, "fallback persisted minted identity")
        c.check(any(x.startswith("P79_NAP_APPLY_OK") for x in backend.logs), "apply marker")
        c.check(not n.verify_after(rec["plan"], backend.inspect(backend.args, rec["plan"])), "apply readback")

        nap_row = next(row for row in backend.state["segments"] if row["guid"] == MINTED_NAP)
        nap_row["label"] = "Nap - battery change"
        refused(lambda: n.main({"mode": "REVERT", "run_id": "NAP-REVERT-LABEL",
                                "source_run_id": "NAP-APPLY", "confirm": "REVERT NAP NAP-APPLY",
                                "params": args(True)}, backend, root), "APPLIED_STATE_DRIFT", c)
        nap_row["label"] = n.MASTER_CUE_LABEL
        nap_row["guid"] = "89898989898989898989898989898989"
        refused(lambda: n.main({"mode": "REVERT", "run_id": "NAP-REVERT-GUID",
                                "source_run_id": "NAP-APPLY", "confirm": "REVERT NAP NAP-APPLY",
                                "params": args(True)}, backend, root), "APPLIED_STATE_DRIFT", c)
        nap_row["guid"] = MINTED_NAP
        revert_raw = {"mode": "REVERT", "run_id": "NAP-REVERT", "source_run_id": "NAP-APPLY",
                      "confirm": "REVERT NAP NAP-APPLY", "params": args(True)}
        n.main(revert_raw, backend, root)
        c.check(backend.state == backend.original, "round trip")
        c.check(any(x.startswith("P79_NAP_REVERT_OK") for x in backend.logs), "revert marker")
        c.positive()

    with tempfile.TemporaryDirectory() as root:
        path = n.write_preview(plan, os.path.join(root, "preview.png"))
        data = open(path, "rb").read()
        c.check(data.startswith(b"\x89PNG") and len(data) > 1000, "preview png")
        c.positive()

    bad = copy.deepcopy(plan["breathing_z_keys"]); bad[-1][1] += 0.5
    c.check("SEAM_VALUE" in n.seam_failures(bad, plan["loop_frames"]), "negative seam control")
    c.negative()

    facts = {"markers": plan["markers"][:-1], "breathing_z_keys": plan["breathing_z_keys"],
             "segments": plan["segments_expected_after"], "passage_keys": copy.deepcopy(plan["passage_keys_before"]),
             "owned_actor_labels": plan["actor_labels"], "sequence_package": n.NAP_SEQUENCE,
             "camera_cut_range": [0, plan["total_frames"]]}
    c.check(any(x.startswith("MARKER|") for x in n.verify_after(plan, facts)), "negative marker control")
    c.negative()

    n.record_minted_nap_guid(plan, MINTED_NAP)
    shifted = copy.deepcopy(plan["segments_expected_after"]); shifted[-1]["start"] += 1
    c.check(any(x.startswith("SHIFT|") for x in n.downstream_timing_failures(
        plan["segments_before"], shifted, 2, plan["nap"]["guid"], plan["nap"]["label"],
        plan["delta_ticks"])), "negative timing control")
    c.negative()

    refused(lambda: n.build_plan(fixture(), dict(args(), expected_interaction4_guid="99999999999999999999999999999999")),
            "I4_GUID_DRIFT", c)
    refused(lambda: n.build_plan(fixture(), dict(args(), expected_passage5_guid="99999999999999999999999999999999")),
            "P05_GUID_DRIFT", c)
    snap = fixture(); snap["asset_exists"] = True
    refused(lambda: n.build_plan(snap, args()), "NAP_SEQUENCE_ASSET_EXISTS", c)
    snap = fixture(); snap["actor_labels"].append("P79_Nap_Puss")
    refused(lambda: n.build_plan(snap, args()), "ACTOR_LABEL_COLLISION", c)
    refused(lambda: n.build_plan(fixture(), dict(args(), breath_period_seconds=4.8)), "LOOP_NOT_WHOLE", c)
    refused(lambda: n.build_plan(fixture(), dict(args(), placement_after_label="Scene 4")),
            "PLACEMENT_BETWEEN_S4_I4_REFUSED", c)
    refused(lambda: n.build_plan(fixture(), dict(args(), nap_label="Nap - battery change")),
            "CUE_LABEL_MISMATCH", c)
    snap = fixture()
    snap["segments"].append({"guid": "98989898989898989898989898989898",
                             "label": n.MASTER_CUE_LABEL, "type": "Sequence",
                             "start": 4100, "end": 4200, "first_show_index": 71})
    refused(lambda: n.build_plan(snap, args()), "NAP_ALREADY_COMPILED", c)

    fake_cue = FakeInfinityShowCue(MINTED_NAP)
    try:
        fake_cue.set_editor_property("cue_guid", "00000000000000000000000000000000")
    except n.PlanError as exc:
        c.check("FAKE_CUE_GUID_READ_ONLY" in str(exc), "fake cue GUID is read-only")
    else:
        raise AssertionError("fake cue accepted cue_guid write")

    backend = FakeBackend()
    refused(lambda: n.main({"mode": "DRY", "run_id": "BAD", "confirm": "wrong", "params": args()},
                           backend, tempfile.mkdtemp()), "CONFIRM_MISMATCH", c)

    c.check(c.pos == 3, "positive count")
    c.check(c.neg == 14, "negative count")
    result = {"tool": n.TOOL, "positive": {"passed": c.pos, "total": 3},
              "negative": {"passed": c.neg, "total": 14}, "checks": c.checks, "status": "passed"}
    out = os.path.join(os.path.dirname(__file__), "harness_result.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True); handle.write("\n")
    print("P79_NAP_HARNESS_OK|positive=%d/3|negative=%d/14|checks=%d" % (c.pos, c.neg, c.checks))


if __name__ == "__main__":
    main()
