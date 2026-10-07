"""Offline harness for klara_hookin.py pure planning (no Unreal). Every positive case has a negative control that
must FAIL the same check, so a planner that always says yes (or always no) cannot pass.
Run: python Saved/CodexConductor/KlaraIngest/test_klara_hookin_offline.py
Numbers: her ranges are [meas] census_report.md (S1 -10.333..200.267 s, S2 0..5 s, S4 0..164 s, 30 fps, tick 24000);
S1 narration 5216..6091 @25 and S2 104..1973 @25 are [meas] s1_narration_after_voices_record.json and
scene_narration_standin_record.json.
"""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import klara_hookin as K  # noqa: E402  (importing without unreal must run nothing)

S1_LO, S1_HI = -310, 6008        # -10.3333 s, 200.2667 s at 30 fps
FPS = 25.0


def her(lo, hi, audio=(), fps=30.0, tick=24000.0, exists=True):
    return {"exists": exists, "fps": fps, "tick": tick, "lower_frame": lo, "upper_frame": hi, "audio": list(audio)}


def facts(her_facts, narration=None, playback=(0, 6125), target_start=0, land=104, strike=None, extra=(), fps=FPS,
          tick=24000.0):
    rs = [{"track": "Shots", "cls": "MovieSceneSubTrack", "start": target_start, "end": target_start + 5000,
           "sequence": "/Game/Scenes/LS_Animals_1", "is_target": True}]
    if narration:
        rs.append({"track": "Narration (stand-in)", "cls": "MovieSceneAudioTrack", "start": narration[0],
                   "end": narration[1], "is_narration": True})
    rs += list(extra)
    return {"scene": "1", "label": "Scene 1 — External Sound", "fps": fps, "tick": tick,
            "playback": list(playback), "target": {"start": target_start, "end": target_start + 5000, "count": 1},
            "narration": {"start": narration[0], "end": narration[1]} if narration else None,
            "root_sections": rs, "land_frame": land, "strike_frame": strike, "her": her_facts}


ROW1 = {"her_sequence": "/Game/KK_S1_Animals/LS_Animals_1", "current_nested": "/Game/Scenes/LS_Animals_1",
        "start_option": "keep", "narration_rule": "after_voices", "narration_track": "Narration (stand-in)",
        "voices_pattern": "Animal_Voices", "tail_s": 0.0}
CLICK = {"sound": "/Game/KK_S1_Animals/Animals_Project_CLICK", "start_frame": S1_LO, "end_frame": S1_LO + 4477}
VOICES = {"sound": "/Game/KK_S1_Animals/Animal_Voices_1", "start_frame": 0, "end_frame": 5899}  # ends 196.633 s inner


class TimeMaths(unittest.TestCase):
    def test_her_span_s1_negative_start(self):
        s = K.her_span(S1_LO, S1_HI, 30, 24000)
        self.assertEqual(s["ticks_per_frame"], 800)
        self.assertAlmostEqual(s["len_s"], 210.6, places=9)
        self.assertAlmostEqual(s["lower_s"], -10.333333333, places=6)
        self.assertEqual(s["lower_tick"], -248000)

    def test_her_span_negative_controls(self):
        with self.assertRaises(K.PlanError):
            K.her_span(0, 100, 7, 24000)            # 24000/7 ticks per frame: not whole
        with self.assertRaises(K.PlanError):
            K.her_span(10, 10, 30, 24000)           # empty

    def test_outer_frames_on_grid(self):
        self.assertEqual(K.outer_frames(210.6, 25)["frames"], 5265)
        self.assertTrue(K.outer_frames(210.6, 25)["on_grid"])
        self.assertEqual(K.outer_frames(164.0, 25)["frames"], 4100)
        self.assertEqual(K.outer_frames(5.0, 25)["frames"], 125)
        self.assertEqual(K.outer_frames(210.6, 30)["frames"], 6318)

    def test_outer_frames_off_grid_control(self):
        o = K.outer_frames(210.6, 24)               # 5054.4 frames
        self.assertFalse(o["on_grid"])
        self.assertEqual(o["frames"], 5055)         # ceiled, never truncated
        self.assertAlmostEqual(o["hold_s"], 0.6 / 24, places=9)
        self.assertNotEqual(o["frames"], int(210.6 * 24))   # control: truncation would cut her last frame

    def test_ceil_frames_float_noise(self):
        self.assertEqual(K.ceil_frames(208.64, 25), 5216)          # not 5217
        self.assertEqual(K.ceil_frames(208.62666666666667, 25), 5216)
        self.assertEqual(K.ceil_frames(208.6000001, 25), 5216)     # control: a hair past 5215 rounds UP
        self.assertEqual(K.ceil_frames(208.6, 25), 5215)

    def test_inner_to_scene_negative_start(self):
        lo = -248000
        self.assertAlmostEqual(K.inner_to_scene_s(lo, 24000, 4.16, lo), 4.16)            # her start = section start
        self.assertAlmostEqual(K.inner_to_scene_s(0, 24000, 4.16, lo), 4.16 + 10.333333333, places=6)
        self.assertNotAlmostEqual(K.inner_to_scene_s(0, 24000, 4.16, lo), 4.16, places=3)  # control: 0 is NOT start
        with self.assertRaises(K.PlanError):
            K.inner_to_scene_s(0, 24000, 0, 0, play_rate=0)


