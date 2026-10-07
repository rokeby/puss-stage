"""Offline harness for klara_hookin_s6.py pure planning (no Unreal). Every positive case has a negative control that
must FAIL the same check, so a planner that always says yes (or always no) cannot pass.
Run: python Saved/CodexConductor/KlaraIngest/test_klara_hookin_s6_offline.py
Numbers [meas]: LS_Void bytes (Content/Void_content/LS_Void.uasset, copied 7 Oct): tick 24000, 30 fps, playback
[0, 5585600) ticks, cut-shaped ranges 9600..5168800, audio-shaped [0, 4512000); S6 score/markers
scene_audio_import_S6_record.json (land 104, playback [0, 4850), score section [104, 4804)).
"""
import copy
import json
import math
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import klara_hookin_s6 as K  # noqa: E402  (importing without unreal must run nothing)

with open(os.path.join(HERE, "klara_hookin_s6_args.json"), encoding="utf-8") as _h:
    ARGS = json.load(_h)
ROW = ARGS["scene"]
FPS = 25.0
SCORE = "/Game/InfinityStage/Audio/ScenesAudio/Score/SW_S6_The_Void_Live"
CUTS = [[9600, 420800], [420800, 434400], [434400, 856000], [856000, 1416800], [1416800, 1776000],
        [1776000, 2308800], [2308800, 2632800], [2632800, 3308000], [3308000, 3808000], [3808000, 5168800]]
MARKERS = [{"label": "S6 score in (land)", "scene_s": 4.16}, {"label": "S6 swell 0:50", "scene_s": 54.96},
           {"label": "S6 trough 2:00", "scene_s": 120.12}, {"label": "S6 climax 2:35", "scene_s": 160.0},
           {"label": "S6 drop 2:54", "scene_s": 177.92}]


def facts(sound=SCORE, cuts=CUTS, owner="TIMELINE", extra=()):
    rs = [{"track": "Shots", "cls": "MovieSceneCinematicShotTrack", "start": 0, "end": 375,
           "sequence": "/Game/Scenes/LS_Void", "is_target": True},
          {"track": "Hangar Fold", "cls": "MovieSceneSubTrack", "start": 0, "end": 775},
          {"track": "Camera Cuts", "cls": "MovieSceneCameraCutTrack", "start": 0, "end": 4825},
          {"track": "Camera Cuts", "cls": "MovieSceneCameraCutTrack", "start": 4825, "end": 4850},
          {"track": "Scene Score", "cls": "MovieSceneAudioTrack", "start": 104, "end": 4804, "sound": sound}]
    return {"label": "Scene 6 — External Sound", "fps": FPS, "tick": 24000.0, "playback": [0, 4850],
            "root_sections": rs + list(extra), "target": {"start": 0, "end": 375, "count": 1}, "land_frame": 104,
            "markers": MARKERS, "camera_owner": owner,
            "her": {"exists": True, "fps": 30.0, "tick": 24000.0, "lower_tick": 0, "upper_tick": 5585600,
                    "cuts_tick": list(cuts), "audio": [{"sound": "/Game/Void_content/The_Void_Live_Stereo_1_",
                                                        "start_tick": 0, "end_tick": 4512000}]}}


def plan(row_over=None, **kw):
    row = dict(ROW, **(row_over or {}))
    return K.plan_s6(facts(**kw), row, ARGS["lighting"], ARGS["hangar_rule"])


class Lengths(unittest.TestCase):
    def test_her_length_rules(self):
        self.assertAlmostEqual(K.her_length(0, 5585600, 24000), 232.733333333, places=6)
        self.assertAlmostEqual(K.her_length(0, 5585600, 24000, 5168800, "her_last_cut"), 215.366666666, places=6)
        with self.assertRaises(K.PlanError):
            K.her_length(0, 5585600, 24000, None, "her_last_cut")
        with self.assertRaises(K.PlanError):
            K.her_length(0, 5585600, 24000, rule="soon")

    def test_outer_frames_ceils(self):
        o = K.outer_frames(232.7333333333, FPS)
        self.assertEqual((o["frames"], o["on_grid"]), (5819, False))
        self.assertNotEqual(o["frames"], int(232.7333333333 * FPS))        # never truncates her last frame


