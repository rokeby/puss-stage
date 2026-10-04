"""Offline harness for scene_exit_block.py (system Python, no Unreal).

Positive controls plan the block on the REAL door geometry in
hangar_exit_doors_record.json (applied 3 Oct) with the last MEASURED Scene
lengths (see SCENES below; stale by design - the live DRY re-reads them).
Negative controls each break one thing and require the matching failure, so
every checker is shown able to fail.
Run:  python test_scene_exit_block.py   -> prints SCENE_EXIT_BLOCK_TESTS|pass=N|fail=0
"""
import copy
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scene_exit_block as seb  # noqa: E402

RESULTS = []
EXIT_MOVE = os.path.join(HERE, seb.EXIT_MOVE_NAME)


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))


def doors_rows():
    with io.open(os.path.join(HERE, seb.DOORS_RECORD_NAME), encoding="utf-8") as handle:
        record = json.load(handle)
    return {int(row["scene"]): row for row in record["plan"]["scenes"]}


# Eye heights in the root frame (dock z from CodexStructure/hangar_s*_plan.json
# minus root z from the doors record root_before).
EYE = {1: 150.0, 2: 180.0, 3: 300.0, 4: 180.0, 5: 180.0, 6: 180.0}
# S3 rise [0, 744] = 31 s @ 24 (probe 30 Sep; nest_s3_record rise_end_s 31.0).
# Last measured (content_end, fps): S1/S4 probe_interaction_cut_binding.json
# (30 Sep); S2/S6 nest_s*_record.json scene_end_s 31.0 (3 Oct); S3
# extend_scene_playback_scene3_refused.json 1573 @ 24 fps; S5
# extend_scene_playback.json 1225 @ 25 (3 Oct).
SCENES = {1: (5270, 25.0), 2: (775, 25.0), 3: (1573, 24.0), 4: (775, 25.0), 5: (1225, 25.0), 6: (775, 25.0)}


def cuts_for(n, end):
    hold = 24 if n == 3 else 25
    rows = [{"label": "Scene %d — External Sound — Entry Handoff Camera" % n, "start": 0, "end": end - hold,
             "active": True, "handoff": True},
            {"label": "Scene %d — External Sound — Exit Handoff Camera" % n, "start": end - hold, "end": end,
             "active": True, "handoff": True}]
    if n == 3:
        rows.insert(1, {"label": "ClamCam1", "start": 81, "end": 1501, "active": True, "handoff": False})
    return rows


def nested_for(n, end):
    rise = {"track": "MovieSceneSubTrack", "sequence": "/Game/InfinityStage/RigAtmos/LS_S%d_HangarRise" % n,
            "active": True, "in_parent": [0, {1: 775, 3: 744, 4: 775}.get(n, end)], "sub_cut_count": 0}
    rows = [rise]
    if n == 1:
        rows.append({"track": "MovieSceneCinematicShotTrack", "sequence": "/Game/Scenes/LS_Animals_1",
                     "active": True, "in_parent": [-1, 5270], "sub_cut_count": 4})
    if n == 3:
        rows.append({"track": "MovieSceneCinematicShotTrack", "sequence": "/Game/Scenes/LS_Clams",
                     "active": True, "in_parent": [-1, 1454], "sub_cut_count": 1})
    return rows


def report_for(n, params=None, rows=None, cuts=None, nested=None, content_end=None):
    rows = rows or doors_rows()
    end, fps = SCENES[n]
    end = content_end if content_end is not None else end
    sem = seb.load_exit_move(EXIT_MOVE, fps)
    hold = seb.hold_frames_from_ticks(24000, fps)
    return sem, seb.build_block_dry_report(sem, rows[n], rows[n]["hangar_dimensions"], EYE[n], end, hold,
                                           cuts if cuts is not None else cuts_for(n, end),
                                           nested if nested is not None else nested_for(n, end), params)


def has(items, needle):
    return any(needle in item for item in items)


def temp_copy(transform):
    folder = tempfile.mkdtemp(prefix="seb_test_")
    path = os.path.join(folder, seb.EXIT_MOVE_NAME)
    with io.open(EXIT_MOVE, encoding="utf-8") as handle:
        text = handle.read()
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(transform(text))
    return folder, path