class ScenePlans(unittest.TestCase):
    def test_s1_with_voices_moves_narration_and_covers_it(self):
        p = K.plan_scene(facts(her(S1_LO, S1_HI, [CLICK, VOICES]), narration=(5216, 6091)), ROW1)
        self.assertEqual(p["refusals"], [])
        self.assertEqual(p["section"], [0, 5265])
        v_end = 0 + (5899 * 800 + 248000) / 24000.0          # 206.9667 s
        n0 = K.ceil_frames(v_end, 25)
        self.assertEqual(p["narration"]["frames"], [n0, n0 + 875])
        self.assertEqual(p["planned_end"], max(5265, n0 + 875))
        self.assertAlmostEqual(p["extend_mode"]["new_end_s"], p["planned_end"] / 25.0)

    def test_s1_without_voices_reports_and_refuses_overrun(self):
        p = K.plan_scene(facts(her(S1_LO, S1_HI, [CLICK]), narration=(5216, 6091)), ROW1)
        self.assertEqual(p["narration"]["action"], "report")
        self.assertTrue(any(r.startswith("NARRATION_PAST_HER_END") for r in p["refusals"]))
        self.assertEqual(p["planned_end"], 5265)              # her length only; narration not covered
        self.assertTrue(any(w.startswith("NO_VOICES_IN_HER_LS") for w in p["warnings"]))

    def test_s1_override_is_an_explicit_decision(self):
        row = dict(ROW1, narration_override_start_s=100.0)
        p = K.plan_scene(facts(her(S1_LO, S1_HI, [CLICK]), narration=(5216, 6091)), row)
        self.assertEqual(p["refusals"], [])
        self.assertEqual(p["narration"]["frames"], [2500, 3375])
        self.assertEqual(p["planned_end"], 5265)

    def test_s2_narration_cannot_fit_a_5s_shot(self):
        row = dict(ROW1, narration_rule="inside_shot", her_sequence="/Game/KK_S2_Shrine/LS_NEW_SHRINE")
        p = K.plan_scene(facts(her(0, 150), narration=(104, 1973)), row)
        self.assertEqual(p["section"], [0, 125])
        self.assertTrue(any(r.startswith("NARRATION_NOT_INSIDE_SHOT") for r in p["refusals"]))
        ok = K.plan_scene(facts(her(0, 150), narration=(10, 100)), row)          # control: fits
        self.assertFalse(any(r.startswith("NARRATION_NOT_INSIDE_SHOT") for r in ok["refusals"]))

    def test_section_past_end_refuses_unless_allowed(self):
        rise = {"track": "Hangar Rise", "cls": "MovieSceneSubTrack", "start": -500, "end": 775}
        row = dict(ROW1, narration_rule="none")
        p = K.plan_scene(facts(her(0, 150), extra=[rise], land=None), row)
        self.assertTrue(any(r.startswith("SECTION_PAST_PLANNED_END") for r in p["refusals"]))
        p2 = K.plan_scene(facts(her(0, 150), extra=[rise], land=None), dict(row, allow_truncate=["Hangar Rise"]))
        self.assertFalse(any(r.startswith("SECTION_PAST_PLANNED_END") for r in p2["refusals"]))
        p3 = K.plan_scene(facts(her(0, 150), extra=[dict(rise, end=100)], land=None), row)   # control: ends inside
        self.assertEqual(p3["refusals"], [])

    def test_start_options_and_land_warning(self):
        row = dict(ROW1, narration_rule="none")
        keep = K.plan_scene(facts(her(S1_LO, S1_HI), land=104, strike=130), row)
        self.assertTrue(any(w.startswith("SHOT_STARTS_BEFORE_LAND") for w in keep["warnings"]))
        land = K.plan_scene(facts(her(S1_LO, S1_HI), land=104, strike=130), dict(row, start_option="land_plus_strike"))
        self.assertEqual(land["section"], [130, 130 + 5265])
        self.assertFalse(any(w.startswith("SHOT_STARTS_BEFORE_LAND") for w in land["warnings"]))
        self.assertEqual(sorted(land["start_candidates"]), ["keep", "land", "land_plus_strike"])
        none = K.plan_scene(facts(her(S1_LO, S1_HI), land=None), dict(row, start_option="land"))
        self.assertTrue(any(r.startswith("START_UNKNOWN") for r in none["refusals"]))
        at = K.plan_scene(facts(her(S1_LO, S1_HI)), dict(row, start_option="at_s", at_s=31.0))
        self.assertEqual(at["section"][0], 775)

    def test_s4_length_and_24fps_scene(self):
        row = dict(ROW1, narration_rule="none")
        p = K.plan_scene(facts(her(0, 4920), playback=(0, 1000), land=None), row)
        self.assertEqual(p["section"], [0, 4100])
        self.assertAlmostEqual(p["end_change_s"], (4100 - 1000) / 25.0)
        p24 = K.plan_scene(facts(her(S1_LO, S1_HI), fps=24.0, land=None), row)
        self.assertEqual(p24["section"], [0, 5055])
        self.assertTrue(any(w.startswith("LENGTH_OFF_GRID") for w in p24["warnings"]))
        self.assertFalse(any(w.startswith("LENGTH_OFF_GRID") for w in
                             K.plan_scene(facts(her(S1_LO, S1_HI), land=None), row)["warnings"]))  # control @25

    def test_tick_mismatch_keeps_seconds(self):
        row = dict(ROW1, narration_rule="none")
        p = K.plan_scene(facts(her(S1_LO, S1_HI), tick=60000.0, land=None), row)
        self.assertEqual(p["section"], [0, 5265])
        self.assertTrue(any(w.startswith("TICK_RESOLUTIONS_DIFFER") for w in p["warnings"]))

    def test_missing_her_or_target(self):
        self.assertTrue(K.plan_scene(facts(her(0, 1, exists=False)), ROW1)["refusals"][0].startswith("HER_LS_MISSING"))
        f = facts(her(S1_LO, S1_HI))
        f["target"] = None
        self.assertTrue(K.plan_scene(f, ROW1)["refusals"][0].startswith("TARGET_SECTION_NOT_FOUND"))

    def test_her_audio_lands_where_she_set_it(self):
        row = dict(ROW1, narration_rule="none", start_option="at_s", at_s=4.16)
        p = K.plan_scene(facts(her(S1_LO, S1_HI, [CLICK]), land=None), row)
        a = p["her_audio_in_scene"][0]
        self.assertAlmostEqual(a["scene_start_s"], 4.16)                  # her click starts at her lower bound
        self.assertAlmostEqual(a["scene_end_s"], 4.16 + 4477 / 30.0)


