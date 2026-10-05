"""Offline harness for curtain_sleight.py and leaf_closed_check.py (system Python, no Unreal).

Fixture: I1 (S1 -> I1 -> P02) built from the REAL offline files where they exist:
  hangar_exit_doors_record.json (S1/S2 roots, dims, leaf), CodexStructure/hangar_s1_plan.json (dock),
  CodexSoftGoods/fit_transition_drapes.json (I1 mouth frame + HOLD/FALL sections, 30 Sep apply),
  CodexSoftGoods/DropBake/final13_opening_a06_w188.json (checkpoint 479 = the held sample),
  CodexStructure/mouth_lanterns_record.json (lantern local pose, 210 cd), CodexCameraPilot/walkin_transitions.json (I1).
INFERRED fixture values (the live DRY re-reads them): P02's start pose / lens / arrival speed (taken as the route
start, 150 cm eye, 25 mm, 600 cm, 250 cm/s like P01), the filmback (UE default 23.76 x 13.365), two hangar lights.
Every checker gets a negative control that must FAIL with its named id; positives must pass.
Run:  python test_curtain_sleight.py   -> prints CURTAIN_SLEIGHT_TESTS|pass=N|fail=0
"""
import copy
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SAVED = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import curtain_sleight as cs  # noqa: E402
import leaf_closed_check as lcc  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def load(*parts):
    with open(os.path.join(SAVED, *parts), "r", encoding="utf-8") as handle:
        return json.load(handle)


def has(failures, prefix):
    return any(text.startswith(prefix) for text in failures)


# ------------------------------------------------------------------------------------------------------------ fixture
DOORS = load("CodexConductor", cs.DOORS_RECORD)
WALK = cs.load_walk_planner(os.path.join(SAVED, cs.WALKIN_PLANNER))


def hangar_for(n, root_override=None):
    row = [r for r in DOORS["plan"]["scenes"] if int(r["scene"]) == n][0]
    leaf = [p for p in row["pieces"] if p["role"] == "leaf"][0]
    rec = root_override or DOORS["root_before"][str(n)]
    root = {"loc": list(rec["location"]), "rot": list(rec["rotation"])}
    plan = load("CodexStructure", "hangar_s%d_plan.json" % n)
    dock_local = cs.to_local({"loc": root["loc"], "yaw": root["rot"][2]}, plan["dock"]["loc"])
    dims = row["hangar_dimensions"]
    return {"root": root, "half_w": float(dims["half_w"]), "height": float(dims["height"]), "depth": float(dims["depth"]),
            "door_face_x": float(leaf["location_cm"][0]) - float(leaf["size_cm"][0]) / 2.0,
            "floor_z": float(leaf["location_cm"][2]) - float(leaf["size_cm"][2]) / 2.0 - 0.5, "dock_local": dock_local}


