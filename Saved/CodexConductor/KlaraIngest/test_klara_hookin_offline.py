"""Offline harness for klara_hookin.py v2 pure planning (no Unreal). Every positive case has a negative control that
must FAIL the same check, so a planner that always says yes (or always no) cannot pass.
Run: python Saved/CodexConductor/KlaraIngest/test_klara_hookin_offline.py
Numbers: her ranges [meas] census_report.md (S1 -10.333..200.267 s, S2 0..5 s, S4 0..164 s; 30 fps, tick 24000);
narration frames [meas] s1_narration_after_voices_record.json / scene_narration_standin_record.json; hangar docks
[meas, 30 Sep] Saved/CodexStructure/hangar_s1_record.json, hangar_s2_record.json, hangar_s4_plan.json; footprints
[meas] offline 2-98% pivot parse of her maps (HOOKIN_PLAN.md section 3).
"""
import copy
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import klara_hookin as K  # noqa: E402  (importing without unreal must run nothing)

S1_LO, S1_HI = -310, 6008
FPS = 25.0
with open(os.path.join(HERE, "klara_hookin_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)
HANGARS = ARGS["hangars"]


def her(lo, hi, audio=(), fps=30.0, tick=24000.0, exists=True):
    return {"exists": exists, "fps": fps, "tick": tick, "lower_frame": lo, "upper_frame": hi, "audio": list(audio)}


def facts(her_facts, narration=None, playback=(0, 6125), target_start=0, land=104, strike=130, extra=(), fps=FPS,
          tick=24000.0, narration_all=None):
    rs = [{"track": "Shots", "cls": "MovieSceneSubTrack", "start": target_start, "end": target_start + 5000,
           "sequence": "/Game/Scenes/LS_Animals_1", "is_target": True}]
    if narration:
        rs.append({"track": "Narration (stand-in)", "cls": "MovieSceneAudioTrack", "start": narration[0],
                   "end": narration[1], "is_narration": True})
    rs += list(extra)
    f = {"scene": "1", "label": "Scene 1 — External Sound", "fps": fps, "tick": tick,
         "playback": list(playback), "target": {"start": target_start, "end": target_start + 5000, "count": 1},
         "narration": {"start": narration[0], "end": narration[1]} if narration else None,
         "root_sections": rs, "land_frame": land, "strike_frame": strike, "her": her_facts}
    if narration_all is not None:
        f["narration_all"] = narration_all
    return f


ROW = {"her_sequence": "/Game/KK_S1_Animals/LS_Animals_1", "current_nested": "/Game/Scenes/LS_Animals_1",
       "start_option": "land_plus_strike", "wide_hold_s": 5.0, "narration_rule": "mute",
       "narration_track": "Narration (stand-in)", "tail_s": 0.0}
CLICK = {"sound": "/Game/KK_S1_Animals/Animals_Project_CLICK", "start_frame": S1_LO, "end_frame": S1_LO + 4477}
VOICES = {"sound": "/Game/KK_S1_Animals/Animal_Voices_1", "start_frame": 0, "end_frame": 5899}


class TimeMaths(unittest.TestCase):
    def test_her_span_negative_start(self):
        s = K.her_span(S1_LO, S1_HI, 30, 24000)
        self.assertEqual((s["ticks_per_frame"], s["lower_tick"]), (800, -248000))
        self.assertAlmostEqual(s["len_s"], 210.6, places=9)
        with self.assertRaises(K.PlanError):
            K.her_span(0, 100, 7, 24000)
        with self.assertRaises(K.PlanError):
            K.her_span(10, 10, 30, 24000)

    def test_outer_frames(self):
        self.assertEqual([K.outer_frames(x, 25)["frames"] for x in (210.6, 164.0, 5.0)], [5265, 4100, 125])
        o = K.outer_frames(210.6, 24)
        self.assertEqual((o["frames"], o["on_grid"]), (5055, False))      # ceiled, never truncated
        self.assertNotEqual(o["frames"], int(210.6 * 24))

    def test_ceil_frames_float_noise(self):
        self.assertEqual(K.ceil_frames(208.64, 25), 5216)
        self.assertEqual(K.ceil_frames(208.6000001, 25), 5216)
        self.assertEqual(K.ceil_frames(208.6, 25), 5215)

    def test_inner_to_scene(self):
        lo = -248000
        self.assertAlmostEqual(K.inner_to_scene_s(lo, 24000, 4.16, lo), 4.16)
        self.assertAlmostEqual(K.inner_to_scene_s(0, 24000, 4.16, lo), 4.16 + 10.333333333, places=6)
        with self.assertRaises(K.PlanError):
            K.inner_to_scene_s(0, 24000, 0, 0, play_rate=0)


class ScenePlans(unittest.TestCase):
    def test_s1_gary_7oct(self):
        """land 104 + strike -> 130, + 5 s wide hold -> cut 255; her 5265 frames; narration MUTED, no tail."""
        f = facts(her(S1_LO, S1_HI, [CLICK]), narration=(5216, 6091), narration_all=[{"start": 5216, "end": 6091}])
        p = K.plan_scene(f, ROW)
        self.assertEqual(p["refusals"], [])
        self.assertEqual(p["section"], [255, 255 + 5265])
        self.assertEqual(p["narration"]["action"], "mute")
        self.assertEqual(p["narration"]["sections"], [[5216, 6091]])
        self.assertEqual(p["planned_end"], 5520)                      # her shot + landing offset, no narration tail
        tl = p["timeline"]
        self.assertEqual((tl["level_visible"], tl["wide"], tl["ours_off"], tl["hers_dark"]),
                         ([104, 5520], [104, 255], [255, 5520], [104, 255]))
        # control: the same Scene under the after_voices rule with no voices refuses (narration past her end)
        q = K.plan_scene(f, dict(ROW, narration_rule="after_voices", start_option="keep", wide_hold_s=0))
        self.assertTrue(any(r.startswith("NARRATION_PAST_HER_END") for r in q["refusals"]))

    def test_wide_hold_moves_the_cut(self):
        a = K.plan_scene(facts(her(S1_LO, S1_HI)), dict(ROW, wide_hold_s=0.0))
        b = K.plan_scene(facts(her(S1_LO, S1_HI)), ROW)
        self.assertEqual(a["section"][0], 130)
        self.assertEqual(b["section"][0] - a["section"][0], 125)

    def test_no_strike_refuses_land_plus_strike(self):
        p = K.plan_scene(facts(her(S1_LO, S1_HI), strike=None), ROW)
        self.assertTrue(any(r.startswith("START_UNKNOWN") for r in p["refusals"]))
        ok = K.plan_scene(facts(her(S1_LO, S1_HI), strike=None), dict(ROW, start_option="land"))   # control
        self.assertEqual(ok["section"][0], 104 + 125)

    def test_timeline_requires_land_when_placed(self):
        p = K.plan_scene(facts(her(S1_LO, S1_HI), land=None), dict(ROW, start_option="at_s", at_s=10.0))
        self.assertIn("TIMELINE_NO_LAND", p["refusals"])
        q = K.plan_scene(facts(her(S1_LO, S1_HI), land=None),
                         dict(ROW, start_option="at_s", at_s=10.0, placed_in_hangar=False))
        self.assertNotIn("TIMELINE_NO_LAND", q["refusals"])
        self.assertEqual(K.plan_timeline(100, 50, 200)["refusals"][0][:14], "TIMELINE_ORDER")
        self.assertEqual(K.plan_timeline(100, 100, 200)["hers_dark"], None)   # no wide window, nothing to darken

    def test_after_voices_still_works(self):
        row = dict(ROW, narration_rule="after_voices", start_option="keep", wide_hold_s=0)
        p = K.plan_scene(facts(her(S1_LO, S1_HI, [CLICK, VOICES]), narration=(5216, 6091), target_start=104), row)
        v_end = 104 / 25.0 + (5899 * 800 + 248000) / 24000.0
        n0 = K.ceil_frames(v_end, 25)
        self.assertEqual(p["narration"]["frames"], [n0, n0 + 875])
        self.assertEqual(p["planned_end"], max(104 + 5265, n0 + 875))

    def test_inside_shot_rule(self):
        row = dict(ROW, narration_rule="inside_shot", start_option="keep", wide_hold_s=0)
        p = K.plan_scene(facts(her(0, 150), narration=(104, 1973), target_start=0, land=0), row)
        self.assertTrue(any(r.startswith("NARRATION_NOT_INSIDE_SHOT") for r in p["refusals"]))
        ok = K.plan_scene(facts(her(0, 150), narration=(10, 100), target_start=0, land=0), row)
        self.assertFalse(any(r.startswith("NARRATION_NOT_INSIDE_SHOT") for r in ok["refusals"]))

    def test_section_past_end(self):
        rise = {"track": "Hangar Rise", "cls": "MovieSceneSubTrack", "start": -500, "end": 9999}
        row = dict(ROW, narration_rule="none")
        p = K.plan_scene(facts(her(S1_LO, S1_HI), extra=[rise]), row)
        self.assertTrue(any(r.startswith("SECTION_PAST_PLANNED_END") for r in p["refusals"]))
        p2 = K.plan_scene(facts(her(S1_LO, S1_HI), extra=[rise]), dict(row, allow_truncate=["Hangar Rise"]))
        self.assertFalse(any(r.startswith("SECTION_PAST_PLANNED_END") for r in p2["refusals"]))

    def test_24fps_and_tick_mismatch(self):
        row = dict(ROW, narration_rule="none")
        p24 = K.plan_scene(facts(her(S1_LO, S1_HI), fps=24.0), row)
        self.assertEqual(p24["length"]["frames"], 5055)
        self.assertTrue(any(w.startswith("LENGTH_OFF_GRID") for w in p24["warnings"]))
        self.assertFalse(any(w.startswith("LENGTH_OFF_GRID") for w in K.plan_scene(facts(her(S1_LO, S1_HI)), row)["warnings"]))
        pt = K.plan_scene(facts(her(S1_LO, S1_HI), tick=60000.0), row)
        self.assertEqual(pt["length"]["frames"], 5265)
        self.assertTrue(any(w.startswith("TICK_RESOLUTIONS_DIFFER") for w in pt["warnings"]))

    def test_her_audio_lands_where_she_set_it(self):
        p = K.plan_scene(facts(her(S1_LO, S1_HI, [CLICK])), dict(ROW, narration_rule="none"))
        a = p["her_audio_in_scene"][0]
        self.assertAlmostEqual(a["scene_start_s"], 255 / 25.0)
        self.assertAlmostEqual(a["scene_end_s"], 255 / 25.0 + 4477 / 30.0)


class Placement(unittest.TestCase):
    def test_s1_fits_translation_only(self):
        lv = "/Game/KK_S1_Animals/L_Animals"
        p = K.plan_placement(lv, ARGS["levels"][lv], HANGARS, 100.0)
        self.assertEqual(p["refusals"], [])
        t = p["fit"]["level_transform"]
        self.assertEqual(t["yaw"], 0.0)
        self.assertAlmostEqual(t["loc"][0], 28784.0135 + 3500 + 272, places=4)
        self.assertAlmostEqual(t["loc"][1], 122.0, places=6)
        self.assertAlmostEqual(t["loc"][2], 150.0, places=6)

    def test_s4_fits(self):
        lv = "/Game/L_KK_children"
        p = K.plan_placement(lv, ARGS["levels"][lv], HANGARS, 100.0)
        self.assertEqual(p["refusals"], [])
        self.assertTrue(p["fit"]["fits"])
        self.assertEqual(p["fit"]["local_yaw"], 0.0)

    def test_s2_does_not_fit_and_is_only_a_warning_because_import_only(self):
        lv = "/Game/Japanese_Alley/Maps/Japanese_Alley"
        row = dict(ARGS["levels"][lv], import_only=True)
        p = K.plan_placement(lv, row, HANGARS, 100.0)
        self.assertFalse(p["fit"]["fits"])
        self.assertAlmostEqual(p["fit"]["overhang_cm"]["side"], 1278.0 - 900.0, places=6)
        self.assertEqual(p["refusals"], [])
        self.assertTrue(any(w.startswith("NO_FIT") for w in p["warnings"]))
        self.assertTrue(any(w.startswith("TALLER_THAN_LATTICE") for w in p["warnings"]))   # 1220 cm > 1200
        hooked = K.plan_placement(lv, dict(row, import_only=False), HANGARS, 100.0)          # control
        self.assertTrue(any(r.startswith("NO_FIT") for r in hooked["refusals"]))
        self.assertTrue(any(r.startswith("WORLD_YAW_NONZERO") for r in hooked["refusals"]))

    def test_rotation_chosen_only_when_needed_and_flagged(self):
        h = HANGARS["1"]
        f0 = K.fit_footprint([0, 1000, 0, 1000], 0, h, h["dock"])
        self.assertEqual(f0["local_yaw"], 0.0)
        f90 = K.fit_footprint([0, 1500, 0, 2500], 0, h, h["dock"], yaw_options=(0, 90))
        self.assertEqual((f90["fits"], f90["local_yaw"]), (True, 90.0))
        p = K.plan_placement("X", {"scene": "1", "footprint_her": [0, 1500, 0, 2500], "local_yaw_options": [0, 90]},
                             HANGARS, 100.0)
        self.assertTrue(any(r.startswith("WORLD_YAW_NONZERO") for r in p["refusals"]))

    def test_transformed_set_lands_inside_the_rotated_s2_box(self):
        """The fitted transform puts her footprint centre on the hangar centreline, on the floor, even for S2's
        -43.57 deg dock; a corner pushed past the wall is outside (control)."""
        lv = "/Game/Japanese_Alley/Maps/Japanese_Alley"
        h = HANGARS["2"]
        fit = K.fit_footprint([-2579, 811, -1147, 1409], 790.0, h, h["dock"], yaw_options=(0,))
        c = K.world_point(fit["level_transform"], [(-2579 + 811) / 2.0, (-1147 + 1409) / 2.0, 790.0])
        self.assertTrue(K.inside_box_local(c, h["dock"], h))
        self.assertAlmostEqual(c[2], h["dock"]["loc"][2], places=6)          # her ground on our floor top
        out = K.world_point(fit["level_transform"], [(-2579 + 811) / 2.0, 1409 + 500.0, 790.0])
        self.assertFalse(K.inside_box_local(out, h["dock"], h))
        self.assertIsNotNone(lv)

    def test_anchor_far_and_near(self):
        h = HANGARS["1"]
        far = K.fit_footprint([0, 1000, 0, 1000], 0, h, h["dock"], anchor="far")
        near = K.fit_footprint([0, 1000, 0, 1000], 0, h, h["dock"], anchor="near")
        self.assertGreater(far["local_offset"][0], near["local_offset"][0])
        with self.assertRaises(K.PlanError):
            K.fit_footprint([0, 1, 0, 1], 0, h, h["dock"], anchor="middle")


class Rekey(unittest.TestCase):
    CH = {"x": {"keys": [[0, 10.0], [48000, 20.0]], "default": 5.0},
          "y": {"keys": [[0, -1.0]], "default": None}, "z": {"keys": [], "default": 0.0}}

    def test_translation(self):
        out = K.rekey_plan(self.CH, {"loc": [100.0, 200.0, 300.0], "yaw": 0.0})
        self.assertEqual(out["x"]["keys"], [[0, 110.0], [48000, 120.0]])
        self.assertEqual((out["x"]["default"], out["y"]["default"], out["z"]["default"]), (105.0, None, 300.0))
        self.assertEqual([k[0] for k in out["x"]["keys"]], [k[0] for k in self.CH["x"]["keys"]])   # times untouched
        self.assertEqual(out["y"]["keys"], [[0, 199.0]])

    def test_rotation_refused(self):
        with self.assertRaises(K.PlanError):
            K.rekey_plan(self.CH, {"loc": [0, 0, 0], "yaw": -43.57})
        K.rekey_plan(self.CH, {"loc": [0, 0, 0], "yaw": 360.0})   # control: a full turn is yaw 0

    def test_rekey_matches_level_transform(self):
        """A keyed camera at her point p ends where the LevelTransform puts a static actor at p (translation-only)."""
        t = {"loc": [32556.0135, 122.0, 150.0], "yaw": 0.0}
        p = [300.0, -50.0, 170.0]
        keyed = K.rekey_plan({"x": {"keys": [[0, p[0]]]}, "y": {"keys": [[0, p[1]]]}, "z": {"keys": [[0, p[2]]]}}, t)
        self.assertEqual([keyed[a]["keys"][0][1] for a in "xyz"], K.world_point(t, p))


class ArgsAndGates(unittest.TestCase):
    def test_shipped_args(self):
        self.assertEqual(K.validate_args(ARGS), [])
        self.assertEqual(ARGS["mode"], "DRY")
        self.assertNotIn("2", ARGS["scenes"])                      # S2 is import-only
        self.assertIn("2", ARGS["import_only"])
        self.assertTrue(ARGS["decided_by"].startswith("Gary 7 Oct"))
        for k in ("1", "4"):
            self.assertEqual(ARGS["scenes"][k]["start_option"], "land_plus_strike")
        self.assertEqual(ARGS["scenes"]["1"]["narration_rule"], "mute")

    def test_bad_args(self):
        bad = copy.deepcopy(ARGS)
        bad["mode"] = "APPLY"
        bad["scenes"]["1"]["start_option"] = "soon"
        bad["scenes"]["2"] = dict(bad["scenes"]["1"])               # hooked AND import-only
        bad["scenes"]["4"]["level_packages"] = ["/Game/Nope"]
        bad["levels"]["/Game/L_KK_children"]["footprint_her"] = [5, 1, 0, 1]
        v = K.validate_args(bad)
        for want in ("MODE_INVALID", "START_OPTION_INVALID", "BOTH_HOOKED_AND_IMPORT_ONLY", "LEVEL_NOT_IN_LEVELS",
                     "FOOTPRINT_INVALID"):
            self.assertTrue(any(want in x for x in v), want)

    def test_live_gates(self):
        clean = {"content": [], "maps": []}
        self.assertEqual(K.live_gates({"mode": "DRY", "census": clean}), [])
        self.assertEqual(K.live_gates({"mode": "APPLY_SEQ", "confirm": "APPLY_SEQ KLARAHOOK", "census": clean,
                                       "decided_by": "Gary"}), [])
        g = K.live_gates({"mode": "APPLY_STREAM", "confirm": "APPLY_STREAM KLARAHOOK", "decided_by": "",
                          "census": {"content": ["/Game/X"], "maps": []}, "pie": True, "sequencer_open": "/Game/M"})
        self.assertEqual(len(g), 4)
        self.assertEqual(K.live_gates({"mode": "REVERT_SEQ", "confirm": "REVERT_SEQ KLARAHOOK", "census": clean}),
                         ["NO_APPLIED_RECORD"])

    def test_census_gate_and_drift(self):
        self.assertEqual(K.census_gate({"content": ["/Game/A"], "maps": []}, ["/Game/A"], []), [])
        self.assertEqual(len(K.census_gate({"content": ["/Game/A", "/Game/B"], "maps": ["/Game/W"]}, ["/Game/A"], [])), 2)
        after = {"target": {"sequence": "/Game/C", "start": 255, "end": 5520, "start_offset_tick": 0},
                 "narration": [[5216, 6091, False]], "vis_track": [{"levels": ["L_Animals"], "range": [104, 5520]}],
                 "hookin_bindings": [{"name": K.OURS_OFF_PREFIX + "Sun", "sections": [[255, 5520]]}]}
        self.assertEqual(K.seq_drift(copy.deepcopy(after), {"after": after}), [])
        moved = copy.deepcopy(after)
        moved["narration"][0][2] = True
        moved["hookin_bindings"] = None
        self.assertEqual(len(K.seq_drift(moved, {"after": after})), 2)

    def test_copy_path_never_her_original(self):
        p = K.copy_path(ARGS, "1", "/Game/KK_S1_Animals/LS_Animals_1")
        self.assertEqual(p, "/Game/InfinityStage/KlaraHookin/LS_Animals_1_S1Hangar")
        self.assertNotEqual(p, "/Game/KK_S1_Animals/LS_Animals_1")

    def test_import_runs_nothing(self):
        self.assertIsNone(K.unreal)
        self.assertTrue(math.isfinite(K.norm_yaw(-43.57)))


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=1).result
    print("KLARAHOOK_HARNESS|run=%d|failures=%d|errors=%d" % (result.testsRun, len(result.failures), len(result.errors)))
    sys.exit(0 if result.wasSuccessful() else 1)