class ScenePlan(unittest.TestCase):
    def test_shipped_plan(self):
        p = plan()
        self.assertEqual(p["refusals"], [])
        self.assertEqual(p["section"], [0, 5819])
        self.assertAlmostEqual(p["planned_end_s"], 232.76, places=6)
        self.assertEqual(p["extend_mode"], {"scene_label": "Scene 6 — External Sound", "new_end_s": 232.76,
                                            "dry_run": True})
        self.assertEqual(p["mute"], [["Scene Score", 104, 4804, SCORE]])
        self.assertEqual(p["timeline"]["level_visible"], [0, 5819])
        self.assertEqual(p["timeline"]["ours_off"], [0, 5819])
        self.assertEqual(p["timeline"]["hangar_off"], [0, 5819])
        self.assertAlmostEqual(p["her_cut_span_scene_s"][0], 0.4, places=9)
        self.assertTrue(any("HER_TAIL_WITHOUT_CUTS" in w for w in p["warnings"]))

    def test_markers_off_at_scene_start_on_at_land(self):
        off = plan()["markers"]
        self.assertEqual([m["lines_up"] for m in off], [False] * 5)
        self.assertTrue(all(abs(m["delta_frames"] - 104.0) <= 0.5 for m in off))      # all ~4.16 s late (markers frame-snapped)
        on = plan({"start_option": "land"})["markers"]                                  # control: start at land 104
        self.assertEqual([m["lines_up"] for m in on], [True] * 5)

    def test_nothing_to_mute_refuses(self):
        p = plan(sound="/Game/Other")
        self.assertTrue(any("NOTHING_TO_MUTE" in r for r in p["refusals"]))
        self.assertFalse(any("NOTHING_TO_MUTE" in r for r in plan()["refusals"]))

    def test_last_cut_rule_and_no_cuts(self):
        p = plan({"end_rule": "her_last_cut"})
        self.assertEqual(p["section"], [0, K.ceil_frames(215.3666666667, FPS)])
        self.assertFalse(any("HER_TAIL_WITHOUT_CUTS" in w for w in p["warnings"]))
        self.assertTrue(any("HER_NO_CAMERA_CUTS" in r for r in plan({"end_rule": "her_playback"}, cuts=[])["refusals"]))

    def test_section_past_end_and_owner(self):
        late = {"track": "Late", "cls": "MovieSceneFloatTrack", "start": 0, "end": 9000}
        self.assertTrue(any("SECTION_PAST_PLANNED_END" in r for r in plan(extra=[late])["refusals"]))
        self.assertTrue(any("SECTION_PAST_PLANNED_END" in w for w in plan({"allow_past_end": ["Late"]}, extra=[late])["warnings"]))
        self.assertTrue(any("CAMERA_OWNER_DOG_FREE_LOOK" in w for w in plan(owner="DOG_FREE_LOOK")["warnings"]))
        self.assertFalse(any("CAMERA_OWNER" in w for w in plan()["warnings"]))


HER = {"loc": [120.0, -340.0, 165.0], "rot": [0.0, -4.0, 37.0], "hfov": 54.4}
ENTRY = {"loc": [27640.2835, 400000.0, 180.0], "rot": [0.0, 0.0, 0.0], "hfov": 54.4}


class Placement(unittest.TestCase):
    def test_match_entry_yaw_is_seamless(self):
        s = K.solve_arrival(HER, ENTRY, "match_entry_yaw")
        self.assertTrue(s["seamless_pos_yaw"])
        self.assertLess(s["residual"]["pos_cm"], 1e-6)
        self.assertAlmostEqual(s["residual"]["yaw_deg"], 0.0, places=9)
        self.assertAlmostEqual(s["transform"]["yaw"], -37.0, places=9)
        self.assertAlmostEqual(s["residual"]["pitch_deg"], 4.0, places=9)               # reported, never fixed

    def test_translation_and_identity_controls(self):
        t = K.solve_arrival(HER, ENTRY, "match_entry_translation")
        self.assertLess(t["residual"]["pos_cm"], 1e-6)
        self.assertAlmostEqual(t["residual"]["yaw_deg"], -37.0, places=9)
        self.assertFalse(t["seamless_pos_yaw"])
        self.assertFalse(K.solve_arrival(HER, ENTRY, "identity")["seamless_pos_yaw"])
        with self.assertRaises(K.PlanError):
            K.solve_arrival(HER, ENTRY, "tilt")

    def test_lead(self):
        s = K.solve_arrival(HER, ENTRY, "match_entry_yaw", lead_cm=200.0)
        self.assertAlmostEqual(s["her_cam_world"][0], ENTRY["loc"][0] + 200.0, places=6)
        self.assertTrue(s["seamless_pos_yaw"])


def key(t, v, a=0.0, l=0.0, interp="RCIM_CUBIC", tmode="RCTM_SMART_AUTO", w="RCTWM_WEIGHTED_NONE"):
    return {"t": t, "v": v, "arrive": a, "leave": l, "interp": interp, "tmode": tmode, "wmode": w}