def fixture(n_scene_for_hangar=1):
    fit = load("CodexSoftGoods", "fit_transition_drapes.json")
    row = [r for r in fit["rows"] if r["interaction"] == 1][0]
    hold, fall = row["sections_planned"]
    bake = load("CodexSoftGoods", "DropBake", "final13_opening_a06_w188.json")
    sample = bake["show_start"] + int(round(hold[2] / 24000.0 * cs.CACHE_FPS))
    a = bake["checkpoints"][str(sample)]["aabb_m"]
    yi = min(abs(a["x"][0]), abs(a["x"][1]))
    lan = load("CodexStructure", "mouth_lanterns_record.json")["lantern"]
    d = [lan["aim_local_cm"][i] - lan["local_cm"][i] for i in range(3)]
    norm = math.sqrt(sum(v * v for v in d))
    reg = load("CodexCameraPilot", "walkin_transitions.json")["I1"]
    mouth = {"loc": [row["mouth"]["x"], row["mouth"]["y"], row["mouth"]["z"]], "yaw": row["mouth"]["yaw"]}
    start = cs.to_world(mouth, [0.0, 0.0, 150.0])
    return {
        "n": 1, "fps": 25.0, "tick_rate": 24000.0, "cue_guid": "FIXTURE-GUID", "cue_label": "Interaction 1 — Washing the Boy",
        "sequence": "%s/%s" % (cs.SEQ_DIR, cs.SEQS[1]), "old_end": row["plan"]["end"],
        "drape": {"frame": mouth, "hold": hold, "fall": fall, "spawn": [0, row["plan"]["end"]], "cache": cs.GC_PATH},
        "cache": {"bake_id": bake["id"], "hold_sample_bake_frame": sample, "duration_ticks": 264000,
                  "hang_aabb_cm": {"x": [a["y"][0] * 100.0, a["y"][1] * 100.0], "y": [-yi * 100.0, yi * 100.0],
                                   "z": [a["z"][0] * 100.0, a["z"][1] * 100.0]}},
        "hangar": hangar_for(n_scene_for_hangar),
        "lantern": {"label": "S02 Mouth Lantern", "rel_loc": list(lan["local_cm"]), "rel_dir": [v / norm for v in d],
                    "candela": lan["candela"], "kelvin": lan["kelvin"], "outer_deg": lan["outer_deg"],
                    "inner_deg": lan["inner_deg"], "radius_cm": lan["radius_cm"], "shadows": lan["shadows"]},
        "next": {"label": "Passage 2", "start_pose": {"x": start[0], "y": start[1], "z": start[2], "pitch": 0.0,
                                                      "yaw": mouth["yaw"], "roll": 0.0},
                 "focal": 25.0, "focus": 600.0, "v_end": 250.0},
        "walk": {"landed_after_release_s": float(reg["landed_s"]) - fall[0] / 25.0, "pile_edge_cm": float(reg["pile_edge_cm"])},
        "filmback_mm": [23.76, 13.365],
        "hangar_lights": [{"label": "S1 Hangar Work Light", "intensity": 5000.0},
                          {"label": "S1 Hangar Lattice Glow 01", "intensity": 0.0}],
        "existing_markers": [], "vamps": [], "walkin_tracks": [], "nested": [], "existing_labels": [],
        "scene": {"live_end": 5270, "content_end": 5270}, "exit_block_applied": False, "external_sound": "",
        "use_sequence_length": True, "reveal_when_covered": True, "fold_sequence_exists": False,
    }


def plan_of(inputs, params=None):
    return cs.plan_sleight(inputs, params or {}, WALK)


def fails(plan, inputs):
    return cs.check_sleight(plan, inputs)


BASE = fixture()
PLAN = plan_of(BASE)
F = PLAN["frames"]

# ------------------------------------------------------------------------------------------------- positive controls
f0 = fails(PLAN, BASE)
check("POS I1 plan passes every check", f0 == [], f0)
check("POS timeline I1 @25: sleight 1250, GO/release 1675, end 1913, delta 1275",
      (F["sleight"], F["release"], PLAN["new_end"], PLAN["delta"]) == (1250, 1675, 1913, 1275),
      (F["sleight"], F["release"], PLAN["new_end"], PLAN["delta"]))
check("POS GO label is 'GO 10 curtain' and parses as default (HOLD in a Sequence cue)",
      PLAN["go"][0] == "GO 10 curtain" and cs.parse_go_label(PLAN["go"][0]) == ("10", "curtain", -1), PLAN["go"])
check("POS held sample is bake frame 479 (release - 1 cache frame)", BASE["cache"]["hold_sample_bake_frame"] == 479)
check("POS twin lantern is scaled into the S1 box (s < 1)", 0.0 < PLAN["lantern"]["scale"] < 1.0, PLAN["lantern"]["scale"])
check("POS walk starts after the GO and the plan checker is clean",
      PLAN["walk"]["start_frame"] >= F["release"] and PLAN["walk"]["failures"] == [],
      (PLAN["walk"]["start_frame"], PLAN["walk"]["failures"]))
