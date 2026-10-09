from __future__ import annotations

import copy
import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path

import chainlink_weave as cw


HERE = Path(__file__).resolve().parent


class ChainlinkPositiveControls(unittest.TestCase):
    def test_default_interlocks_without_intersections(self):
        weave = cw.build_weave()
        result = cw.validate_interlocks(weave)
        self.assertTrue(result["ok"], result)
        self.assertGreater(result["knuckle_count"], 20)
        self.assertEqual(result["non_knuckle_intersections"], 0)

    def test_seed_is_deterministic(self):
        self.assertEqual(cw.deterministic_digest(cw.build_weave()), cw.deterministic_digest(cw.build_weave()))
        self.assertNotEqual(
            cw.deterministic_digest(cw.build_weave()),
            cw.deterministic_digest(cw.build_weave(replace(cw.WeaveConfig(), seed=5710))),
        )

    def test_budget_and_lods(self):
        lods = cw.build_lods()
        self.assertLessEqual(lods["lod0"].triangles, 20_000)
        self.assertLess(lods["lod1"].triangles, lods["lod0"].triangles)
        self.assertEqual(lods["lod2"]["triangles"], 2)

    def test_one_draw_per_scalar_is_recorded(self):
        weave = cw.build_weave()
        self.assertGreater(weave.draws, len(weave.pickets) * 4)
        self.assertIsInstance(weave.draws, int)

    def test_option_off_is_byte_identical(self):
        params = {"fence": {"asset": "FenceOpen", "damage": 0.48}}
        before = json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
        called = []

        def legacy(value):
            called.append("legacy")
            return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

        def weave(_value):
            called.append("weave")
            return "changed"

        result = cw.dispatch_p02_chainlink(params, legacy, weave)
        after = json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(before, after)
        self.assertEqual(called, ["legacy"])
        self.assertEqual(result, legacy(copy.deepcopy(params)))

    def test_option_weave_selects_new_builder(self):
        called = []
        result = cw.dispatch_p02_chainlink(
            {"chainlink": "weave"},
            lambda _: called.append("legacy"),
            lambda _: called.append("weave") or "woven",
        )
        self.assertEqual(result, "woven")
        self.assertEqual(called, ["weave"])


class ChainlinkNegativeControls(unittest.TestCase):
    def test_budget_refuses_overrun(self):
        with self.assertRaisesRegex(ValueError, "TRI_BUDGET_REFUSED"):
            cw.build_weave(replace(cw.WeaveConfig(), diamond_m=0.05, tube_sides=8, samples_per_half_diamond=4))

    def test_invalid_option_refused(self):
        with self.assertRaisesRegex(ValueError, "unsupported chainlink option"):
            cw.dispatch_p02_chainlink({"chainlink": "magic"}, lambda _: None, lambda _: None)

    def test_apply_requires_confirmation(self):
        with self.assertRaisesRegex(ValueError, "confirmation"):
            cw._ensure_outputs("APPLY", "wrong", "P57-NEG")

    def test_bad_tube_sides_refused(self):
        with self.assertRaisesRegex(ValueError, "tube_sides"):
            cw.build_weave(replace(cw.WeaveConfig(), tube_sides=3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
