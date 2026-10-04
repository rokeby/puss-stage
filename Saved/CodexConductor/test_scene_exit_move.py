"""Offline harness for scene_exit_move.py (system Python, no Unreal).

Positive controls run the planner on the REAL door geometry in
hangar_exit_doors_record.json (measured 3 Oct) for S1, S2, S4, S5, S6; S3 must
refuse.  Negative controls each break one thing and require the matching
failure, so every checker is shown able to fail.
Run:  python test_scene_exit_move.py   -> prints SCENE_EXIT_MOVE_TESTS|pass=N|fail=0
"""
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scene_exit_move as sem  # noqa: E402

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def doors_rows():
    with io.open(os.path.join(HERE, sem.DOORS_RECORD_NAME), encoding="utf-8") as handle:
        record = json.load(handle)
    return {int(row["scene"]): row for row in record["plan"]["scenes"]}


# Eye heights in the root frame: dock z minus root z (hangar plans + record
# root_before, 3 Oct).  S3's root sits at z -120 with its floor at +120.
EYE = {1: 150.0, 2: 180.0, 3: 300.0, 4: 180.0, 5: 180.0, 6: 180.0}
SCENE_END = 2000
HOLD = 25


def handoff_cuts(window_start):
    return [{"label": "Scene N — External Sound — Entry Handoff Camera", "start": 0, "end": 375,
             "active": True, "handoff": True},
            {"label": "Scene N — External Sound — Exit Handoff Camera", "start": 375, "end": SCENE_END,
             "active": True, "handoff": True}]