check("POS only lit hangar lights are keyed", [r["label"] for r in PLAN["lights"]] == ["S1 Hangar Work Light"])

# +control: a different mouth (other yaw / place) still matches: the match is RELATIVE, not absolute numbers
other = copy.deepcopy(BASE)
other["drape"]["frame"] = {"loc": [0.0, 400000.0, 0.0], "yaw": -117.0}
other["next"]["start_pose"].update({"x": 0.0, "y": 400000.0, "yaw": -117.0})
fo = fails(plan_of(other), other)
check("POS(+ctrl) another mouth pose still matches", fo == [], fo)

# +control: S2's ROTATED hangar root (-43.57 deg) passes the ORIENTED box guard ...
s2 = copy.deepcopy(BASE)
s2["hangar"] = hangar_for(2)
plan_s2 = plan_of(s2)
f2 = fails(plan_s2, s2)
check("POS(+ctrl) S2 rotated root passes the oriented guard", f2 == [], f2)
# ... and a naive world AABB (the 4 Oct trap) would have failed it: the guard choice matters on this input
ref = plan_s2["frames_of_reference"]
aabb = s2["cache"]["hang_aabb_cm"]
lo_w, hi_w = cs.world_aabb(ref["hangar_drape_world"], [aabb["x"][0], aabb["y"][0], aabb["z"][0]],
                           [aabb["x"][1], aabb["y"][1], aabb["z"][1]])
naive_lo = [lo_w[i] - ref["root"]["loc"][i] for i in range(3)]
naive_hi = [hi_w[i] - ref["root"]["loc"][i] for i in range(3)]
check("CTRL naive world-AABB guard would FAIL on S2 (why the guard is oriented)",
      bool(cs.inside_hangar(naive_lo, naive_hi, s2["hangar"], 10.0)), (naive_lo, naive_hi))

# ------------------------------------------------------------------------------------------------- 1. frame match
p = copy.deepcopy(PLAN)
p["mouth_camera"]["keys"] = [(k[0], k[1] + 5.0) + tuple(k[2:]) for k in p["mouth_camera"]["keys"]]
check("NEG mouth camera +5 cm -> MATCH_POSE", has(fails(p, BASE), "MATCH_POSE"))
p = copy.deepcopy(PLAN)
p["mouth_camera"]["keys"] = [(k[0],) + tuple(k[1:5]) + (k[5] + 0.2,) + tuple(k[6:]) for k in p["mouth_camera"]["keys"]]
check("NEG mouth camera yaw +0.2 deg -> MATCH_POSE", has(fails(p, BASE), "MATCH_POSE"))
p = copy.deepcopy(PLAN)
p["hangar_drape"]["gc"] = p["hangar_drape"]["gc"][:2] + [0, p["hangar_drape"]["gc"][3]]
check("NEG hangar drape first sample instead of the held sample -> MATCH_SAMPLE", has(fails(p, BASE), "MATCH_SAMPLE"))
p = copy.deepcopy(PLAN)
p["hangar_drape"]["cache"] = "/Game/Scenes/Curtain/Baked/GC_Other"
check("NEG different cache -> MATCH_CACHE", has(fails(p, BASE), "MATCH_CACHE"))
p = copy.deepcopy(PLAN)
p["mouth_camera"]["keys"] = [k[:7] + (40.0,) + k[8:] if k[0] == 0 else k for k in p["mouth_camera"]["keys"]]
check("NEG mouth focal 40 vs 35 -> MATCH_LENS", has(fails(p, BASE), "MATCH_LENS"))
p = copy.deepcopy(PLAN)
p["mouth_card"]["rel_drape"] = [p["mouth_card"]["rel_drape"][0] - 3.0] + p["mouth_card"]["rel_drape"][1:]
check("NEG cards differ -> MATCH_CARD", has(fails(p, BASE), "MATCH_CARD"))
p = copy.deepcopy(PLAN)
p["lantern"]["keys"] = [(f, v * 0.5) for f, v in p["lantern"]["keys"]]
check("NEG twin lantern at half candela -> MATCH_LIGHT", has(fails(p, BASE), "MATCH_LIGHT"))