class ArgsAndGates(unittest.TestCase):
    def test_shipped_args_validate_and_are_dry(self):
        with open(os.path.join(HERE, "klara_hookin_args.json"), encoding="utf-8") as h:
            args = json.load(h)
        self.assertEqual(K.validate_args(args), [])
        self.assertEqual(args["mode"], "DRY")
        bad = copy.deepcopy(args)
        bad["mode"] = "APPLY"
        bad["scenes"]["1"]["start_option"] = "soon"
        bad["scenes"]["2"]["scene_sequence"] = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
        v = K.validate_args(bad)
        self.assertTrue(any(x.startswith("MODE_INVALID") for x in v))
        self.assertTrue(any("START_OPTION_INVALID" in x for x in v))
        self.assertTrue(any("TARGET_IS_THE_MASTER" in x for x in v))

    def test_live_gates(self):
        clean = {"content": [], "maps": []}
        self.assertEqual(K.live_gates({"mode": "DRY", "census": clean}), [])
        g = K.live_gates({"mode": "APPLY_SEQ", "confirm": "APPLY_SEQ KLARAHOOK", "census": clean, "decided_by": "Gary"})
        self.assertEqual(g, [])
        g = K.live_gates({"mode": "APPLY_SEQ", "confirm": "APPLY_STREAM KLARAHOOK", "census": clean, "decided_by": "x"})
        self.assertTrue(g and g[0].startswith("CONFIRM_MISMATCH"))
        g = K.live_gates({"mode": "APPLY_STREAM", "confirm": "APPLY_STREAM KLARAHOOK", "decided_by": "",
                          "census": {"content": ["/Game/X"], "maps": []}, "pie": True, "sequencer_open": "/Game/M"})
        self.assertEqual(len(g), 4)
        g = K.live_gates({"mode": "REVERT_SEQ", "confirm": "REVERT_SEQ KLARAHOOK", "census": clean})
        self.assertEqual(g, ["NO_APPLIED_RECORD"])

    def test_census_gate(self):
        self.assertEqual(K.census_gate({"content": ["/Game/A"], "maps": []}, ["/Game/A"], []), [])
        self.assertEqual(len(K.census_gate({"content": ["/Game/A", "/Game/B"], "maps": ["/Game/W"]}, ["/Game/A"], [])), 2)

    def test_seq_drift(self):
        after = {"target": {"sequence": "/Game/H", "start": 0, "end": 5265, "start_offset_tick": 0},
                 "narration": [5216, 6091], "vis_track": [{"levels": ["L_Animals"], "range": [0, 5265]}]}
        self.assertEqual(K.seq_drift(copy.deepcopy(after), {"after": after}), [])
        moved = copy.deepcopy(after)
        moved["target"]["end"] = 5266
        moved["narration"] = [5217, 6092]
        self.assertEqual(len(K.seq_drift(moved, {"after": after})), 2)

    def test_import_runs_nothing(self):
        self.assertIsNone(K.unreal)


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=1).result
    print("KLARAHOOK_HARNESS|run=%d|failures=%d|errors=%d" % (result.testsRun, len(result.failures), len(result.errors)))
    sys.exit(0 if result.wasSuccessful() else 1)
