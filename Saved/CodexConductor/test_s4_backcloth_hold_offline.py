"""Offline positive/negative controls for s4_backcloth_hold.py. No Unreal."""
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s4_backcloth_hold as H  # noqa: E402


def args(**kw):
    with open(os.path.join(HERE, H.ARGS_NAME), encoding="utf-8") as f:
        a = json.load(f)
    a.update(kw)
    return a


class Plan(unittest.TestCase):
    def test_positive_one_frame_keep(self):
        p = H.plan_hold([0, 4890], [{"range": [0, 775], "active": True}], 11.0, 24000.0, args())
        self.assertEqual(p["section_range"], [775, 776])
        self.assertEqual(p["hold_range"], [775, 4890])
        self.assertEqual(p["start_frame_offset_tick"], 263040)
        self.assertAlmostEqual(p["hold_cache_time_s"], 10.96)
        self.assertEqual(p["completion"], "KEEP_STATE")

    def test_negative_controls(self):
        with self.assertRaisesRegex(H.PlanError, "ACTIVE_FOLD_COUNT"):
            H.plan_hold([0, 4890], [], 11.0, 24000.0, args())
        with self.assertRaisesRegex(H.PlanError, "FOLD_NOT_AT_ZERO"):
            H.plan_hold([0, 4890], [{"range": [1, 775]}], 11.0, 24000.0, args())
        with self.assertRaisesRegex(H.PlanError, "HOLD_TIME_NOT_DOWN"):
            H.plan_hold([0, 4890], [{"range": [0, 775]}], 8.0, 24000.0, args())
        with self.assertRaisesRegex(H.PlanError, "NOTHING_TO_HOLD"):
            H.plan_hold([0, 775], [{"range": [0, 775]}], 11.0, 24000.0, args())


class Conflicts(unittest.TestCase):
    def test_positive_and_negative(self):
        rows = [{"binding": "S4 Backcloth Hold: P04 Backcloth (baked)", "tracks": [
            {"name": "S4 Backcloth Cache Hold", "class": "MovieSceneGeometryCacheTrack",
             "sections": [{"range": [775, 776]}]}]}]
        self.assertEqual(len(H.conflict_rows(rows, "P04 Backcloth (baked)", "S4 Backcloth Cache Hold", [775, 4890])), 1)
        rows[0]["tracks"][0]["name"] = "Earlier"
        rows[0]["tracks"][0]["sections"][0]["range"] = [0, 775]
        self.assertEqual(H.conflict_rows(rows, "P04 Backcloth (baked)", "S4 Backcloth Cache Hold", [775, 4890]), [])


class Readback(unittest.TestCase):
    W = {"range": [775, 776], "completion": "KEEP_STATE", "cache": "/Game/X", "start_offset": 263040,
         "end_offset": 0, "first_loop_offset": 0, "play_rate": 1.0, "reverse": False}

    def test_positive_and_each_negative(self):
        self.assertEqual(H.readback_diff(self.W, copy.deepcopy(self.W)), [])
        for k, v in (("range", [775, 777]), ("completion", "RESTORE_STATE"), ("cache", "/Game/Y"),
                     ("start_offset", 263039), ("end_offset", 1), ("first_loop_offset", 1),
                     ("play_rate", 0.0), ("reverse", True)):
            got = copy.deepcopy(self.W); got[k] = v
            self.assertTrue(H.readback_diff(self.W, got), k)


class Args(unittest.TestCase):
    def test_shipped_dry_and_confirms(self):
        a = args()
        self.assertEqual(H.validate_args(a), [])
        self.assertEqual((a["mode"], a["confirm"], a["decided_by"]), ("DRY", "", ""))
        ap = args(mode="APPLY", confirm="APPLY S4BACKCLOTH", decided_by="conductor")
        self.assertEqual(H.validate_args(ap), [])
        self.assertIn("CONFIRM", H.validate_args(dict(ap, confirm="APPLY S4HOLD")))
        self.assertIn("SECTION_FRAMES_MUST_BE_1", H.validate_args(dict(ap, section_frames=2)))
        self.assertEqual(H.validate_args(args(mode="REVERT", confirm="REVERT S4BACKCLOTH")), [])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    bad = len(result.failures) + len(result.errors)
    print("HARNESS %d/%d passed" % (result.testsRun - bad, result.testsRun))
    raise SystemExit(1 if bad else 0)