# ------------------------------------------------------------------------------------------------- 2. the cut
p = copy.deepcopy(PLAN)
p["cuts"][1]["range"][0] += 1
check("NEG one-frame gap at the cut -> CUT_GAP", has(fails(p, BASE), "CUT_GAP"))
p = copy.deepcopy(PLAN)
p["cuts"][1]["range"][0] -= 1
check("NEG one-frame overlap at the cut -> CUT_OVERLAP", has(fails(p, BASE), "CUT_OVERLAP"))
p = copy.deepcopy(PLAN)
p["cuts"] = [{"camera": "hangar_camera", "range": [0, 600]}, {"camera": "mouth_camera", "range": [600, 1250]},
             {"camera": "hangar_camera", "range": [1250, p["new_end"]]}]
check("NEG two camera changes -> CUT_NOT_ONE_SLEIGHT", has(fails(p, BASE), "CUT_NOT_ONE_SLEIGHT"))
p = copy.deepcopy(PLAN)
p["cuts"][1]["range"][1] -= 5
check("NEG cut track ends before playback -> CUT_GAP", has(fails(p, BASE), "CUT_GAP"))

# ------------------------------------------------------------------------------------------------- 3. curtain covers the frame
far = plan_of(BASE, {"sleight_distance_cm": 2600.0})
check("NEG camera 26 m back (frame wider than the curtain) -> COVER_", has(fails(far, BASE), "COVER_"))
p = copy.deepcopy(PLAN)
p["hangar_drape"]["keys"] = [k if k[0] != F["strike"] else (k[0], k[1], k[2], k[3] + 300.0) + k[4:] for k in p["hangar_drape"]["keys"]]
check("NEG hangar drape still flying at the cut -> COVER_HANGAR", has(fails(p, BASE), "COVER_HANGAR"))
wide = plan_of(BASE, {"sleight_focal_mm": 16.0})
check("NEG 16 mm at the cut (frame spills past the hang) -> COVER_", has(fails(wide, BASE), "COVER_"))

# ------------------------------------------------------------------------------------------------- 4. the GO hold
p = copy.deepcopy(PLAN)
p["go"] = [p["go"][0], F["play1"] - 25]
check("NEG GO one second before the play ends -> GO_BEFORE_PLAY_END", has(fails(p, BASE), "GO_BEFORE_PLAY_END"))
p = copy.deepcopy(PLAN)
p["go"] = ["go 10 curtain", p["go"][1]]
check("NEG lower-case go -> GO_PARSE", has(fails(p, BASE), "GO_PARSE"))
p = copy.deepcopy(PLAN)
p["go"] = ["GO 10 PASS curtain", p["go"][1]]
check("NEG explicit PASS -> GO_PARSE (not a hold)", has(fails(p, BASE), "GO_PARSE"))
p = copy.deepcopy(PLAN)
p["mouth_drape"]["hold"][1] -= 1
check("NEG HOLD section ends a frame before the GO -> GO_NOT_ON_RELEASE", has(fails(p, BASE), "GO_NOT_ON_RELEASE"))
vamp = copy.deepcopy(BASE)
vamp["vamps"] = [[1600, 1700]]
check("NEG GO inside a vamp -> GO_IN_VAMP", has(fails(PLAN, vamp), "GO_IN_VAMP"))
dup = copy.deepcopy(BASE)
dup["existing_markers"] = [["GO 10 HOLD boy", 100]]
check("NEG GO number already used -> GO_DUPLICATE", has(fails(PLAN, dup), "GO_DUPLICATE"))

