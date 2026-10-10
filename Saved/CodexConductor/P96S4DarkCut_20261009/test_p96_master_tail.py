"""Offline positive/negative controls for the P96 Master-tail bridge."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("p96_master_tail_core", os.path.join(HERE, "p96_master_tail_core.py"))
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def record(count=67):
    return {"run": "P96-LIVE", "plan": {"visibility": [
        {"group": C.SOURCE_GROUP, "path": "/World/A%02d" % i, "label": "S4 Lattice %02d" % i}
        for i in range(count)] + [{"group": "p04_lights", "path": "/World/P04", "label": "P04"}]}}


class Positive(unittest.TestCase):
    def test_exact_67_inventory(self):
        rows = C.inventory_from_p96(record())
        self.assertEqual(len(rows), 67); self.assertEqual(len({row["path"] for row in rows}), 67)

    def test_cut_rounds_up_and_bridges_two_tail_frames(self):
        got = C.master_window(24000, 24)
        self.assertEqual(got["cut_frame_exact"], 29317.44)
        self.assertEqual(got["hidden_range"], [29316, 29319])
        self.assertEqual(got["fade_keys"], [[29316, 0.0], [29318, 1.0], [29319, 0.0]])

    def test_plan_is_master_only_and_stable(self):
        args = {"tail_frames": 2, "release_frames": 1, "compiled_s4_cut_tick": 29317440}
        a = C.build_plan(record(), 24000, 24, args); b = C.build_plan(record(), 24000, 24, args)
        self.assertEqual(C.digest(a), C.digest(b)); self.assertEqual(a["master"], C.MASTER)


class Negative(unittest.TestCase):
    def test_wrong_inventory_count_refused(self):
        with self.assertRaisesRegex(C.PlanError, "INVENTORY_COUNT"):
            C.inventory_from_p96(record(66))

    def test_duplicate_inventory_refused(self):
        bad = record(); bad["plan"]["visibility"][1]["path"] = bad["plan"]["visibility"][0]["path"]
        with self.assertRaisesRegex(C.PlanError, "DUPLICATE"):
            C.inventory_from_p96(bad)

    def test_more_than_two_tail_frames_refused(self):
        with self.assertRaisesRegex(C.PlanError, "MASTER_WINDOW_ARGS"):
            C.master_window(24000, 24, 3, 1)

    def test_release_must_be_one_frame(self):
        with self.assertRaisesRegex(C.PlanError, "MASTER_WINDOW_ARGS"):
            C.master_window(24000, 24, 2, 2)

    def test_live_source_has_guarded_transaction_surface(self):
        text = open(os.path.join(HERE, "p96_master_tail.py"), encoding="utf-8").read()
        for token in ("DRY", "APPLY", "REVERT", "PreP96MasterTail", 'MARK = "P96_MASTER_TAIL"', '"%s_APPLY_OK',
                      'set_property_name_and_path("bHidden", "bHidden")', "MovieSceneFadeTrack"):
            self.assertIn(token, text)
        self.assertNotIn("save_all", text.lower()); self.assertNotIn("delete_asset", text)

    def test_shipped_args_are_dry(self):
        args = json.load(open(os.path.join(HERE, "p96_master_tail_args.json"), encoding="utf-8"))
        self.assertEqual((args["mode"], args["confirm"], args["plan_sha256"]), ("DRY", "", ""))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    failed = len(result.failures) + len(result.errors)
    print("P96_MASTER_TAIL_HARNESS_%s|passed=%d|total=%d|positive=3|negative=6" %
          ("OK" if not failed else "FAILED", result.testsRun - failed, result.testsRun))
    raise SystemExit(1 if failed else 0)
