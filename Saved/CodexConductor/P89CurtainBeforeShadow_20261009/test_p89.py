"""Offline positive/negative controls for P89. No Unreal import or project mutation."""
import copy
import importlib.util
import json
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "p89_curtain_before_shadow.py")
SPEC = importlib.util.spec_from_file_location("p89_offline", PATH)
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
RESULTS = []


def check(name, condition, detail=None):
    RESULTS.append((name, bool(condition), detail))


def rejects(name, fn, text):
    try:
        fn()
    except Exception as error:  # noqa: BLE001
        check(name, text in str(error), str(error))
        return
    check(name, False, "did not reject")


def spec(cls, name, prop, channel_rows, start=0, end=100):
    return {"class": cls, "name": name, "prop": prop, "path": prop,
            "sections": [{"range": [start, end], "channels": channel_rows}]}


def channel(name, keys, default=None):
    return {"name": name, "raw": name + "_183", "default": default, "keys": copy.deepcopy(keys)}


def fixture(interaction=1, curtain_start=10, hung_frame=20, dark_key=20, peak_frame=30,
            vis=None, gc_start=10, end=100):
    spawn = spec("MovieSceneSpawnTrack", "Spawned", "", [channel("Spawned", [[curtain_start, True], [80, False]], False)], 0, end)
    transform = spec("MovieScene3DTransformTrack", P.SLEIGHT_TRACK, "", [
        channel("Location.X", [[curtain_start, 100.0], [hung_frame, 100.0]], 100.0),
        channel("Location.Y", [[curtain_start, 20.0], [hung_frame, 20.0]], 20.0),
        channel("Location.Z", [[curtain_start, 900.0], [hung_frame, 0.0], [79, 0.0]], 900.0),
        channel("Rotation.X", [[curtain_start, 0.0], [79, 0.0]], 0.0),
        channel("Rotation.Y", [[curtain_start, 0.0], [79, 0.0]], 0.0),
        channel("Rotation.Z", [[curtain_start, 5.0], [79, 5.0]], 5.0),
        channel("Scale.X", [], 1.0), channel("Scale.Y", [], 1.0), channel("Scale.Z", [], 1.0),
    ], 0, end)
    gc = {"class": "MovieSceneGeometryCacheTrack", "name": "Geometry Cache", "prop": "", "path": "",
          "sections": [{"range": [gc_start, 80], "channels": [], "start_offset": 100, "end_offset": 999,
                        "asset": "/Game/GC"}]}
    intensity = spec("MovieSceneFloatTrack", P.SPOT_TRACK, "Intensity",
                     [channel("Intensity", [[0, 0.0], [dark_key, 0.0], [peak_frame, 100.0], [70, 100.0], [75, 0.0]], 0.0)], 0, end)
    evaluated = [[f, P.interp(intensity["sections"][0]["channels"][0]["keys"], f, 0.0)] for f in range(end)]
    return {"interaction": interaction, "sequence": "/Game/I%d" % interaction, "fps": 25.0, "playback": [0, end],
            "spawn": spawn, "transform": transform, "gc": gc, "visibility": copy.deepcopy(vis or []),
            "spot_intensity": intensity, "spot_evaluated": evaluated,
            "hung_pose": {"Location.X": 100.0, "Location.Y": 20.0, "Location.Z": 0.0,
                          "Rotation.X": 0.0, "Rotation.Y": 0.0, "Rotation.Z": 5.0,
                          "Scale.X": 1.0, "Scale.Y": 1.0, "Scale.Z": 1.0},
            "owned": {"spawn": {}, "transform": {}, "gc": {}, "visibility": [], "spot_intensity": {}}}


# UE 5.8 normalization traps.
check("P channel suffix normalised", P.norm_channel("Location.Y_183") == "Location.Y")
check("P unsuffixed channel preserved", P.norm_channel("Location.Y") == "Location.Y")
check("P enum wrapper normalised", P.enum_token("<MovieSceneCompletionMode.RESTORE_STATE: 1>") == "RESTORE_STATE")
check("P normal enum preserved", P.enum_token("LightUnits.CANDELAS") == "CANDELAS")