# ------------------------------------------------------------------------------------------------- 5. mouth ready before the cut
p = copy.deepcopy(PLAN)
p["mouth_card"]["spawn"] = [[F["sleight"], True], [F["release"], False]]
r = fails(p, BASE)
check("NEG mouth card spawns ON the cut -> READY_MOUTH and STATE_CHANGES_ACROSS_CUT",
      has(r, "READY_MOUTH") and has(r, "STATE_CHANGES_ACROSS_CUT"), r)
late = copy.deepcopy(BASE)
late["drape"]["spawn"] = [F["sleight"] - 5, late["drape"]["spawn"][1]]
check("NEG mouth drape spawns 5 frames before the cut -> READY_MOUTH", has(fails(PLAN, late), "READY_MOUTH"))
p = copy.deepcopy(PLAN)
p["hangar_drape"]["spawn"] = [[F["fly0"], True], [F["sleight"] + 1, False]]
check("NEG hangar drape despawns 1 frame after the cut -> STATE_CHANGES_ACROSS_CUT",
      has(fails(p, BASE), "STATE_CHANGES_ACROSS_CUT"))
p = copy.deepcopy(PLAN)
p["lantern"]["keys"] = [(0, 0.0), (F["fly0"], 0.0), (F["fly1"], p["lantern"]["candela"]),
                        (F["sleight"] + 2, p["lantern"]["candela"]), (F["sleight"] + 3, 0.0)]
check("NEG twin lantern off 3 frames after the cut -> STATE_CHANGES_ACROSS_CUT",
      has(fails(p, BASE), "STATE_CHANGES_ACROSS_CUT"))
lazy = plan_of(BASE, {"push_s": 46.5})
check("NEG push arrives 0.5 s before the cut -> READY", has(fails(lazy, BASE), "READY"))

# ------------------------------------------------------------------------------------------------- 6. inside-box guard
raw = plan_of(BASE, {"lantern_scale": 1.0})
check("NEG unscaled twin lantern (13 m house left in a 10 m half-width hangar) -> BOX",
      has(fails(raw, BASE), "BOX: twin lantern"), raw["lantern"]["root"]["loc"])
deep = plan_of(BASE, {"curtain_from_door_cm": -100.0})
check("NEG drape behind the door face -> BOX", has(fails(deep, BASE), "BOX: hangar drape"))
narrow = copy.deepcopy(BASE)
narrow["hangar"]["half_w"] = 900.0
check("NEG hangar half width 9 m (drape 9.4 m) -> BOX", has(fails(plan_of(narrow), narrow), "BOX: hangar drape"))

# ------------------------------------------------------------------------------------------------- 7. fly-in, fold, walk
low = copy.deepcopy(BASE)
low["hangar"]["height"] = 2400.0
check("NEG 24 m hangar: flown hem visible in the wide -> FLY_IN_VISIBLE_IN_WIDE",
      has(fails(plan_of(low), low), "FLY_IN_VISIBLE_IN_WIDE"))
fold = plan_of(BASE, {"fold_end_s": 49.0})
check("NEG fold ends 1 s before the cut (< 2 s margin) -> FOLD_LATE", has(fails(fold, BASE), "FOLD_LATE"))
p = copy.deepcopy(PLAN)
p["walk"]["start_frame"] = F["release"] - 10
check("NEG walk starts during the GO hold -> WALK_BEFORE_GO", has(fails(p, BASE), "WALK_BEFORE_GO"))
p = copy.deepcopy(PLAN)
p["mouth_camera"]["keys"].insert(1, (F["sleight"] + 100,) + tuple(p["mouth_camera"]["keys"][0][1:]))
check("NEG an extra mouth-camera key before the walk -> WALK_BEFORE_GO", has(fails(p, BASE), "WALK_BEFORE_GO"))
p = copy.deepcopy(PLAN)
p["hangar_camera"]["keys"].append((F["strike"] + 10, 6000.0) + tuple(p["hangar_camera"]["keys"][-1][2:]))
check("NEG hangar camera driven into the drape -> CAMERA_PATH", has(fails(p, BASE), "CAMERA_PATH"))

