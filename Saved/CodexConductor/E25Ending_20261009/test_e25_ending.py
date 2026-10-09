"""Offline +/- harness.  Does not import Unreal."""

import copy
import json
import os
import shutil
import tempfile

import e25_ending as E


PASS = 0
FAIL = 0
POS = 0
NEG = 0


def check(name, condition, positive=False, negative=False):
    global PASS, FAIL, POS, NEG
    if condition:
        PASS += 1
        if positive: POS += 1
        if negative: NEG += 1
        print("PASS|" + name)
    else:
        FAIL += 1
        print("FAIL|" + name)


def rejects(name, fn, text):
    try:
        fn()
    except Exception as error:
        check(name, text in str(error), negative=True)
        return
    check(name, False, negative=True)


def fixture():
    return {
        "segments": [
            {"guid": "1" * 32, "label": "Scene 6 — External Sound", "type": "SCENE", "start": 1000, "end": 2000, "first_show_index": 18},
            {"guid": "2" * 32, "label": "Closing — Sweeping Up", "type": "SEQUENCE", "start": 2000, "end": 2100, "first_show_index": 19},
        ],
        "actors": [
            {"path": "/Game/Map.PersistentLevel.OpeningCamera", "label": "Opening — Stalls Camera", "class": "CineCameraActor", "hidden": False},
            {"path": "/Game/Map.PersistentLevel.P01", "label": "Passage 01 - Structure", "class": "InfinityStagePassageActor", "hidden": False},
            {"path": "/Game/Map.PersistentLevel.Curtain", "label": "Opening — Curtain", "class": "GeometryCacheActor", "hidden": False},
            {"path": "/Game/Map.PersistentLevel.P02", "label": "Passage 02 - Structure", "class": "InfinityStagePassageActor", "hidden": False},
            {"path": "/Game/Map.PersistentLevel.Hangar", "label": "Hangar S4", "class": "Actor", "hidden": False},
            {"path": "/Game/Map.PersistentLevel.Sky", "label": "Editor Sky", "class": "SkyAtmosphere", "hidden": True},
        ],
        "asset_exists": False,
        "owned_mask_exists": False,
        "tick_resolution": 24000.0,
        "opening_end_pose": {"location": [-900.0, 0.0, 160.0], "rotation": [5.0, 0.0, 0.0], "focal_mm": 35.0},
    }


class FakeBackend(object):
    def __init__(self):
        self.before = fixture()
        self.state = copy.deepcopy(self.before)
        self.dirty = {"content": [], "maps": []}
        self.logs = []
        self.args = None
        self.plan = None

    def log(self, text): self.logs.append(text)
    def stop(self, text): self.logs.append(text)
    def census(self): return copy.deepcopy(self.dirty)
    def preflight(self, args, unused):
        self.args = args
        if self.dirty != {"content": [], "maps": []}: raise E.PlanError("DIRTY")
    def inspect(self, args, plan=None):
        if plan is None or not self.state["asset_exists"]:
            return copy.deepcopy(self.state)
        return dict(copy.deepcopy(self.state), sequence_package=args["sequence_package"],
                    camera_cut_range=[0, plan["total_frames"]], camera_cut_actor_path=plan["camera_actor_path"],
                    stage_actor_paths=copy.deepcopy(plan["stage_actor_paths"]),
                    hidden_actor_paths=copy.deepcopy(plan["hidden_actor_paths"]),
                    visibility=copy.deepcopy(plan["visibility"]), mask_label=plan["mask"]["label"],
                    camera_keys=copy.deepcopy(plan["camera_keys"]))
    def backup(self, run, packages, prefix="PreE25Ending"):
        return {"root": "/fake/%s-%s" % (prefix, run), "files": list(packages)}
    def apply(self, plan, args):
        self.plan = plan
        self.state["asset_exists"] = True; self.state["owned_mask_exists"] = True
        minted = "A" * 32
        ending = copy.deepcopy(plan["ending"]); ending["guid"] = minted
        self.state["segments"] = E.expected_segments(plan["segments_before"], plan["anchors"]["scene6_index"], ending, plan["delta_ticks"])
        self.dirty = {"content": [args["show_package"], args["master_package"], args["sequence_package"]],
                      "maps": [args["level_package"]]}
        return {"minted_guid": minted, "label": E.CUE_LABEL}
    def save(self, packages):
        self.dirty = {"content": [], "maps": []}
        return list(packages)
    def revert(self, record, args):
        self.state = copy.deepcopy(self.before)
        archive = "/Game/InfinityStage/Dev/Sequences/_Reverted/LS_Ending_OpeningStage_" + record["run_id"]
        self.dirty = {"content": [args["show_package"], args["master_package"], archive], "maps": [args["level_package"]]}
        return {"archived_sequence": archive}