# Negative: the validator refuses curtain-after-spot and inadequate margin.
bad = fixture(curtain_start=10, hung_frame=20, dark_key=15, peak_frame=25)
first_bad = P.first_positive_frame(bad["spot_evaluated"], 1.0e-4)
rejects("N curtain-after-spot refused", lambda: P.assert_order(bad, bad["hung_pose"], first_bad, 13, P.merged_params({})),
        "CURTAIN_AFTER_SPOT_REFUSED")

# Positive: a curtain already hung early enough is accepted and remains exactly untouched.
good = fixture(curtain_start=0, hung_frame=0, dark_key=20, peak_frame=30, gc_start=0)
good["transform"]["sections"][0]["channels"][2]["keys"] = [[0, 0.0], [79, 0.0]]
good_before = json.dumps(good, sort_keys=True)
good_plan = P.build_plan(good, {})
check("P curtain-before-spot accepted", good_plan["timing"]["before"]["margin_frames"] >= 13, good_plan["timing"])
check("P compliant interaction marked unchanged", not good_plan["needs_change"] and good_plan["timing"]["changed_tracks"] == [])
check("P unchanged interaction specs untouched", all(good_plan["writes"][k] == good[k] for k in
      ("spawn", "transform", "gc", "visibility", "spot_intensity")))
check("P planner does not mutate input", json.dumps(good, sort_keys=True) == good_before)

# Fault repair: hold the existing hung pose from zero, extend spawn/GC, preserve later unspawn and fall events.
fault = fixture(curtain_start=10, hung_frame=20, dark_key=20, peak_frame=30, gc_start=10)
plan = P.build_plan(fault, {})
timing = plan["timing"]
check("P faulty interaction requests change", plan["needs_change"])
check("P fixed curtain ready from frame zero", timing["after"]["curtain_ready"] == 0, timing)
check("P default margin is 0.5 s at 25 fps", timing["margin_frames_required"] == 13)
check("P fixed order clears margin", timing["after"]["margin_frames"] >= 13, timing)
check("P later unspawn preserved", P.channels(plan["writes"]["spawn"])["Spawned"]["keys"][-1] == [80, False])
check("P GC offsets preserved", plan["writes"]["gc"]["sections"][0]["start_offset"] == 100 and
      plan["writes"]["gc"]["sections"][0]["end_offset"] == 999)
check("P GC end preserved", plan["writes"]["gc"]["sections"][0]["range"] == [0, 80])
check("P spot unchanged when curtain-zero supplies margin", plan["writes"]["spot_intensity"] == fault["spot_intensity"])
check("P transform held at recorded hung Z", P.interp(P.channels(plan["writes"]["transform"])["Location.Z"]["keys"], 0) == 0.0)

# Working visibility is true=visible and is extended; inert bHiddenInGame is reported but not treated as control.
working_vis = spec("MovieSceneVisibilityTrack", "Visibility", "bHidden",
                   [channel("Visibility", [[10, True], [80, False]], False)], 0, 100)
with_vis = fixture(vis=[working_vis])
vis_plan = P.build_plan(with_vis, {})
check("P bHidden visibility uses TRUE as visible", P.bool_at(P.channels(vis_plan["writes"]["visibility"][0])["Visibility"]["keys"], 0, False))
check("P visibility later-off preserved", P.channels(vis_plan["writes"]["visibility"][0])["Visibility"]["keys"][-1] == [80, False])
inert_vis = spec("MovieSceneVisibilityTrack", "Visibility", "bHiddenInGame",
                 [channel("Visibility", [[0, False]], False)], 0, 100)