# ------------------------------------------------------------------------------------------------- 8. idempotent DRY
r1 = cs.build_dry_report(BASE, {}, WALK, "pre")
r2 = cs.build_dry_report(copy.deepcopy(BASE), {}, WALK, "pre")
check("POS DRY twice -> same plan digest and same refusals", r1["plan_digest"] == r2["plan_digest"]
      and r1["refusals"] == r2["refusals"] and r1["apply_ready"], (r1["plan_digest"], r2["plan_digest"], r1["refusals"]))
moved = copy.deepcopy(BASE)
moved["hangar"]["root"]["loc"][0] += 1.0
check("NEG(digest sensitivity) a 1 cm root change changes the digest",
      cs.build_dry_report(moved, {}, WALK, "pre")["plan_digest"] != r1["plan_digest"])
ra = cs.build_dry_report(BASE, {}, WALK, "applied")
check("NEG DRY after APPLY -> ALREADY_APPLIED and no second plan",
      ra["plan"] is None and has(ra["refusals"], "ALREADY_APPLIED") and not ra["apply_ready"])
ro = cs.build_dry_report(BASE, {}, WALK, "orphan")
check("NEG half-applied state -> ORPHAN_SLEIGHT_STATE", has(ro["refusals"], "ORPHAN_SLEIGHT_STATE"))
try:
    cs.plan_sleight(BASE, {"sleight_secs": 50}, WALK)
    check("NEG unknown param refuses", False)
except cs.PlanError as exc:
    check("NEG unknown param refuses", "UNKNOWN_PARAMS" in str(exc))

# ------------------------------------------------------------------------------------------------- 9. live gates
for key, value, ident in (("exit_block_applied", True, "EXIT_BLOCK_STILL_APPLIED"),
                          ("scene", {"live_end": 7061, "content_end": 5270}, "SCENE_STILL_LONG"),
                          ("external_sound", "InfinityExternalSoundAuthority.DECLARED_UNPAUSABLE", "GO_WOULD_BE_DEMOTED"),
                          ("walkin_tracks", ["Interaction 1 — Stalls Camera"], "WALKIN_PRESENT"),
                          ("fold_sequence_exists", True, "FOLD_SEQUENCE_EXISTS"),
                          ("nested", ["/Game/X"], "NESTED_SEQUENCES_IN_INTERACTION"),
                          ("use_sequence_length", False, "USE_SEQUENCE_LENGTH_OFF"),
                          ("existing_labels", ["S1 Sleight Hangar Camera"], "ACTOR_EXISTS")):
    g = copy.deepcopy(BASE)
    g[key] = value
    refusals, _ = cs.live_gates(g, {}, "pre")
    check("NEG live gate %s" % ident, has(refusals, ident), refusals)
refusals, warns = cs.live_gates(BASE, {}, "pre")
check("POS live gates clean on the fixture; placeholder/test warnings present",
      refusals == [] and has(warns, "FOLD_PLACEHOLDER") and has(warns, "TEST_EXPECTS_STALLS"), refusals)

# ------------------------------------------------------------------------------------------------- 10. GO parser parity
with open(os.path.join(SAVED, "CodexCueing", "cue_list_tool.py"), "r", encoding="utf-8") as handle:
    src = handle.read()
GO_RE = re.compile(re.search(r'GO_RE = re\.compile\(r"(.*)"\)', src).group(1))
labels = ["GO 10 curtain", "GO 10 HOLD curtain", "GO 1.5 PASS x", "go 10 curtain", "GO curtain", "GO 1a x",
          "GO .", "  GO 7  ", "GO 3 HOLD", "Go 2 y"]
parity = []
for lab in labels:
    ours = cs.parse_go_label(lab)
    theirs = GO_RE.match(lab)
    parity.append((lab, ours is not None, theirs is not None))