def main():
    rows = doors_rows()
    summary = {}
    for n in (1, 2, 4, 5, 6):
        report = sem.build_dry_report(rows[n], EYE[n], SCENE_END, HOLD, handoff_cuts(0), [],
                                      camera_label=sem.CAMERA_LABEL_PATTERN % n,
                                      camera_tags=["SceneExitMove", "SceneExitMove.S%d" % n])
        rep = report["plan"]["report"]
        summary[n] = {"window_s": rep["total_s"], "on_screen_s": rep["on_screen_s_including_exit_hold"],
                      "walk_cm": round(rep["walk_cm"], 1), "min_clear_cm": round(rep["min_leaf_clearance_cm"], 1)}
        check("S%d plan passes" % n, report["apply_ready"], report["refusals"])
        check("S%d warns metal black" % n, any("EXIT_BLACK_IS_METAL" in w for w in report["warnings"]))
        check("S%d window ends at scene_end-hold" % n, rep["window"][1] == SCENE_END - HOLD)
        last = report["plan"]["camera_keys"][-1]
        geom = report["geometry"]
        check("S%d ends past the door face, before the black" % n,
              geom["door_face_x"] < last[1] < geom["black_front_x"])
        check("S%d leaf closed pose == recorded leaf" % n,
              abs(report["plan"]["leaf_keys"][0][1] - geom["leaf_center"][0]) < 1e-6)

    # S3 refuses on the backdrop, and passes the geometry when the backdrop is declared cut.
    s3 = sem.build_dry_report(rows[3], EYE[3], SCENE_END, HOLD, handoff_cuts(0), [])
    check("S3 refuses: backdrop behind leaf", any(r.startswith("S3_BACKDROP_BEHIND_LEAF") for r in s3["refusals"]),
          s3["refusals"])
    s3_cut = sem.build_dry_report(rows[3], EYE[3], SCENE_END, HOLD, handoff_cuts(0), [],
                                  params={"s3_backdrop_cut": True})
    check("S3 geometry passes once the backdrop is cut", s3_cut["apply_ready"], s3_cut["refusals"])

    # Hinge maths: 90 deg about the -Y jamb puts the leaf in the room, flush to the jamb line.
    geom = sem.door_geometry(rows[1])
    poly = sem.leaf_polygon(geom, 90.0, "left")
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    check("hinge 90: leaf spans 299 cm toward the camera", abs((max(xs) - min(xs)) - 299.0) < 1e-6)
    check("hinge 90: leaf stays on the -Y side", max(ys) < 0.0 and abs(min(ys) - (-149.5)) < 1e-6, (min(ys), max(ys)))
    check("hinge 90: leaf never goes behind the wall face", max(xs) <= geom["door_face_x"] + 1e-6)
    poly_r = sem.leaf_polygon(geom, 90.0, "right")
    check("right hinge mirrors", abs(min(p[1] for p in poly_r) - (149.5 - 50.0)) < 1e-6)
    for theta in (0.0, 30.0, 60.0, 100.0):
        check("leaf never reaches the Exit Black at %g" % theta,
              max(p[0] for p in sem.leaf_polygon(geom, theta, "left")) < geom["black_front_x"])

    # ---- negative controls: each must produce its own failure ----
    def plan_fail(params, expect):
        plan = sem.plan_exit_move(geom, EYE[1], SCENE_END, HOLD, params)
        failures = sem.check_plan(plan, geom, params)
        check("NEG %s" % expect, any(expect in f for f in failures), failures)

    # door opens too late for the walk -> camera hits the leaf
    plan_fail({"walk_delay_s": -1.0, "door_open_s": 6.0, "seat_distance_cm": 400.0}, "from the leaf")
    # final pose in front of the door face -> refused by the planner itself
    try:
        sem.plan_exit_move(geom, EYE[1], SCENE_END, HOLD, {"final_gap_cm": 600.0})
        check("NEG final pose before the door face refused", False)
    except sem.PlanError:
        check("NEG final pose before the door face refused", True)
    # a doorway too narrow for the lens at the final pose -> frame not filled
    narrow = dict(geom, opening_half_w=5.0)
    plan = sem.plan_exit_move(narrow, EYE[1], SCENE_END, HOLD)
    check("NEG frame-fill checker can fail", any("not filled" in f for f in sem.check_plan(plan, narrow)))
    # eye outside the doorway
    plan = sem.plan_exit_move(geom, 600.0, SCENE_END, HOLD)
    check("NEG eye above the doorway", any("outside the doorway" in f or "not filled" in f
                                           for f in sem.check_plan(plan, geom)))
    # window before the Scene starts
    plan = sem.plan_exit_move(geom, EYE[1], 100, HOLD)
    check("NEG window before scene start", any("before the Scene" in f for f in sem.check_plan(plan, geom)))
    # tampered keys: speed, backwards, hinge, closed pose
    base = sem.plan_exit_move(geom, EYE[1], SCENE_END, HOLD)
    fast = copy.deepcopy(base)
    k = list(fast["camera_keys"][100]); k[1] += 50.0; fast["camera_keys"][100] = tuple(k)
    check("NEG speed spike detected", any("exceeds" in f or "backwards" in f or "acceleration" in f
                                          for f in sem.check_plan(fast, geom)))
    off = copy.deepcopy(base)
    k = list(off["leaf_keys"][10]); k[1] += 5.0; off["leaf_keys"][10] = tuple(k)
    check("NEG leaf off its hinge detected", any("leaves its hinge" in f for f in sem.check_plan(off, geom)))
    shut = copy.deepcopy(base)
    k = list(shut["leaf_keys"][0]); k[5] = 3.0; shut["leaf_keys"][0] = tuple(k)
    check("NEG leaf not closed at start detected", any("closed pose" in f for f in sem.check_plan(shut, geom)))
    gap = copy.deepcopy(base)
    del gap["camera_keys"][50]
    check("NEG missing frame detected", any("one per display frame" in f for f in sem.check_plan(gap, geom)))
    # ramps longer than the walk
    try:
        sem.walk_profile(100.0, 250.0, 1.0, 0.8)
        check("NEG ramps longer than walk refused", False)
    except sem.PlanError:
        check("NEG ramps longer than walk refused", True)

    # gates
    win = base["report"]["window"][0]
    interior = [{"label": "Shot A", "start": win - 10, "end": win + 5, "active": False, "handoff": False}]
    check("NEG inactive interior cut overlapping the window refuses",
          sem.gate_root_cuts(interior, win, SCENE_END))
    check("POS interior cut ending at the window passes",
          not sem.gate_root_cuts([dict(interior[0], end=win)], win, SCENE_END))
    check("POS handoff cuts are exempt (the match re-ranges them)",
          not sem.gate_root_cuts(handoff_cuts(win), win, SCENE_END))
    nested = [{"track": "MovieSceneCinematicShotTrack", "sequence": "/Game/Scenes/LS_Animals_1",
               "in_parent": [-1, SCENE_END], "active": True, "sub_cut_count": 4}]
    check("NEG nested shot cuts in the window refuse (S1 LS_Animals_1 shape)",
          sem.gate_nested(nested, win, SCENE_END))
    check("POS nested sub without cuts passes", not sem.gate_nested([dict(nested[0], sub_cut_count=0)], win, SCENE_END))
    rise = [{"track": "MovieSceneSubTrack", "sequence": "/Game/InfinityStage/RigAtmos/LS_S1_HangarRise",
             "in_parent": [0, win + 1], "active": True, "sub_cut_count": 0}]
    check("NEG rise still running in the window refuses", sem.gate_rise(rise, win))
    check("POS rise done before the window passes", not sem.gate_rise([dict(rise[0], in_parent=[0, win])], win))
    check("NEG handoff-looking label refused",
          sem.looks_like_handoff_camera("Scene 1 — External Sound — Exit Handoff Camera", []))
    check("NEG handoff tags refused",
          sem.looks_like_handoff_camera("anything", ["InfinityStage.SceneHandoff", "InfinityStage.SceneExit"]))
    check("POS our camera label is not a handoff",
          not sem.looks_like_handoff_camera("S1 Exit Door Camera", ["SceneExitMove", "SceneExitMove.S1"]))
    full = sem.build_dry_report(rows[1], EYE[1], SCENE_END, HOLD, handoff_cuts(0), nested)
    check("NEG dry report carries the nested refusal", any("NESTED_CUTS_IN_WINDOW" in r for r in full["refusals"]))
    check("ticks->frames: 24000 ticks = 25 frames", sem.frames_from_ticks(24000) == 25)

    failed = [row for row in RESULTS if not row[1]]
    for name, ok, detail in RESULTS:
        if not ok:
            print("FAIL", name, detail)
    print("SUMMARY", json.dumps(summary))
    print("SCENE_EXIT_MOVE_TESTS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