inert = fixture(vis=[inert_vis])
inert_plan = P.build_plan(inert, {})
state = P.curtain_state(dict(inert, spawn=inert_plan["writes"]["spawn"], transform=inert_plan["writes"]["transform"],
                             gc=inert_plan["writes"]["gc"], visibility=inert_plan["writes"]["visibility"]),
                        0, inert["hung_pose"], P.merged_params({}))
check("P inert bHiddenInGame does not hide curtain", state["ready"] and state["inert_visibility_tracks"] == ["Visibility"], state)
rejects("N unknown visibility property refused", lambda: P.visibility_at([
    spec("MovieSceneVisibilityTrack", "Visibility", "Odd", [channel("Visibility", [[0, True]], True)])], 0), "VISIBILITY_PROPERTY")

# Edge case: spot starts too soon; shift only initial ramp, keep plateau/fade-out events fixed.
early = fixture(curtain_start=2, hung_frame=4, dark_key=4, peak_frame=20, gc_start=2)
early_plan = P.build_plan(early, {})
check("P early spot fade shifted", "spot_intensity" in early_plan["timing"]["changed_tracks"])
check("P shifted spot meets margin", early_plan["timing"]["after"]["spot_first_nonzero"] >= 13, early_plan["timing"])
early_keys = P.channels(early_plan["writes"]["spot_intensity"])["Intensity"]["keys"]
check("P later spot events untouched", early_keys[-2:] == [[70, 100.0], [75, 0.0]], early_keys)
overlap = fixture(curtain_start=2, hung_frame=3, dark_key=4, peak_frame=6, gc_start=2)
overlap["spot_intensity"]["sections"][0]["channels"][0]["keys"] = [[0, 0.0], [4, 0.0], [6, 100.0], [7, 100.0], [8, 0.0]]
overlap["spot_evaluated"] = [[f, P.interp(overlap["spot_intensity"]["sections"][0]["channels"][0]["keys"], f, 0.0)] for f in range(100)]
rejects("N fade shift refuses event overlap", lambda: P.build_plan(overlap, {}), "SHIFTED_FADE_OVERLAPS_NEXT_EVENT")

# Parameters, tolerance, and unowned-state masking.
check("P float readback tolerance accepts float32 drift", not P.compare(7482.804199, 7482.8042))
rejects("N margin out of range refused", lambda: P.merged_params({"margin_seconds": -1}), "MARGIN_SECONDS")
rejects("N unknown argument refused", lambda: P.merged_params({"creative_guess": 1}), "UNKNOWN_PARAMS")
rejects("N I3 apply refused until I1 is fixed", lambda: P.enforce_apply_order(3, True), "I1_MUST_BE_FIXED_FIRST")
P.enforce_apply_order(3, False)
check("P I3 apply accepted after I1 is compliant", True)
snap = {"playback": [0, 100], "bindings": [{"guid": "A", "name": "D", "parent": "", "tracks": [
    {"class": "MovieSceneSpawnTrack", "name": "Spawned", "prop": "", "sections": []},
    {"class": "Other", "name": "Keep", "prop": "X", "sections": []}]}]}
owned = {"spawn": {"binding_guid": "A", "class": "MovieSceneSpawnTrack", "name": "Spawned", "prop": ""},
         "transform": {"binding_guid": "Z", "class": "T", "name": "", "prop": ""},
         "gc": {"binding_guid": "Z", "class": "G", "name": "", "prop": ""},
         "spot_intensity": {"binding_guid": "Z", "class": "F", "name": "", "prop": ""}, "visibility": []}
masked = P.without_owned(snap, owned)
check("P owned mask retains unrelated track", masked["bindings"][0]["tracks"] == [snap["bindings"][0]["tracks"][1]])

for name, ok, detail in RESULTS:
    if not ok:
        print("FAIL", name, str(detail)[:1000])
passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = len(RESULTS) - passed
print("P89_OFFLINE_HARNESS|pass=%d|fail=%d|total=%d" % (passed, failed, len(RESULTS)))
sys.exit(1 if failed else 0)