# The port follows the TRANSPORT (InfinityStageTransportController.cpp:601-645), which is what holds the show.
# cue_list_tool.py's GO_RE is looser on one shape: "GO 1a x" (the C++ rejects a number with a letter; the regex
# matches "1" and takes "a x" as the label). Recorded as a finding, not papered over.
diverge = [x[0] for x in parity if x[1] != x[2]]
check("POS GO parser agrees with cue_list_tool.py's GO_RE except the known 'GO 1a x' divergence",
      diverge == ["GO 1a x"], diverge)
check("POS the sleight's own GO label parses identically in both", cs.parse_go_label(PLAN["go"][0]) is not None
      and GO_RE.match(PLAN["go"][0]) is not None and GO_RE.match(PLAN["go"][0]).group(1) == "10")

# ------------------------------------------------------------------------------------------------- 11. revert exactness
SNAP = {"playback": [0, 638],
        "bindings": [
            {"name": cs.MOUTH_DRAPE, "guid": "G-DRAPE", "parent": "",
             "tracks": [{"class": "MovieSceneGeometryCacheTrack", "name": "", "sections": [BASE["drape"]["hold"], BASE["drape"]["fall"]]},
                        {"class": "MovieSceneSpawnTrack", "name": "", "sections": [[0, 638]]}]},
            {"name": "Interaction 1 — Stalls Camera", "guid": "G-STALLS", "parent": "", "tracks": []},
            {"name": "Curtain Rig - Fire Safety Curtain", "guid": "G-RIG", "parent": "",
             "tracks": [{"class": "MovieSceneBoolTrack", "name": "", "sections": [[0, 639]]}]}],
        "root_tracks": [], "cuts": [["G-STALLS", 0, 638, True]], "markers": [["note", 12]], "level_labels": []}
SNAP = cs.normalize_snapshot(SNAP)   # the live _snapshot() is normalized the same way
names = [PLAN["hangar_camera"]["label"], PLAN["hangar_camera"]["label"] + "/CameraComponent",
         PLAN["mouth_camera"]["label"], PLAN["mouth_camera"]["label"] + "/CameraComponent",
         PLAN["lantern"]["label"], PLAN["lantern"]["label"] + "/LightComponent",
         PLAN["hangar_drape"]["name"], PLAN["hangar_card"]["name"], PLAN["mouth_card"]["name"]]
for row in PLAN["lights"]:
    names += [row["label"], row["label"] + "/LightComponent"]
GUIDS = {name: "NEW-%02d" % i for i, name in enumerate(names)}
after = cs.apply_model(SNAP, PLAN, GUIDS)
record = {"snapshot_before": SNAP, "created_binding_guids": sorted(GUIDS.values()),
          "created_markers": [list(m) for m in PLAN["markers"]] + [list(PLAN["go"])],
          "created_labels": [PLAN["hangar_camera"]["label"], PLAN["mouth_camera"]["label"], PLAN["lantern"]["label"]]}
check("POS APPLY model changes the sequence (sanity)", cs.snapshot_diff(SNAP, after) != [])
check("POS APPLY model: tails moved (spawn 638->1913, rig 639->1914), drape re-timed",
      [b for b in after["bindings"] if b["guid"] == "G-RIG"][0]["tracks"][0]["sections"] == [[0, 1914]]
      and [t for t in [b for b in after["bindings"] if b["guid"] == "G-DRAPE"][0]["tracks"]
           if t["class"] == "MovieSceneSpawnTrack"][0]["sections"] == [[0, 1913]])
back = cs.revert_model(after, record)
check("POS REVERT model restores the snapshot exactly", cs.snapshot_diff(back, SNAP) == [], cs.snapshot_diff(back, SNAP))
for skip, ident in ((("cuts",), "cuts"), (("markers",), "markers"), (("sections",), "bindings"),
                    (("actors",), "level_labels"), (("playback",), "playback")):
    d = cs.snapshot_diff(cs.revert_model(after, record, skip=skip), SNAP)
    check("NEG REVERT that forgets %s is caught (%s differs)" % (skip[0], ident), any(ident in x for x in d), d)
