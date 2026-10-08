import importlib.util
import os
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("guard", os.path.join(HERE, "sequence_completion_guard.py"))
G = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G)


def doc(track_class="MovieSceneVisibilityTrack", completion="RestoreState", end=90, playback_end=100):
    return {
        "file": "fixture.uasset", "sha256": "abc", "movie": {"PlaybackRange": [0, playback_end]},
        "tracks": [{"owner": "Fixture", "cls": track_class, "sections": [{
            "range": [10, end], "export": "Fixture.Section", "props": {
                "EvalOptions": {"CompletionMode": completion}}}]}],
    }


class CandidateControls(unittest.TestCase):
    def test_positive_restore_mid_scene(self):
        self.assertTrue(G.section_candidate("MovieSceneVisibilityTrack", [1, 9], "RestoreState", 10))

    def test_positive_project_default_mid_scene(self):
        self.assertTrue(G.section_candidate("MovieSceneSubTrack", [0, 9], "PROJECT_DEFAULT", 10))

    def test_negative_keep_state(self):
        self.assertFalse(G.section_candidate("MovieSceneVisibilityTrack", [1, 9], "KeepState", 10))

    def test_negative_reaches_end(self):
        self.assertFalse(G.section_candidate("MovieSceneVisibilityTrack", [1, 10], "RestoreState", 10))

    def test_negative_irrelevant_track(self):
        self.assertFalse(G.section_candidate("MovieSceneFloatTrack", [1, 9], "RestoreState", 10))

    def test_negative_open_spawn(self):
        self.assertFalse(G.section_candidate("MovieSceneSpawnTrack", None, "ProjectDefault", 10))


class SnapshotControls(unittest.TestCase):
    def test_snapshot_positive(self):
        out = G.snapshot_asset(doc(), "S1")
        self.assertEqual((len(out["candidates"]), out["candidates"][0]["completion"]), (1, "RESTORE_STATE"))

    def test_snapshot_negative(self):
        out = G.snapshot_asset(doc(completion="KeepState"), "S1")
        self.assertEqual(out["candidates"], [])


class GuardControls(unittest.TestCase):
    def test_apply_args_positive_and_negative(self):
        good = {"mode": "APPLY", "run": "P14-001", "confirm": "APPLY P14KEEP",
                "decided_by": "Gary", "targets": ["x"]}
        self.assertEqual(G.validate_args(good), [])
        self.assertIn("CONFIRM", G.validate_args(dict(good, confirm="yes")))
        self.assertIn("TARGETS", G.validate_args(dict(good, targets=[])))

    def test_target_selection_positive_and_negative(self):
        rows = [{"id": "a"}, {"id": "b"}]
        chosen, missing = G.choose_targets(rows, ["b", "missing"])
        self.assertEqual(([row["id"] for row in chosen], missing), (["b"], ["missing"]))

    def test_readback_positive_and_negative(self):
        want = [{"id": "x", "completion": "KEEP_STATE", "range": [1, 2]}]
        self.assertEqual(G.readback_diff(want, list(want)), [])
        self.assertTrue(G.readback_diff(want, [{"id": "x", "completion": "RESTORE_STATE", "range": [1, 2]}]))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("P14KEEP_HARNESS|passed=%d|failed=%d|errors=%d" % (
        result.testsRun - len(result.failures) - len(result.errors), len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)