CH = {"x": {"keys": [key(0, 100.0, 0.0, 2.0), key(30, 160.0, 1.0, 1.0), key(60, 150.0, -0.5, -0.5)], "default": 100.0,
            "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"},
      "y": {"keys": [key(0, -50.0, 0.0, 0.5), key(30, -20.0, 1.5, 1.5), key(60, 40.0, 3.0, 3.0)], "default": -50.0,
            "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"},
      "z": {"keys": [key(0, 170.0), key(60, 175.0)], "default": 170.0, "pre": "RCCE_CONSTANT", "post": "RCCE_CONSTANT"},
      "yaw": {"keys": [key(0, 10.0), key(60, 40.0)], "default": 10.0}}


class Rekey(unittest.TestCase):
    def test_translation_matches_level_transform(self):
        t = {"loc": [27000.0, 400100.0, 15.0], "yaw": 0.0}
        r = K.rekey_rigid(CH, t)
        self.assertEqual(r["problems"], [])
        self.assertEqual([r[a]["keys"][-1]["v"] for a in "xyz"], K.rigid_point(t, [CH[a]["keys"][-1]["v"] for a in "xyz"]))
        self.assertEqual(r["x"]["keys"][1]["tmode"], "RCTM_SMART_AUTO")                # untouched by a translation
        self.assertEqual(r["yaw"]["keys"][0]["v"], 10.0)

    def test_yaw_rotates_the_curve_exactly(self):
        t = {"loc": [500.0, -200.0, 0.0], "yaw": -37.0}
        r = K.rekey_rigid(CH, t)
        self.assertEqual(r["problems"], [])
        for seg in (0, 1):
            for f in (3, 11, 17, 29):
                fr = 30 * seg + f
                ox = K.eval_hermite(CH["x"]["keys"][seg], CH["x"]["keys"][seg + 1], fr)
                oy = K.eval_hermite(CH["y"]["keys"][seg], CH["y"]["keys"][seg + 1], fr)
                want = K.rigid_point(t, [ox, oy, 0.0])
                got = [K.eval_hermite(r[a]["keys"][seg], r[a]["keys"][seg + 1], fr) for a in "xy"]
                self.assertAlmostEqual(got[0], want[0], places=6)
                self.assertAlmostEqual(got[1], want[1], places=6)
        self.assertTrue(all(k["tmode"] == K.USER for k in r["x"]["keys"] + r["y"]["keys"]))
        self.assertAlmostEqual(r["yaw"]["keys"][1]["v"], 3.0, places=9)                  # 40 + (-37)
        # control: rotating values but NOT tangents is not the rotated curve
        bad = copy.deepcopy(r)
        for a, src in (("x", CH["x"]), ("y", CH["y"])):
            for k, o in zip(bad[a]["keys"], src["keys"]):
                k["arrive"], k["leave"] = o["arrive"], o["leave"]
        ox = K.eval_hermite(CH["x"]["keys"][0], CH["x"]["keys"][1], 11)
        oy = K.eval_hermite(CH["y"]["keys"][0], CH["y"]["keys"][1], 11)
        self.assertGreater(abs(K.eval_hermite(bad["x"]["keys"][0], bad["x"]["keys"][1], 11)
                               - K.rigid_point(t, [ox, oy, 0])[0]), 1e-3)

    def test_yaw_refusals(self):
        t = {"loc": [0.0, 0.0, 0.0], "yaw": 15.0}
        times = copy.deepcopy(CH)
        times["y"]["keys"][1]["t"] = 31
        self.assertTrue(any("XY_KEY_TIMES_DIFFER" in p for p in K.rekey_rigid(times, t)["problems"]))
        weighted = copy.deepcopy(CH)
        weighted["x"]["keys"][0]["wmode"] = "RCTWM_WEIGHTED_BOTH"
        self.assertTrue(any("WEIGHTED" in p for p in K.rekey_rigid(weighted, t)["problems"]))
        ext = copy.deepcopy(CH)
        ext["x"]["post"] = "RCCE_LINEAR"
        self.assertTrue(any("EXTRAPOLATION" in p for p in K.rekey_rigid(ext, t)["problems"]))
        self.assertEqual(K.rekey_rigid(times, {"loc": [1.0, 2.0, 3.0], "yaw": 0.0})["problems"], [])  # translation ok