again = cs.apply_model(SNAP, PLAN, GUIDS)
check("POS APPLY model deterministic", cs.snapshot_diff(again, after) == [])

# ------------------------------------------------------------------------------------------------- 12. leaf closed check
leaf_s1 = [p for p in [r for r in DOORS["plan"]["scenes"] if r["scene"] == 1][0]["pieces"] if p["role"] == "leaf"][0]
leaf_s3 = [p for p in [r for r in DOORS["plan"]["scenes"] if r["scene"] == 3][0]["pieces"] if p["role"] == "leaf"][0]
closed = {"parent": "S1 Hangar Root", "location": [6024.95, 0.0, 225.0], "rotation": [0.0, 0.0, 0.0],
          "scale": [0.5, 2.99, 4.49]}
check("POS leaf at the record's closed pose -> CLOSED", lcc.leaf_verdict(closed, leaf_s1, "S1 Hangar Root")[0] == "CLOSED",
      lcc.leaf_verdict(closed, leaf_s1, "S1 Hangar Root"))
opened = dict(closed, rotation=[0.0, 0.0, -85.0])
check("NEG leaf swung 85 deg -> NOT_CLOSED", lcc.leaf_verdict(opened, leaf_s1, "S1 Hangar Root")[0] == "NOT_CLOSED")
nudged = dict(closed, location=[6024.95, 0.2, 225.0])
check("NEG leaf 2 mm off -> NOT_CLOSED", lcc.leaf_verdict(nudged, leaf_s1, "S1 Hangar Root")[0] == "NOT_CLOSED")
check("NEG leaf detached -> NOT_ON_ROOT", lcc.leaf_verdict(dict(closed, parent=None), leaf_s1, "S1 Hangar Root")[0] == "NOT_ON_ROOT")
s3_closed = {"parent": "S3 Hangar Root", "location": leaf_s3["location_cm"], "rotation": [0.0, 0.0, 0.0],
             "scale": [1.0, 1.0, 1.0]}
check("POS S3 mesh leaf (mesh_size 0 thick -> scale 1) -> CLOSED",
      lcc.leaf_verdict(s3_closed, leaf_s3, "S3 Hangar Root")[0] == "CLOSED", lcc.expected_closed(leaf_s3))

# ------------------------------------------------------------------------------------------------- report
passed = sum(1 for _, ok, _ in RESULTS if ok)
failed = [(name, detail) for name, ok, detail in RESULTS if not ok]
for name, ok, detail in RESULTS:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  | " + str(detail)[:400]))
print("PLAN_SUMMARY|frames=%s|new_end=%d|delta=%d (%.2f s)|go=%s|lantern s=%.3f cd=%.1f root=%s|walk_start=%d|"
      "landed_s=%.2f|matched_world=%s|hangar_matched_root=%s|digest=%s"
      % (json.dumps(F, sort_keys=True), PLAN["new_end"], PLAN["delta"], PLAN["delta_s"], PLAN["go"],
         PLAN["lantern"]["scale"], PLAN["lantern"]["candela"], [round(v, 1) for v in PLAN["lantern"]["root"]["loc"]],
         PLAN["walk"]["start_frame"], PLAN["walk"]["landed_s"],
         [round(v, 1) for v in PLAN["mouth_camera"]["level_world"]["loc"]],
         [round(v, 1) for v in cs.pose_at([k[:7] for k in PLAN["hangar_camera"]["keys"]], F["sleight"])["loc"]],
         PLAN["digest"]))
print("CURTAIN_SLEIGHT_TESTS|pass=%d|fail=%d" % (passed, len(failed)))
sys.exit(1 if failed else 0)
