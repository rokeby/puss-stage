"""Offline positive/negative harness for Job 144.  No Unreal import."""
from __future__ import print_function

import copy
import json
import os
import tempfile

import job144_core as C
import job144_interaction_hangar as J

HERE = os.path.dirname(os.path.abspath(__file__))
PASS = 0
FAIL = 0
ROWS = []


def check(name, fn, expected=None):
    global PASS, FAIL
    try:
        value = fn()
        if expected is not None and value != expected:
            raise AssertionError("%r != %r" % (value, expected))
        PASS += 1; ROWS.append({"name": name, "control": "+", "ok": True})
    except Exception as exc:
        FAIL += 1; ROWS.append({"name": name, "control": "+", "ok": False, "error": repr(exc)})


def rejects(name, fn, contains):
    global PASS, FAIL
    try:
        fn()
        raise AssertionError("accepted")
    except (C.PlanError, J.Stop) as exc:
        if contains not in str(exc):
            FAIL += 1; ROWS.append({"name": name, "control": "-", "ok": False, "error": repr(exc)})
        else:
            PASS += 1; ROWS.append({"name": name, "control": "-", "ok": True})
    except Exception as exc:
        FAIL += 1; ROWS.append({"name": name, "control": "-", "ok": False, "error": repr(exc)})


def actor(label, candidate=True, path=None, tags=None, binding_guids=None):
    return {"label": label, "path": path or "/World/" + label, "class": "StaticMeshActor",
            "outer_level": "/Game/Klara/S2", "tags": tags or [], "scene_candidate": candidate,
            "sequence_binding_guids": binding_guids or []}


def snap(n=2):
    cam = "I2 Hangar Hold Camera" if n == 2 else "S3 Sleight Hangar Camera"
    mouth = "I%d Sleight Mouth Camera" % n
    actors = [actor("Shrine Prop" if n == 2 else "Shore Figure"),
              actor("S%d Hangar Back Wall" % n, False), actor("S%d Hangar Root" % n, False)]
    return {"sequence": "/Game/I%d" % n, "scene_wrapper": "/Game/InfinityStage/Dev/Sequences/LS_DevScene_0%d" % n,
            "playback": [0, 2226], "scene_playback": [0, 5000],
            "markers": {"CST curtain hung": 175, "CST sleight": 1250},
            "wall_candidates": [{"label": "S%d Hangar Side Wall" % n, "root_local_center": [3000, 0, 1500],
                                  "bounds_min": [0, -1000, 0], "bounds_max": [6000, -950, 3000],
                                  "interior_point": [3000, -950, 1500], "interior_normal": [-1, 0, 0],
                                  "rear_clearance_cm": 50},
                                 {"label": "S%d Hangar Back Wall" % n, "root_local_center": [6000, 0, 1500],
                                  "bounds_min": [6000, -1000, 0], "bounds_max": [6050, 1000, 3000],
                                  "interior_point": [6000, 0, 1500], "interior_normal": [-1, 0, 0],
                                  "rear_clearance_cm": 50}],
            "curtain_pose": {"loc": [5600, 0, 0], "roll": 0, "pitch": 0, "yaw": 0},
            "actors": actors, "world_labels": [cam, mouth] + [r["label"] for r in actors],
            "bindings": [{"guid": "A", "name": cam, "spawnable": False},
                         {"guid": "B", "name": mouth, "spawnable": False},
                         {"guid": "C", "name": "Shadow Cat", "spawnable": True,
                          "tracks": [{"class": "MovieSceneSpawnTrack", "sections": [{}]},
                                     {"class": "MovieScene3DTransformTrack", "sections": [{}]}]}],
            "cuts": [{"guid": "A", "range": [0, 1250], "active": True},
                     {"guid": "B", "range": [1250, 2226], "active": True}],
            "fade_tracks": {"interaction": 0, "scene": 0},
            "puppet_bindings": ["Shadow Cat", "Boy Gobo"], "existing_tools": {"job89": "present"}}


def visibility_binding(guid="VIS", label="S2 Ghost Light"):
    return {"guid": guid, "name": label, "spawnable": False, "tracks": [{
        "class": "MovieSceneVisibilityTrack", "track_index": 0, "display": "Visibility",
        "property": "bHidden", "sections": [{"section_index": 0, "range": [0, 1301],
        "channels": [{"channel_index": 0, "name": "None", "base": "None",
                      "keys": [[0, False], [1300, True]]}]}]}]}


def conflict_plan(policy):
    s = snap(2)
    ghost = actor("S2 Ghost Light", path="/World/Ghost", binding_guids=["VIS"])
    s["actors"].append(ghost); s["world_labels"].append(ghost["label"])
    s["bindings"].append(visibility_binding())
    p = C.merged_params({"interaction": 2, "hide_actor_paths": ["/World/Ghost"],
                         "approved_shadow_source_labels": ["Shadow Cat"],
                         "visibility_conflict_policy": policy})
    p["approved_inventory_digest"] = C.inventory_plan(s["actors"], p)["digest"]
    return C.make_plan(s, p)