class LoadExemptArgs(unittest.TestCase):
    def test_plan_load(self):
        now = {"/Game/A": {"streamed": True, "initially_loaded": True, "initially_visible": False},
               "/Game/B": {"streamed": True, "initially_loaded": False, "initially_visible": False},
               "/Game/C": {"streamed": False}}
        lp = K.plan_load(now, ["/Game/A", "/Game/B", "/Game/C"])
        self.assertEqual([c["level"] for c in lp["changes"]], ["/Game/A"])
        self.assertEqual(lp["changes"][0]["after"], {"initially_loaded": False, "initially_visible": False})
        self.assertEqual(lp["refusals"], ["NOT_STREAMED: /Game/C"])

    def test_exempt_after(self):
        before = ["/Game/KK_S1_Animals/L_Animals.L_Animals", "/Game/L_KK_children.L_KK_children"]
        self.assertEqual(K.exempt_after(before, "/Game/L_KK_Void"), before + ["/Game/L_KK_Void"])
        self.assertEqual(K.exempt_after(before + ["/Game/L_KK_Void.L_KK_Void"], "/Game/L_KK_Void"),
                         before + ["/Game/L_KK_Void.L_KK_Void"])

    def test_shipped_args(self):
        self.assertEqual(K.validate_args(ARGS), [])
        self.assertEqual(ARGS["mode"], "DRY")
        self.assertEqual(ROW["copy_path"], "/Game/InfinityStage/KlaraHookin/LS_Void_S6")
        self.assertNotIn("/Game/L_KK_Void", ARGS["on_demand"]["levels"])
        self.assertIn("/Game/Japanese_Alley/Maps/Japanese_Alley", ARGS["on_demand"]["levels"])
        rec = os.path.join(os.path.dirname(HERE), "scene_audio_import_S6_record.json")
        if os.path.exists(rec):
            with open(rec, encoding="utf-8") as h:
                r = json.load(h)
            self.assertEqual(ROW["mute_sounds"], [r["sound"]])
            self.assertEqual(ROW["marker_track_s"], {m["label"]: m["track_s"] for m in r["plan"]["markers"]})

    def test_bad_args(self):
        bad = copy.deepcopy(ARGS)
        bad["mode"] = "APPLY"
        bad["scene"]["copy_path"] = bad["scene"]["her_sequence"]
        bad["scene"]["placement"] = "tilt"
        bad["hangar_rule"] = "maybe"
        bad["on_demand"]["levels"] = "all"
        v = K.validate_args(bad)
        for want in ("MODE_INVALID", "COPY_PATH_IS_AN_ORIGINAL", "PLACEMENT_INVALID", "HANGAR_RULE_INVALID",
                     "ON_DEMAND_LEVELS_NOT_A_LIST"):
            self.assertTrue(any(want in x for x in v), want)

    def test_live_gates(self):
        clean = {"content": [], "maps": []}
        self.assertEqual(K.live_gates({"mode": "DRY", "census": clean}), [])
        ok = {"mode": "APPLY_SEQ", "confirm": "APPLY_SEQ KLARAVOID", "census": clean, "decided_by": "Gary",
              "stream_applied": True}
        self.assertEqual(K.live_gates(ok), [])
        self.assertEqual(K.live_gates(dict(ok, stream_applied=False)), ["STREAM_NOT_APPLIED (APPLY_STREAM first)"])
        self.assertIn("SEQ_STILL_APPLIED (REVERT_SEQ first)",
                      K.live_gates({"mode": "REVERT_STREAM", "confirm": "REVERT_STREAM KLARAVOID", "census": clean,
                                    "record_applied": True, "seq_applied": True}))
        self.assertEqual(len(K.live_gates({"mode": "APPLY_STREAM", "confirm": "APPLY_STREAM KLARAHOOK",
                                           "census": {"content": ["/Game/X"], "maps": []}, "pie": True})), 4)

    def test_record_names_never_the_s1s4_ones(self):
        for m in K.MODES:
            self.assertTrue(K.record_path(m).startswith("klara_hookin_s6_"))

    def test_import_runs_nothing(self):
        self.assertIsNone(K.unreal)


class MeasuredBytes(unittest.TestCase):
    """Pins the offline byte facts the plan uses; skipped if the Content copy is absent."""
    PATH = os.path.join(HERE, "..", "..", "..", "Content", "Void_content", "LS_Void.uasset")

    def test_ls_void_ranges(self):
        if not os.path.exists(self.PATH):
            self.skipTest("Content copy absent")
        with open(self.PATH, "rb") as h:
            b = h.read()
        pat = bytes.fromhex("f801000000000000010000008b01000000000000")
        ranges, i = [], 0
        while True:
            i = b.find(pat, i)
            if i < 0:
                break
            j = i + len(pat)
            if struct.unpack_from("<i", b, j + 16)[0] == 10:
                d = b[j + 21:j + 31]
                if d[0] != 2:
                    ranges.append([struct.unpack_from("<i", d, 1)[0], struct.unpack_from("<i", d, 6)[0]])
            i += 1
        self.assertEqual(ranges[0], [0, 5585600])                                   # PlaybackRange
        self.assertTrue(all(c in ranges for c in CUTS))
        self.assertIn([0, 4512000], ranges)
        self.assertNotIn([0, 4512001], ranges)                                       # control


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=1).result
    print("KLARAVOID_HARNESS|run=%d|failures=%d|errors=%d|skipped=%d" % (result.testsRun, len(result.failures),
                                                                      len(result.errors), len(result.skipped)))
    sys.exit(0 if result.wasSuccessful() else 1)
