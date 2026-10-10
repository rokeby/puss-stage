"""Offline +/- harness for Job 128. Does not import Unreal."""
import copy
import json
import os
import unittest

import job128_core as core

HERE = os.path.dirname(os.path.abspath(__file__))


def row(index, left_box=None, right_box=None, lx=0.0, rx=0.0):
    return {"cue_index": 122 + index, "cue_guid": "%032X" % (index + 1),
            "cue_label": "P05 Wing %03d" % (index % 8 + 1),
            "left_local": {"location": [lx, -250.0, 0.0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
            "right_local": {"location": [rx, 250.0, 0.0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
            "left_world_transform": {"location": [100.0 + index*500, -250, 0], "rotation": [0,0,0], "scale": [1,1,1]},
            "right_world_transform": {"location": [100.0 + index*500, 250, 0], "rotation": [0,0,0], "scale": [1,1,1]},
            "left_box": left_box or {"min": [90.1+index*500, -300, 0], "max": [109.9+index*500, 50, 500]},
            "right_box": right_box or {"min": [90.1+index*500, -50, 0], "max": [109.9+index*500, 300, 500]},
            "left_inward": [0, 1, 0], "right_inward": [0, -1, 0]}


def rows():
    out = [row(i) for i in range(93)]
    # Discriminator equivalent to recorded cue 124: left is 6 cm behind right.
    out[2] = row(2, {"min": [1234, -100, 0], "max": [1253.8, 100, 500]},
                 {"min": [1245, -100, 0], "max": [1255, 100, 500]})
    return out


class Job128Harness(unittest.TestCase):
    def test_pos_recorded_sign_evidence(self):
        evidence = core.recorded_sign_evidence()
        self.assertEqual(evidence["before_cm"], 0.0)
        self.assertGreater(evidence["minus_20_cm"], 11.0)
        self.assertEqual(evidence["plus_20_cm"], 0.0)

    def test_pos_choose_minus_sign(self):
        chosen = core.choose_sign(rows())
        self.assertEqual(chosen["chosen"]["sign"], -1.0)
        self.assertEqual(chosen["chosen"]["overlap_count_after"], 0)
        self.assertGreater(chosen["chosen"]["minimum_gap_after_cm"], 0.0)

    def test_pos_all_93_target_relation(self):
        plan = core.choose_sign(rows())["chosen"]
        self.assertEqual(plan["row_count"], 93)
        self.assertTrue(all(abs(x["after_left_local_x_cm"] - x["right_local_x_cm"] + 20) < 1e-9
                            for x in plan["rows"]))

    def test_pos_world_transforms_listed(self):
        item = core.choose_sign(rows())["chosen"]["rows"][0]
        self.assertEqual(item["before_left_world_transform"]["location"][0], 100.0)
        self.assertEqual(item["after_left_world_transform"]["location"][0], 80.0)
        self.assertEqual(item["right_world_transform"]["location"][0], 100.0)

    def test_pos_x_only_guard(self):
        before = {"location": [0, 1, 2], "rotation": [3, 4, 5], "scale": [1, 1, 1]}
        after = copy.deepcopy(before); after["location"][0] = -20
        self.assertTrue(core.x_only_changed(before, after))

    def test_pos_stable_confirmation(self):
        plan = core.choose_sign(rows())["chosen"]
        self.assertEqual(core.confirm_token(plan), core.confirm_token(copy.deepcopy(plan)))

    def test_pos_right_and_other_passages_untouched(self):
        fp = {"p05_right_sha256": "r", "non_p05_show_sha256": "s", "other_passage_refs_sha256": "l"}
        self.assertEqual(core.untouched_refusals(fp, copy.deepcopy(fp)), [])

    def test_neg_wrong_count(self):
        with self.assertRaisesRegex(core.GateError, "P05_COUNT"):
            core.plan_rows(rows()[:-1])

    def test_neg_duplicate_guid(self):
        data = rows(); data[-1]["cue_guid"] = data[0]["cue_guid"]
        with self.assertRaisesRegex(core.GateError, "DUPLICATE"):
            core.plan_rows(data)

    def test_neg_non_p05(self):
        data = rows(); data[0]["cue_label"] = "P04 Wing 001"
        with self.assertRaisesRegex(core.GateError, "ROW_NOT_P05"):
            core.plan_rows(data)

    def test_neg_bad_inward_pair(self):
        data = rows(); data[0]["right_inward"] = [0, 1, 0]
        with self.assertRaisesRegex(core.GateError, "INWARD_NOT_OPPOSED"):
            core.plan_rows(data)

    def test_neg_tilted_pair(self):
        data = rows(); data[0]["left_inward"] = [0, 0, 1]; data[0]["right_inward"] = [0, 0, -1]
        with self.assertRaisesRegex(core.GateError, "P05_PAIR_NOT_LEVEL"):
            core.plan_rows(data)

    def test_neg_plus_sign_rejected(self):
        plus = core.plan_rows(rows(), 1.0)
        self.assertGreater(plus["overlap_count_after"], 0)

    def test_pos_live_geometry_tie_uses_recorded_sign(self):
        data = rows()
        # Symmetric identical 20 cm slabs make +/- equally good for every row.
        for i, value in enumerate(data):
            x = i * 500.0
            value["left_box"] = {"min": [x-9.9, -100, 0], "max": [x+9.9, 100, 500]}
            value["right_box"] = copy.deepcopy(value["left_box"])
        self.assertEqual(core.choose_sign(data)["chosen"]["sign"], -1.0)

    def test_neg_twenty_cm_insufficient_refuses(self):
        data = rows()
        for i, value in enumerate(data):
            x = i * 500.0
            value["left_box"] = {"min": [x-30, -100, 0], "max": [x+30, 100, 500]}
            value["right_box"] = copy.deepcopy(value["left_box"])
        with self.assertRaisesRegex(core.GateError, "CHOSEN_SIGN_STILL_OVERLAPS"):
            core.choose_sign(data)

    def test_neg_y_change_rejected(self):
        before = {"location": [0, 1, 2], "rotation": [3, 4, 5], "scale": [1, 1, 1]}
        after = copy.deepcopy(before); after["location"][0] = -20; after["location"][1] = 9
        self.assertFalse(core.x_only_changed(before, after))

    def test_neg_bad_magnitude(self):
        with self.assertRaisesRegex(core.GateError, "MAGNITUDE"):
            core.target_left_x(0, -1, 19)

    def test_neg_right_or_other_passage_change(self):
        before = {"p05_right_sha256": "r", "non_p05_show_sha256": "s", "other_passage_refs_sha256": "l"}
        after = dict(before); after["p05_right_sha256"] = "changed"
        self.assertEqual(core.untouched_refusals(before, after), ["RIGHT_WINGS_CHANGED"])
        after = dict(before); after["non_p05_show_sha256"] = "changed"
        self.assertEqual(core.untouched_refusals(before, after), ["OTHER_PASSAGES_SHOW_CHANGED"])
        after = dict(before); after["other_passage_refs_sha256"] = "changed"
        self.assertEqual(core.untouched_refusals(before, after), ["OTHER_PASSAGES_LEVEL_CHANGED"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Job128Harness)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "positive_controls": 8, "negative_controls": 10, "ok": result.wasSuccessful()}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True); handle.write("\n")
    print("JOB128_OFFLINE_HARNESS_%s|tests=%d|positive=8|negative=10" %
          ("PASS" if result.wasSuccessful() else "FAIL", result.testsRun))
    raise SystemExit(0 if result.wasSuccessful() else 1)