def main():
    rows = doors_rows()
    summary = {}
    # ---------------------------------------------------------------- positives
    for n in (1, 2, 4, 5, 6):
        sem, report = report_for(n)
        rep = report["plan"]["report"]
        end, fps = SCENES[n]
        summary[n] = {"content_end": end, "w0": rep["w0"], "w1": rep["w1"], "new_end": rep["new_end"],
                      "grow_s": round(rep["grow_s"], 2), "raise_cm": round(rep["raise_cm"], 1),
                      "door_from_dock_cm": rows[n]["door_center_dock_cm"][0] + 500.0}
        check("S%d block passes" % n, report["apply_ready"], report["refusals"])
        check("S%d starts at the old end" % n, rep["w0"] == end)
        check("S%d puppet minute is 1500 frames" % n, rep["puppet"] == [end, end + 1500], rep["puppet"])
        check("S%d grows by 1791 frames (60 + 3 + 7.64 + 1 s)" % n, rep["new_end"] - end == 1791, rep["new_end"] - end)
        check("S%d exit hold is the last 25 frames" % n, rep["exit_hold"] == [rep["new_end"] - 25, rep["new_end"]])
        check("S%d warns metal black + rise + card + growth" % n,
              has(report["warnings"], "EXIT_BLACK_IS_METAL") and has(report["warnings"], "RISE_SECTION_ENDS")
              and has(report["warnings"], "CARD_IS_PLAIN_LIT") and has(report["warnings"], "SHOW_GROWS"),
              report["warnings"])
    # Reuse proof: the B part is byte-identical to scene_exit_move's own plan at that end.
    import scene_exit_move as sem_direct  # offline import is safe: unreal is None here
    sem, report = report_for(2)
    rep = report["plan"]["report"]
    direct = sem_direct.plan_exit_move(sem_direct.door_geometry(rows[2]), EYE[2], rep["new_end"], 25)
    check("B keys identical to scene_exit_move's own planner",
          direct["camera_keys"] == report["plan"]["exit_plan"]["camera_keys"]
          and direct["leaf_keys"] == report["plan"]["leaf_keys"])
    check("loaded planner has no main()", not hasattr(sem, "main") and not hasattr(sem, "_gather"))
    check("camera keys = 1 hold key + B's per-frame keys",
          len(report["plan"]["camera_keys"]) == 1 + len(direct["camera_keys"]))
    labels = [m[0] for m in report["plan"]["markers"]]
    check("five EXB markers in order", len(labels) == 5 and all(l.startswith("EXB ") for l in labels))
    mode = seb.extend_mode_for("Scene 2 — External Sound", rep["new_end"])
    check("extend mode uses extend_scene_playback's keys",
          set(mode) == {"scene_label", "new_end_frame", "dry_run"} and mode["dry_run"] is True
          and isinstance(mode["new_end_frame"], int))
    # S3: 24 fps, backdrop and tail gap.
    sem3, s3 = report_for(3)
    check("S3 refuses: backdrop behind leaf", has(s3["refusals"], "S3_BACKDROP_BEHIND_LEAF"), s3["refusals"])
    check("S3 refuses: tail gap after ClamCam1", has(s3["refusals"], "TAIL_GAP"), s3["refusals"])
    check("S3 planner runs at 24 fps", sem3.FPS == 24.0 and s3["plan"]["report"]["puppet"][1]
          - s3["plan"]["report"]["puppet"][0] == 1440)
    _, s3ok = report_for(3, {"s3_backdrop_cut": True, "start_at_last_interior_end": True})
    rep3 = s3ok["plan"]["report"]
    check("S3 passes once backdrop cut + start at last interior end", s3ok["apply_ready"], s3ok["refusals"])
    check("S3 block starts at ClamCam1's end (1501)", rep3["w0"] == 1501, rep3["w0"])
    summary[3] = {"content_end": 1573, "w0": rep3["w0"], "new_end": rep3["new_end"],
                  "grow_s": round(rep3["grow_s"], 2), "raise_cm": round(rep3["raise_cm"], 1)}
    check("S3 curtain hangs from its raised door floor (z 120)",
          abs(s3ok["plan"]["cg"]["hem_hung_z"] - 122.0) < 1e-6)
    sem25 = seb.load_exit_move(EXIT_MOVE, 25.0)
    check("FPS override changes frame counts (24 vs 25)",
          sem3.plan_exit_move(sem3.door_geometry(rows[1]), 150.0, 5000, 24)["report"]["window"]
          != sem25.plan_exit_move(sem25.door_geometry(rows[1]), 150.0, 5000, 24)["report"]["window"])
    check("ticks -> frames: 24000 = 25 @25, 24 @24",
          seb.hold_frames_from_ticks(24000, 25) == 25 and seb.hold_frames_from_ticks(24000, 24) == 24)
    # Playback state machine and decision gate.
    plan_file = {"content_end": 775, "new_end": 2566}
    check("state pre (no plan)", seb.playback_state(775, {}) == ("pre", 775))
    check("state extended", seb.playback_state(2566, plan_file) == ("extended", 775))
    check("state pre (plan, not yet extended)", seb.playback_state(775, plan_file) == ("pre", 775))
    check("NEG state drift", seb.playback_state(900, plan_file) == ("drift", None))
    check("POS decided", seb.decided({"decided_by": "Gary", "scenes": [1, 2]}, 2))
    check("NEG undecided: empty decided_by", not seb.decided({"decided_by": " ", "scenes": [2]}, 2))
    check("NEG undecided: scene not listed", not seb.decided({"decided_by": "Gary", "scenes": [1]}, 2))
    check("NEG undecided: no file", not seb.decided({}, 2))

    # ---------------------------------------------------------------- negatives (geometry)
    def fails(params, needle, n=2):
        try:
            _, rep_ = report_for(n, params)
        except seb.PlanError as exc:
            return needle in str(exc), str(exc)
        return has(rep_["refusals"], needle), rep_["refusals"]

    for name, params, needle in (
            ("narrow curtain does not cover the door", {"curtain_width_cm": 350.0}, "does not cover"),
            ("short curtain does not cover the door", {"curtain_height_cm": 470.0}, "does not cover"),
            ("curtain at the door face", {"curtain_offset_cm": 0.0}, "not in front of the door face"),
            ("hem off the floor", {"curtain_floor_gap_cm": 30.0}, "off the floor"),
            ("curtain too close to the seat", {"curtain_offset_cm": 850.0}, "1 m in front"),
            ("oversized card leaves the frame", {"card_width_cm": 700.0}, "not inside the hold frame"),
            ("card behind the curtain", {"card_gap_cm": -5.0}, "behind the curtain"),
            ("card overhangs the curtain", {"curtain_width_cm": 470.0, "curtain_cover_margin_cm": 5.0}, "overhangs"),
            ("curtain taller than the hangar", {"curtain_height_cm": 2800.0}, "leaves the hangar box on z"),
            ("curtain wider than the hangar", {"curtain_width_cm": 2100.0}, "leaves the hangar box on y"),
            ("unknown param refuses", {"curtian_width_cm": 700.0}, "UNKNOWN_PARAMS")):
        ok, detail = fails(params, needle)
        check("NEG " + name, ok, detail)

    # Tampered plans: each checker must be able to fail on its own.
    sem, base = report_for(2)
    geom, hangar = base["geometry"], rows[2]["hangar_dimensions"]

    def tamper(mutate, needle, params=None):
        plan = copy.deepcopy(base["plan"])
        mutate(plan)
        failures = seb.check_block(sem, plan, geom, hangar, params)
        return any(needle in f for f in failures), failures

    def move_cam(plan):
        k = list(plan["camera_keys"][0]); k[1] += 1.0; plan["camera_keys"][0] = tuple(k)

    def lift_early(plan):
        k = list(plan["curtain_keys"][1]); k[3] += 1.0; plan["curtain_keys"][1] = tuple(k)

    def not_raised(plan):
        ms = plan["report"]["move"][0]
        plan["curtain_keys"] = [tuple(list(k[:3]) + [k[3] - 10.0] + list(k[4:])) if k[0] == ms else k
                                for k in plan["curtain_keys"]]

    def door_early(plan):
        plan["report"]["door_start_frame"] = plan["report"]["move"][0]

    def low_raise(plan):
        plan["report"]["raise_cm"] = 300.0

    def short_hold(plan):
        plan["report"]["puppet"] = [plan["report"]["puppet"][0], plan["report"]["puppet"][0] + 1400]

    def bad_sum(plan):
        plan["report"]["new_end"] += 1

    def dup_marker(plan):
        plan["markers"][1] = (plan["markers"][0][0], plan["markers"][1][1])

    def backwards(plan):
        k = list(plan["curtain_keys"][-2]); k[3] = -1000.0; plan["curtain_keys"][-2] = tuple(k)

    for name, mutate, needle in (("camera moves in the hold", move_cam, "camera moves during the puppet hold"),
                                 ("curtain moves in the hold", lift_early, "curtain moves during the puppet hold"),
                                 ("curtain not raised at move start", not_raised, "not fully raised"),
                                 ("door opens before the curtain is gone", door_early, "door starts before"),
                                 ("raise below the door top", low_raise, "does not clear the door top"),
                                 ("puppet hold not 60 s", short_hold, "puppet hold is not"),
                                 ("segments do not add up", bad_sum, "do not add up"),
                                 ("duplicate marker", dup_marker, "not unique"),
                                 ("curtain keys backwards", backwards, "backwards")):
        ok, detail = tamper(mutate, needle)
        check("NEG " + name, ok, detail)
    # Raised curtain in frame: a high eye (400) plans a high raise; cut it to the door-top minimum.
    _, high = report_for(2, None, content_end=775)
    sem_h = seb.load_exit_move(EXIT_MOVE, 25.0)
    plan_h = seb.plan_block(sem_h, geom, 400.0, 775, 25, cuts_for(2, 775))
    check("POS high eye still plans clean", not seb.check_block(sem_h, plan_h, geom, hangar),
          seb.check_block(sem_h, plan_h, geom, hangar))
    plan_h["report"]["raise_cm"] = (geom["opening_z"][1] + 50.0) - plan_h["cg"]["hem_hung_z"]
    plan_h["curtain_keys"] = [tuple(list(k[:3]) + [min(k[3], plan_h["cg"]["curtain"]["center"][2]
                                                       + plan_h["report"]["raise_cm"])] + list(k[4:]))
                              for k in plan_h["curtain_keys"]]
    f_h = seb.check_block(sem_h, plan_h, geom, hangar)
    check("NEG raised curtain still in frame", any("in frame" in f for f in f_h), f_h)

    # Gates reused from scene_exit_move, on the block window.
    end = SCENES[2][0]
    over = cuts_for(2, end) + [{"label": "Shot", "start": 700, "end": 900, "active": False, "handoff": False}]
    _, r = report_for(2, cuts=over)
    check("NEG interior cut into the block refuses (inactive too)", has(r["refusals"], "ROOT_CUT_OVERLAP"), r["refusals"])
    _, r = report_for(2, cuts=cuts_for(2, end) + [{"label": "Shot", "start": 100, "end": end,
                                                   "active": True, "handoff": False}])
    check("POS interior cut ending exactly at W0 passes", r["apply_ready"], r["refusals"])
    _, r = report_for(2, cuts=cuts_for(2, end) + [{"label": "Shot", "start": 100, "end": 600,
                                                   "active": True, "handoff": False}])
    check("NEG interior cut ending early leaves a TAIL_GAP", has(r["refusals"], "TAIL_GAP"), r["refusals"])
    s1_nested = nested_for(1, 5270)
    s1_nested[1] = dict(s1_nested[1], in_parent=[-1, 6000])
    _, r = report_for(1, nested=s1_nested)
    check("NEG S1 shot running into the block refuses", has(r["refusals"], "NESTED_CUTS_IN_WINDOW"), r["refusals"])
    s1_rise = nested_for(1, 5270)
    s1_rise[0] = dict(s1_rise[0], in_parent=[0, 6000])
    _, r = report_for(1, nested=s1_rise)
    check("NEG rise still running in the block refuses", has(r["refusals"], "RISE_OVERLAPS_WINDOW"), r["refusals"])
    check("POS our labels are not handoff cameras",
          not any(sem.looks_like_handoff_camera(p % 2, ["SceneExitBlock"]) for p in seb.LABELS.values()))

    # Inside-box checker, directly.
    check("POS inside box", not seb.inside_box([10, -100, 0], [5900, 100, 1000], hangar, 6000.0, 0.0, 10.0))
    check("NEG box: through the door face", seb.inside_box([10, -100, 0], [6001, 100, 1000], hangar, 6000.0, 0.0, 10.0) == ["x"])
    check("NEG box: underground (sunk REST frame)", "z" in seb.inside_box([10, -100, -3500], [5900, 100, -2900],
                                                                        hangar, 6000.0, 0.0, 10.0))

    # Loader refusals on a drifted copy of scene_exit_move.py.
    for name, transform, needle in (
            ("API drift", lambda t: t.replace("def plan_exit_move(geom, eye_z_root,", "def plan_exit_move(geom, eye_z,"),
             "EXIT_MOVE_API_DRIFT"),
            ("top-level call", lambda t: t.replace("\nclass PlanError", "\nprint('side effect')\n\nclass PlanError"),
             "EXIT_MOVE_SIDE_EFFECT"),
            ("no _here", lambda t: t.replace("def _here():", "def _there():"), "EXIT_MOVE_SHAPE")):
        folder, path = temp_copy(transform)
        try:
            seb.load_exit_move(path, 25.0)
            check("NEG loader refuses " + name, False, "loaded")
        except seb.PlanError as exc:
            check("NEG loader refuses " + name, needle in str(exc), str(exc))
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    folder, path = temp_copy(lambda t: t)
    try:
        check("POS loader accepts an unmodified copy", seb.load_exit_move(path, 25.0).FPS == 25.0)
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    failed = [row for row in RESULTS if not row[1]]
    for name, ok, detail in RESULTS:
        if not ok:
            print("FAIL", name, detail)
    print("SUMMARY", json.dumps(summary, sort_keys=True))
    print("SCENE_EXIT_BLOCK_TESTS|pass=%d|fail=%d" % (len(RESULTS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
