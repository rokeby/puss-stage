"""Offline positive/negative harness for go_markers_sync.py. Never imports or starts Unreal."""
import copy
import importlib.util
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("go_markers_sync", HERE / "go_markers_sync.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


def marker(frame, label):
    return dict(SYNC.MARKER_DEFAULTS, frame=frame, label=label)


class GoMarkerSyncHarness(unittest.TestCase):
    def test_time_parse_table(self):
        for text, expected in (("74.5", 74.5), ("1:14.5", 74.5), ("0:01:14.5", 74.5),
                               ("00:01:14:12", 74.48)):
            self.assertAlmostEqual(SYNC.parse_time(text), expected, places=8, msg=text)

    def test_bad_times_refused(self):
        for text in ("", "one minute", "-1", "1::2", "00:00:00:25", "1:2:3:4:5"):
            with self.subTest(text=text), self.assertRaises(SYNC.PlanError):
                SYNC.parse_time(text)

    def test_go_field_positive_and_negative(self):
        self.assertEqual(SYNC.parse_go_field("20 PASS"), ("20", "PASS", "GO 20 PASS"))
        self.assertEqual(SYNC.parse_go_field("3.5 HOLD"), ("3.5", "HOLD", "GO 3.5 HOLD"))
        self.assertEqual(SYNC.parse_go_field("7"), ("7", None, "GO 7"))
        for text in ("GO 2", "two HOLD", "2 pass", "2 WAIT", "2."):
            with self.subTest(text=text), self.assertRaises(SYNC.PlanError):
                SYNC.parse_go_field(text)

    def _fixture(self, confirm_moves=True):
        existing = {
            "/Game/A": [marker(100, "GO 1 HOLD"), marker(200, "GO 2 HOLD"),
                         marker(300, "GO 3 HOLD"), marker(900, "GO 99 PASS")],
            "/Game/B": [],
        }
        desired = [
            {"number": "1", "label": "GO 1 HOLD", "sequence": "/Game/A", "frame": 100, "segment": "I1"},
            {"number": "2", "label": "GO 2 PASS", "sequence": "/Game/A", "frame": 200, "segment": "I1"},
            {"number": "3", "label": "GO 3 HOLD", "sequence": "/Game/B", "frame": 350, "segment": "S1"},
            {"number": "4", "label": "GO 4 PASS", "sequence": "/Game/B", "frame": 400, "segment": "S1"},
        ]
        return existing, desired, SYNC.build_plan(desired, existing, confirm_moves=confirm_moves)

    def test_plan_classifies_all_four_actions_and_orphan(self):
        _existing, _desired, plan = self._fixture()
        self.assertEqual([row["action"] for row in plan["actions"]],
                         ["UNCHANGED", "RELABEL", "MOVE", "ADD"])
        self.assertEqual([(row["number"], row["label"]) for row in plan["orphans"]],
                         [("99", "GO 99 PASS")])

    def test_move_refused_without_confirm(self):
        existing, desired, _plan = self._fixture()
        with self.assertRaisesRegex(SYNC.PlanError, "CONFIRM_MOVES_REQUIRED"):
            SYNC.build_plan(desired, existing, confirm_moves=False)

    def test_expected_markers_preserve_non_go_and_orphan(self):
        existing, _desired, plan = self._fixture()
        existing["/Game/A"].append(marker(42, "InfinityStage.VampStart"))
        after_a = SYNC.expected_markers(existing["/Game/A"], plan["actions"], "/Game/A")
        labels = [(row["frame"], row["label"]) for row in after_a]
        self.assertIn((42, "InfinityStage.VampStart"), labels)
        self.assertIn((900, "GO 99 PASS"), labels)
        self.assertIn((200, "GO 2 PASS"), labels)
        self.assertNotIn((200, "GO 2 HOLD"), labels)
        self.assertNotIn((300, "GO 3 HOLD"), labels)

    def test_duplicate_existing_go_refused(self):
        existing = {"/Game/A": [marker(1, "GO 1")], "/Game/B": [marker(2, "GO 1 PASS")]}
        desired = [{"number": "1", "label": "GO 1", "sequence": "/Game/A", "frame": 1, "segment": "P1"}]
        with self.assertRaisesRegex(SYNC.PlanError, "DUPLICATE_EXISTING_GO"):
            SYNC.build_plan(desired, existing, confirm_moves=True)

    @staticmethod
    def fake_sequence():
        return {
            "path": "/Game/Fake",
            "markers": [marker(100, "GO 1 HOLD")],
            "tracks": [{"class": "MovieSceneFloatTrack", "display_name": "Intensity", "row": 0,
                        "sections": [{"range": [0, 1000], "row": 0, "sub_sequence": None, "time_scale": 1.0,
                                      "channels": [{"name": "Value", "keys": [
                                          {"time": [100, 0.0], "value": 1.0},
                                          {"time": [200, 0.0], "value": 2.0}]}]}]}],
        }

    def test_guard_positive_marker_only_change_passes(self):
        before = self.fake_sequence()
        after = copy.deepcopy(before)
        after["markers"] = [marker(120, "GO 1 PASS"), marker(300, "GO 2")]
        SYNC.assert_timing_unchanged(SYNC.fake_timing_fingerprint(before), SYNC.fake_timing_fingerprint(after))

    def test_guard_float_tolerance(self):
        before = self.fake_sequence()
        after = copy.deepcopy(before)
        after["tracks"][0]["sections"][0]["channels"][0]["keys"][0]["value"] += 0.00009
        SYNC.assert_timing_unchanged(SYNC.fake_timing_fingerprint(before), SYNC.fake_timing_fingerprint(after))

    def test_guard_negative_key_move_trips_timing_changed(self):
        before = self.fake_sequence()
        after = copy.deepcopy(before)
        after["markers"] = [marker(120, "GO 1 PASS")]
        after["tracks"][0]["sections"][0]["channels"][0]["keys"][0]["time"][0] += 1
        with self.assertRaisesRegex(SYNC.TimingChanged, "time"):
            SYNC.assert_timing_unchanged(SYNC.fake_timing_fingerprint(before), SYNC.fake_timing_fingerprint(after))

    def test_rule9_and_marker_api_shape(self):
        source = (HERE / "go_markers_sync.py").read_text(encoding="utf-8")
        self.assertIn("find_marked_frame_by_label", source)
        self.assertIn("get_marked_frames_from_sequence", source)
        self.assertIn("add_marked_frame_to_sequence", source)
        self.assertIn("delete_marked_frame(self.sequence", source)
        self.assertNotIn("add_possessable(", source)
        self.assertNotIn("evaluate_keys(", source)
        self.assertNotIn("bHiddenInGame", source)
        for forbidden in ("save_dirty_packages", "save_current_level", "save_all", "delete_asset", "reload_packages"):
            self.assertNotIn(forbidden, source)
        self.assertIn('"APPLY GO MARKERS"', source)
        self.assertIn('"REVERT GO MARKERS"', source)
        self.assertIn('"PreGoMarkerSync-%s"', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