def planned(n=2, labels=None):
    s = snap(n); p = C.merged_params({"interaction": n, "hide_actor_labels": labels or [],
                                     "approved_shadow_source_labels": ["Shadow Cat"]})
    if labels:
        p["approved_inventory_digest"] = C.inventory_plan(s["actors"], p)["digest"]
    return C.make_plan(s, p)


check("+ I2 plan", lambda: planned(2)["interaction"], 2)
check("+ I3 plan", lambda: planned(3)["interaction"], 3)
check("+ farthest wall", lambda: planned(2)["wall"]["label"], "S2 Hangar Back Wall")
check("+ bHidden property", lambda: planned(2)["visibility"]["property"], "bHidden")
check("+ visibility channel is visible-state", lambda: planned(2)["visibility"]["channel_semantics"], "VISIBLE")
check("+ hidden false", lambda: C.visibility_keys(0, 20)[0][1], False)
check("+ restored true", lambda: C.visibility_keys(0, 20)[-1], [20, True])
check("+ spot off at sleight", lambda: planned(2)["spot"]["intensity_keys"][-1], [1250, 0.0])
check("+ existing puppet census", lambda: planned(2)["puppet_bindings"], ["Shadow Cat", "Boy Gobo"])
check("+ active I2 cut camera", lambda: planned(2)["shadow_camera"]["binding"], "I2 Hangar Hold Camera")
check("+ approved card is spawned", lambda: planned(2)["shadow_sources"][0]["spawn_keys"][0][1], True)
check("+ approved card follows moved curtain", lambda: abs(
    planned(2)["shadow_sources"][0]["pose"]["Location.X"] -
    planned(2)["curtain_target"]["loc"][0]) < 3.0, True)
check("+ exact hide approval", lambda: len(planned(2, ["Shrine Prop"])["visibility"]["actors"]), 1)
check("+ camera framing distance", lambda: planned(2)["camera_distance_cm"] > 700.0, True)
check("+ measured camera override", lambda: C.camera_distance(C.merged_params(
    {"camera_distance_override_cm": 714.009})), 714.009)
check("+ scene wrapper only", lambda: planned(3)["save_packages"][0].startswith("/Game/I") or
      planned(3)["save_packages"][1].startswith("/Game/I"), True)

duplicate_labels = [actor("Twin Prop", path="/World/A"), actor("Twin Prop", path="/World/B")]
check("+ duplicate unselected labels accepted", lambda: len(C.inventory_plan(
    duplicate_labels, C.merged_params({}))["all"]), 2)
check("+ exact actor path selects one duplicate", lambda: C.inventory_plan(
    duplicate_labels, C.merged_params({"hide_actor_paths": ["/World/B"]}))["approved_hide"][0]["path"],
      "/World/B")
tagged = [actor("Twin Prop", path="/World/A", tags=["Job144.I2.Hide"]),
          actor("Twin Prop", path="/World/B")]
check("+ exact tag selection", lambda: C.inventory_plan(
    tagged, C.merged_params({"hide_actor_tags": ["Job144.I2.Hide"]}))["approved_hide"][0]["path"],
      "/World/A")
check("+ visibility conflict defaults safe", lambda: C.merged_params({})["visibility_conflict_policy"], "SAFE_SKIP")
check("+ safe policy skips conflicting actor", lambda: len(conflict_plan("SAFE_SKIP")["visibility"]["actors"]), 0)
check("+ safe policy reports exact conflict", lambda: conflict_plan("SAFE_SKIP")["visibility"]["skipped"][0]["tracks"][0]["guid"], "VIS")
check("+ reuse policy selects existing track", lambda: conflict_plan("REUSE_EXISTING")["visibility"]["actors"][0]["visibility_action"], "REUSE_EXISTING")
check("+ reuse policy extends section", lambda: conflict_plan("REUSE_EXISTING")["visibility"]["actors"][0]["visibility_section_range"], [0, 2227])
check("+ reuse policy extends hidden keys", lambda: conflict_plan("REUSE_EXISTING")["visibility"]["actors"][0]["visibility_keys"][-2:], [[2225, False], [2226, True]])

rejects("- interaction 1", lambda: C.merged_params({"interaction": 1}), "INTERACTION_MUST")
bad = snap(); bad["cuts"][0]["guid"] = "NOPE"
rejects("- unresolved cut", lambda: C.make_plan(bad, C.merged_params({"interaction": 2})), "CUT_BINDING_MISSING")
bad = snap(); bad["world_labels"].remove("I2 Hangar Hold Camera")
rejects("- cut absent from show world", lambda: C.make_plan(bad, C.merged_params({"interaction": 2})), "CUT_NOT_RESOLVED")
rejects("- infrastructure cannot hide", lambda: planned(2, ["S2 Hangar Back Wall"]), "INFRASTRUCTURE")
rejects("- unapproved census", lambda: C.make_plan(snap(), C.merged_params(
    {"interaction": 2, "hide_actor_labels": ["Shrine Prop"], "approved_inventory_digest": "wrong"})), "NOT_APPROVED")
