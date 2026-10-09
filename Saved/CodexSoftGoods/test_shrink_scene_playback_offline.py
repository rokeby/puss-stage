"""Offline positive/negative controls for shrink_scene_playback.py (no Unreal import)."""

import importlib.util
import os
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("scene_shrink", os.path.join(HERE, "shrink_scene_playback.py"))
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)


def section(identifier, start, end, active=True):
    return {"id": identifier, "start": start, "end": end, "has_end": end is not None, "active": active}


def passage(start, frames):
    return {"section_start_tick": start, "section_start_s": start / 24000.0,
            "channels": {"Travel": [{"frame": frame, "sub_frame": 0.0, "value": value}
                                     for frame, value in frames]}}


class ArgsControls(unittest.TestCase):
    def test_positive_exact_confirm(self):
        self.assertEqual(S.validate_args({"mode": "DRY", "confirm": "DRY SHRINK",
                                          "cue_label": "I2", "new_end_frame": 1950}), [])

    def test_negative_loose_confirm_and_bool_frame(self):
        problems = S.validate_args({"mode": "APPLY", "confirm": "yes", "cue_label": "I2",
                                    "new_end_frame": True})
        self.assertTrue(any("CONFIRM" in item for item in problems))
        self.assertTrue(any("INT" in item for item in problems))


class SectionControls(unittest.TestCase):
    def test_positive_crossing_section_is_trimmed(self):
        changes = S.plan_section_changes([section("cross", 100, 300)], 200)
        self.assertEqual((changes[0]["action"], changes[0]["after"]["end"]), ("trim", 200))

    def test_negative_section_ending_at_boundary_is_untouched(self):
        self.assertEqual(S.plan_section_changes([section("done", 100, 200)], 200), [])

    def test_positive_later_section_is_deactivated(self):
        changes = S.plan_section_changes([section("late", 200, 300)], 200)
        self.assertEqual((changes[0]["action"], changes[0]["after"]["active"]), ("deactivate", False))

    def test_negative_earlier_section_is_not_deactivated(self):
        changes = S.plan_section_changes([section("early", 100, 190)], 200)
        self.assertEqual(changes, [])


class CutCoverageControls(unittest.TestCase):
    def test_positive_adjacent_cuts_are_gap_free(self):
        report = S.cut_coverage_rows(0, 200, [section("a", 0, 100), section("b", 100, 200)])
        self.assertEqual(report["gaps"], [])

    def test_negative_cut_gap_is_refused(self):
        report = S.cut_coverage_rows(0, 200, [section("a", 0, 90), section("b", 100, 200)])
        self.assertEqual(report["gaps"], [[90, 100]])


class KeyCarryControls(unittest.TestCase):
    def test_positive_downstream_keys_follow_negative_delta(self):
        before = {"early": passage(0, [(10, 0.0), (20, 1.0)]),
                  "later": passage(5000, [(5010, 0.0), (5020, 1.0)])}
        after = {"early": passage(0, [(10, 0.0), (20, 1.0)]),
                 "later": passage(4000, [(4010, 0.0), (4020, 1.0)])}
        self.assertEqual(S.passage_key_delta_failures(before, after, ["later"], -1000, 0), [])

    def test_negative_section_moves_but_keys_do_not(self):
        before = {"later": passage(5000, [(5010, 0.0), (5020, 1.0)])}
        after = {"later": passage(4000, [(5010, 0.0), (5020, 1.0)])}
        self.assertTrue(S.passage_key_delta_failures(before, after, ["later"], -1000, 0))


class SegmentControls(unittest.TestCase):
    def test_positive_earlier_cue_and_later_boundaries(self):
        before = [{"label": "P2", "start": 0.0, "end": 10.0},
                  {"label": "I2", "start": 10.0, "end": 20.0},
                  {"label": "P3", "start": 20.0, "end": 30.0}]
        after = [{"label": "P2", "start": 0.0, "end": 10.0},
                 {"label": "I2", "start": 10.0, "end": 15.0},
                 {"label": "P3", "start": 15.0, "end": 25.0}]
        self.assertEqual(S.segment_retime_failures(before, after, "I2", -5.0), [])

    def test_negative_earlier_segment_shift_is_caught(self):
        before = [{"label": "P2", "start": 0.0, "end": 10.0},
                  {"label": "I2", "start": 10.0, "end": 20.0}]
        after = [{"label": "P2", "start": -1.0, "end": 9.0},
                 {"label": "I2", "start": 10.0, "end": 15.0}]
        self.assertTrue(S.segment_retime_failures(before, after, "I2", -5.0))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("SCENE_SHRINK_HARNESS|passed=%d|failed=%d|errors=%d" %
          (passed, len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