def pinned(plan):
    return {
        "expected_scene6_guid": plan["anchors"]["scene6_guid"],
        "expected_closing_guid": plan["anchors"]["closing_guid"],
        "expected_camera_path": plan["camera_actor_path"],
        "expected_stage_actor_paths": plan["stage_actor_paths"],
        "expected_hidden_actor_paths": plan["hidden_actor_paths"],
    }


def main():
    plan = E.build_plan(fixture(), {})
    check("UE 5.8 enum string normalised", E.enum_name("<InfinityCueType.SEQUENCE: 2>") == "SEQUENCE", positive=True)
    check("placement after S6 before Closing", [r["label"] for r in plan["segments_expected_after"]] ==
          ["Scene 6 — External Sound", E.CUE_LABEL, "Closing — Sweeping Up"], positive=True)
    check("black then arrival camera", [r["frame"] for r in plan["camera_keys"]] == [0, 50, 300], positive=True)
    check("visibility trap semantics explicit", plan["visibility"]["stage"] == [[0, False], [50, True], [300, True]], positive=True)
    check("sky hidden and mask present", any("Sky" in p for p in plan["hidden_actor_paths"]) and plan["mask"]["label"], positive=True)
    check("optional beats excluded", len(plan["optional_later_beats_not_built"]) == 4, positive=True)

    root = tempfile.mkdtemp(prefix="e25-harness-")
    try:
        backend = FakeBackend()
        dry = E.main({"mode": "DRY", "run_id": "DRY1", "confirm": "DRY E25 DRY1", "params": {}}, backend, root)
        check("DRY writes plan only", not backend.state["asset_exists"] and os.path.isfile(os.path.join(root, "e25_ending_plan.json")), positive=True)
        params = pinned(dry)
        applied = E.main({"mode": "APPLY", "run_id": "APPLY1", "confirm": "APPLY E25 APPLY1", "params": params}, backend, root)
        check("APPLY minted read-only GUID and verified", applied["plan"]["ending"]["guid"] == "A" * 32 and applied["status"] == "saved_readback_verified", positive=True)
        result = E.main({"mode": "REVERT", "run_id": "REV1", "source_run_id": "APPLY1",
                         "confirm": "REVERT E25 APPLY1", "params": params}, backend, root)
        check("REVERT restores original spine", not backend.state["asset_exists"] and "_Reverted" in result["archived_sequence"], positive=True)
    finally:
        shutil.rmtree(root)

    rejects("bad confirm", lambda: E.main({"mode": "DRY", "run_id": "X", "confirm": "yes"}, FakeBackend(), tempfile.mkdtemp()), "CONFIRM_MISMATCH")
    bad = fixture(); bad["asset_exists"] = True
    rejects("dedupe sequence", lambda: E.build_plan(bad, {}), "ENDING_ARTIFACT_EXISTS")
    bad = fixture(); bad["owned_mask_exists"] = True
    rejects("dedupe owned mask", lambda: E.build_plan(bad, {}), "ENDING_ARTIFACT_EXISTS")
    bad = fixture(); bad["segments"].insert(1, copy.deepcopy(bad["segments"][0])); bad["segments"][1]["label"] = E.CUE_LABEL
    rejects("dedupe cue", lambda: E.build_plan(bad, {}), "ENDING_ALREADY_COMPILED")
    bad = fixture(); bad["segments"].insert(1, {"guid": "3"*32, "label": "Other", "start": 2000, "end": 2001, "first_show_index": 19})
    rejects("refuse S6 tail ambiguity", lambda: E.build_plan(bad, {}), "S6_CLOSING_BOUNDARY_DRIFT")
    rejects("S6 GUID drift", lambda: E.build_plan(fixture(), {"expected_scene6_guid": "F"*32}), "S6_GUID_DRIFT")
    rejects("Closing GUID drift", lambda: E.build_plan(fixture(), {"expected_closing_guid": "F"*32}), "CLOSING_GUID_DRIFT")
    rejects("camera census drift", lambda: E.build_plan(fixture(), {"expected_camera_path": "/wrong"}), "CAMERA_CENSUS_DRIFT")
    rejects("stage census drift", lambda: E.build_plan(fixture(), {"expected_stage_actor_paths": ["/wrong"]}), "STAGE_CENSUS_DRIFT")
    rejects("hidden census drift", lambda: E.build_plan(fixture(), {"expected_hidden_actor_paths": ["/wrong"]}), "HIDDEN_CENSUS_DRIFT")
    bad = fixture(); bad["actors"] = [a for a in bad["actors"] if a["label"] != "Editor Sky"]
    rejects("sky must stay hidden", lambda: E.build_plan(bad, {}), "NO_SKY_ACTOR")
    bad = fixture(); bad["actors"] = [a for a in bad["actors"] if a["label"] != "Opening — Stalls Camera"]
    rejects("camera must resolve", lambda: E.build_plan(bad, {}), "OPENING_CAMERA_COUNT")
    bad = fixture(); bad["actors"] = [a for a in bad["actors"] if a["label"] != "Opening — Curtain"]
    rejects("opening curtain required", lambda: E.build_plan(bad, {}), "NO_OPENING_CURTAIN")
    bad = fixture(); bad["actors"] = [a for a in bad["actors"] if a["label"] != "Passage 01 - Structure"]
    rejects("P01 stage and lighting required", lambda: E.build_plan(bad, {}), "NO_P01_STAGE_LIGHTING")
    rejects("role overlap", lambda: E.normalise_args({"expected_stage_actor_paths": ["x"], "expected_hidden_actor_paths": ["x"]}), "ACTOR_ROLE_OVERLAP")
    rejects("black duration bound", lambda: E.normalise_args({"black_seconds": 0}), "BLACK_SECONDS_RANGE")
    rejects("arrival duration bound", lambda: E.normalise_args({"arrival_seconds": 0}), "ARRIVAL_SECONDS_RANGE")
    check("CueGuid input removed as read-only", "ending_cue_guid" not in E.normalise_args({"ending_cue_guid": "F"*32}), positive=True)
    rejects("invalid minted GUID", lambda: E.record_minted_guid(plan, "<Guid>"), "MINTED_GUID_INVALID")
    broken = copy.deepcopy(plan); E.record_minted_guid(broken, "A"*32)
    facts = {"segments": broken["segments_expected_after"], "sequence_package": E.SEQUENCE,
             "camera_cut_range": [0, broken["total_frames"]], "camera_cut_actor_path": "/wrong",
             "stage_actor_paths": broken["stage_actor_paths"], "hidden_actor_paths": broken["hidden_actor_paths"],
             "visibility": broken["visibility"], "mask_label": broken["mask"]["label"],
             "camera_keys": broken["camera_keys"]}
    check("negative scene-cut control", "CAMERA_CUT_BINDING" in E.verify_after(broken, facts), negative=True)
    facts["camera_cut_actor_path"] = broken["camera_actor_path"]; facts["visibility"] = {}
    check("negative visibility control", "VISIBILITY_KEYS" in E.verify_after(broken, facts), negative=True)

    result = {"positive": POS, "negative": NEG, "checks": PASS, "failed": FAIL}
    with open(os.path.join(os.path.dirname(__file__), "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True); handle.write("\n")
    if FAIL:
        raise SystemExit("E25_ENDING_HARNESS_FAILED|pass=%d|fail=%d" % (PASS, FAIL))
    print("E25_ENDING_HARNESS_OK|positive=%d|negative=%d|checks=%d" % (POS, NEG, PASS))


if __name__ == "__main__":
    main()