rejects("- rear throw too close", lambda: C.make_plan(snap(), C.merged_params(
    {"interaction": 2, "spot_side": "rear"})), "REAR_THROW_CLEARANCE")
bad = snap(); bad["wall_candidates"][0]["root_local_center"][0] = 6000.5
rejects("- ambiguous back wall", lambda: C.make_plan(bad, C.merged_params({"interaction": 2})), "AMBIGUOUS")
rejects("- invalid frame range", lambda: C.visibility_keys(4, 5), "TOO_SHORT")
bad = snap(); bad["fade_tracks"]["scene"] = 1
rejects("- existing fade conflict", lambda: C.make_plan(bad, C.merged_params({"interaction": 2})), "FADE_TRACK_CONFLICT")
rejects("- missing shadow source", lambda: C.make_plan(snap(), C.merged_params(
    {"interaction": 2, "approved_shadow_source_labels": ["Missing Puppet"]})), "SHADOW_SOURCE_LABELS_MISSING")
bad = snap(); bad["bindings"][2]["tracks"][0]["sections"] = []
rejects("- approved shadow source must have spawn section", lambda: C.make_plan(
    bad, C.merged_params({"interaction": 2, "approved_shadow_source_labels": ["Shadow Cat"]})),
    "SHADOW_SOURCE_SPAWN_TRACK")
rejects("- ambiguous selected label still refused", lambda: C.inventory_plan(
    duplicate_labels, C.merged_params({"hide_actor_labels": ["Twin Prop"]})), "HIDE_LABEL_NOT_UNIQUE")
rejects("- missing exact actor path", lambda: C.inventory_plan(
    duplicate_labels, C.merged_params({"hide_actor_paths": ["/World/Missing"]})), "HIDE_PATHS_MISSING")
rejects("- invalid visibility conflict policy", lambda: C.merged_params(
    {"visibility_conflict_policy": "OVERWRITE"}), "VISIBILITY_CONFLICT_POLICY")

ambiguous = snap(2)
ghost = actor("S2 Ghost Light", path="/World/Ghost", binding_guids=["VIS"])
ambiguous["actors"].append(ghost); ambiguous["world_labels"].append(ghost["label"])
binding = visibility_binding(); binding["tracks"][0]["sections"].append(copy.deepcopy(binding["tracks"][0]["sections"][0]))
ambiguous["bindings"].append(binding)
params_ambiguous = C.merged_params({"hide_actor_paths": ["/World/Ghost"],
                                    "visibility_conflict_policy": "REUSE_EXISTING"})
params_ambiguous["approved_inventory_digest"] = C.inventory_plan(ambiguous["actors"], params_ambiguous)["digest"]
rejects("- ambiguous visibility reuse refused", lambda: C.make_plan(ambiguous, params_ambiguous),
        "VISIBILITY_TRACK_REUSE_AMBIGUOUS")

before = [[0, 0.0], [1250, 50.0], [1400, 60.0]]
after = C.merge_camera(before, 0, 100, 1250, 20.0)
check("+ sleight and later keys preserved", lambda: [x for x in after if x[0] >= 1250], [[1250, 50.0], [1400, 60.0]])
after = C.offset_curtain([[0, 1.0], [175, 2.0], [1249, 3.0], [1250, 4.0]], 175, 1250, 10.0)
check("+ curtain offset bounded", lambda: after, [[0, 1.0], [175, 12.0], [1249, 13.0], [1250, 4.0]])


class FakeBackend(object):
    def __init__(self, root): self.root=root; self.events=[]
    def log(self, text): self.events.append(text)
    def fail(self, text): raise J.Stop(text)
    def preflight(self, mode, confirm):
        if confirm != J.CONFIRMS[mode]: raise J.Stop("CONFIRM")
    def census(self): return {"content": [], "maps": []}
    def build_report(self, params, run): return {"plan": planned(params["interaction"])}
    def apply(self, report, run): return {"packages": ["/Game/I2"], "backup": "B"}
    def revert(self, n, run): return {"packages": ["/Game/I2"], "backup": "B", "archived": "R"}


with tempfile.TemporaryDirectory() as temp:
    fake = FakeBackend(temp)
    check("+ DRY dispatch", lambda: J.main({"mode": "DRY", "confirm": "DRY JOB144",
                                             "params": {"interaction": 2}}, fake)["plan"]["interaction"], 2)
with tempfile.TemporaryDirectory() as temp:
    fake = FakeBackend(temp)
    rejects("- confirmation", lambda: J.main({"mode": "DRY", "confirm": "WRONG",
                                               "params": {"interaction": 2}}, fake), "CONFIRM")

result = {"tool": "JOB144_INTERACTION_HANGAR_HARNESS", "passed": PASS, "failed": FAIL, "tests": ROWS}
with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8", newline="\n") as handle:
    json.dump(result, handle, indent=1, sort_keys=True); handle.write("\n")
print("JOB144_HARNESS_%s|passed=%d|failed=%d|report=%s" % ("OK" if FAIL == 0 else "FAILED", PASS, FAIL,
                                                            os.path.join(HERE, "harness_result.json")))
raise SystemExit(1 if FAIL else 0)
