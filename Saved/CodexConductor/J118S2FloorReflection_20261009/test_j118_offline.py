"""Offline +/- harness for Job 118.  Uses system Python; imports no Unreal module."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
FIX = HERE / "j118_ppv_fix.py"
PROBE = HERE / "j118_floor_reflection_probe.py"

spec = importlib.util.spec_from_file_location("j118_ppv_fix", FIX)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Geometry(unittest.TestCase):
    def test_target_box_positive(self):
        rows = [
            {"min": [0, -100, -5], "max": [1000, 100, 0]},
            {"min": [1000, -200, -5], "max": [2000, 200, 0]},
        ]
        got = module.target_box(rows, 500, 200, 4500)
        self.assertEqual(got["min"], [-500, -700, -205])
        self.assertEqual(got["max"], [2500, 700, 4500])
        self.assertEqual(got["center"], [1000, 0, 2147.5])

    def test_target_box_negative_control(self):
        with self.assertRaises(ValueError):
            module.target_box([], 500, 200, 4500)

    def test_scale_positive(self):
        self.assertEqual(module.scaled_actor_scale([1, 2, 1], [100, 200, 50], [300, 400, 250]), [3, 4, 5])

    def test_scale_negative_control(self):
        with self.assertRaises(ValueError):
            module.scaled_actor_scale([1, 1, 1], [0, 20, 20], [100, 100, 100])

    def test_off_centre_brush_recenters_positive_and_negative(self):
        got = module.recentered_actor_location([10, 20, 30], [15, 10, 30], [1, 2, 1], [2, 4, 1],
                                               [1000, 2000, 3000])
        self.assertEqual(got, [990, 2020, 3000])
        self.assertNotEqual(got, [1000, 2000, 3000])  # negative control: actor origin != brush centre
        with self.assertRaises(ValueError):
            module.recentered_actor_location([0, 0, 0], [0, 0, 0], [1, 0, 1], [1, 1, 1], [0, 0, 0])


class SelectionAndGates(unittest.TestCase):
    def test_unique_template_positive(self):
        self.assertEqual(module.choose_template(["P01 PPV"], ""), "P01 PPV")
        self.assertEqual(module.choose_template(["A", "B"], "B"), "B")

    def test_ambiguous_template_negative_control(self):
        with self.assertRaises(ValueError):
            module.choose_template(["A", "B"], "")
        with self.assertRaises(ValueError):
            module.choose_template(["A"], "wrong")

    def test_confirm_positive_and_negative(self):
        self.assertTrue(module.confirm_ok("DRY", ""))
        self.assertTrue(module.confirm_ok("APPLY", "APPLY J118S2PPV"))
        self.assertTrue(module.confirm_ok("REVERT", "REVERT J118S2PPV"))
        self.assertFalse(module.confirm_ok("APPLY", "yes"))
        self.assertFalse(module.confirm_ok("REVERT", "APPLY J118S2PPV"))

    def test_digest_detects_drift(self):
        a = {"priority": 2.0, "fields": ["reflection_method"]}
        b = {"priority": 3.0, "fields": ["reflection_method"]}
        self.assertEqual(module.digest(a), module.digest(dict(a)))
        self.assertNotEqual(module.digest(a), module.digest(b))


class StaticSafety(unittest.TestCase):
    def setUp(self):
        self.probe = PROBE.read_text(encoding="utf-8")
        self.fix = FIX.read_text(encoding="utf-8")

    def test_probe_parses_and_has_no_unreal_save_api(self):
        ast.parse(self.probe)
        forbidden = ("save_current_level", "save_asset(", "save_loaded_asset", "save_dirty_packages")
        for token in forbidden:
            self.assertNotIn(token, self.probe)
        self.assertIn("before = census()", self.probe)
        self.assertIn("if before != after", self.probe)

    def test_probe_no_mutating_editor_calls_negative_control(self):
        forbidden = ("set_editor_property(", "set_actor_", "set_material(", "spawn_actor", "destroy_actor",
                     "duplicate_actor", "materialize_passage", "load_map(")
        for token in forbidden:
            self.assertNotIn(token, self.probe)
        # Writing the JSON evidence artifact is expected and is not an Unreal mutation.
        self.assertIn("json.dump(report", self.probe)

    def test_fix_names_only_persistent_package_for_save(self):
        self.assertIn('"packages_allowed_to_dirty_and_save": [WORLD]', self.fix)
        self.assertIn('"klara_packages_forbidden": sorted(KLARA_PACKAGES)', self.fix)
        self.assertIn("REVERT_REFUSES_KLARA_LEVEL", self.fix)
        self.assertNotIn("save_asset(", self.fix)

    def test_requests_are_narrow_execute_project_python(self):
        for name in ("j118_floor_reflection_probe_request.json", "j118_ppv_fix_request.json"):
            data = json.loads((HERE / name).read_text(encoding="utf-8"))
            args = data["arguments"]
            self.assertEqual(args["tool_name"], "ExecuteProjectPythonFile")
            self.assertTrue(args["arguments"]["relativeSavedPath"].startswith(
                "CodexConductor/J118S2FloorReflection_20261009/"))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "positive_controls": 8,
        "negative_controls": 8,
        "passed": result.wasSuccessful(),
    }
    (HERE / "harness_result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("J118_HARNESS|tests=%d|failures=%d|errors=%d|positive_controls=8|negative_controls=8" %
          (result.testsRun, len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
