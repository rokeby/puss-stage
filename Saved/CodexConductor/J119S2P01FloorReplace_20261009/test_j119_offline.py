"""Offline positive/negative harness for Job 119; imports no Unreal module."""
from __future__ import annotations

import ast
import importlib.util
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "j119_s2_p01_floor_replace.py"
spec = importlib.util.spec_from_file_location("j119_tool", TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class Geometry(unittest.TestCase):
    def test_fit_equal_cube_positive(self):
        source = {"bbox_min": [-50, -50, -50], "bbox_max": [50, 50, 50],
                  "location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [2, 3, .01]}
        target = {"bbox_min": [-50, -50, -50], "bbox_max": [50, 50, 50],
                  "location": [100, 200, -4.5], "rotation": [0, 0, 90], "scale": [4, 5, .01]}
        got = tool.fit_transform(source, target)
        self.assertEqual(got, {"location": [100, 200, -4.5], "rotation": [0, 0, 90], "scale": [4, 5, .01]})

    def test_fit_different_bounds_positive(self):
        source = {"bbox_min": [0, 0, 0], "bbox_max": [10, 20, 2],
                  "location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}
        target = {"bbox_min": [-5, -5, -1], "bbox_max": [5, 5, 1],
                  "location": [100, 200, 3], "rotation": [0, 0, 0], "scale": [2, 4, .5]}
        got = tool.fit_transform(source, target)
        self.assertEqual(got["scale"], [2, 2, .5])
        self.assertEqual(got["location"], [90, 180, 2.5])

    def test_degenerate_negative(self):
        row = {"bbox_min": [0, 0, 0], "bbox_max": [0, 1, 1], "location": [0, 0, 0],
               "rotation": [0, 0, 0], "scale": [1, 1, 1]}
        with self.assertRaises(ValueError):
            tool.fit_transform(row, row)

    def test_pitch_negative(self):
        source = {"bbox_min": [-1, -1, -1], "bbox_max": [1, 1, 1], "location": [0, 0, 0],
                  "rotation": [0, 0, 0], "scale": [1, 1, 1]}
        target = dict(source, rotation=[0, 1, 0])
        with self.assertRaises(ValueError):
            tool.fit_transform(source, target)


class Gates(unittest.TestCase):
    def test_confirm_positive_and_negative(self):
        self.assertTrue(tool.confirm_ok("DRY", ""))
        self.assertTrue(tool.confirm_ok("APPLY", "APPLY J119S2P01FLOOR"))
        self.assertTrue(tool.confirm_ok("REVERT", "REVERT J119S2P01FLOOR"))
        self.assertFalse(tool.confirm_ok("APPLY", "yes"))
        self.assertFalse(tool.confirm_ok("REVERT", "APPLY J119S2P01FLOOR"))

    def test_sequence_actor_tracks_inherit_positive(self):
        rows = [{"track_class": "MovieScene3DTransformTrack", "property": "", "object_kind": "actor"},
                {"track_class": "MovieSceneBoolTrack", "property": "bHidden|bHidden", "object_kind": "ancestor_actor"}]
        blockers, inherited = tool.sequence_binding_policy(rows)
        self.assertEqual(blockers, [])
        self.assertEqual(len(inherited), 2)

    def test_sequence_component_track_negative(self):
        row = {"track_class": "MovieSceneBoolTrack", "property": "bHidden|bHidden", "object_kind": "component"}
        blockers, inherited = tool.sequence_binding_policy([row])
        self.assertEqual(blockers, [row])
        self.assertEqual(inherited, [])

    def test_digest_detects_drift(self):
        self.assertEqual(tool.digest({"a": 1}), tool.digest({"a": 1}))
        self.assertNotEqual(tool.digest({"a": 1}), tool.digest({"a": 2}))


class StaticSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = TOOL.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.text)

    def test_persistent_only_and_klara_forbidden(self):
        self.assertIn('"save_allowlist": [WORLD]', self.text)
        self.assertIn('"klara_packages_forbidden": list(KLARA_PACKAGES)', self.text)
        self.assertNotIn("save_dirty_packages", self.text)
        self.assertNotIn("save_asset(", self.text)

    def test_old_actors_never_destroyed_negative_control(self):
        calls = [node for node in ast.walk(self.tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "destroy_actor"]
        self.assertEqual(len(calls), 1)
        rendered = ast.unparse(calls[0])
        self.assertIn("owned[row[", rendered)
        self.assertIn("created_actor_path", rendered)

    def test_bhidden_contract_and_no_inert_property(self):
        self.assertIn('"bhidden"', self.text.lower())
        self.assertNotIn("bHiddenInGame", self.text)

    def test_backup_record_and_targeted_save(self):
        self.assertIn("PreJ119S2P01Floor", self.text)
        self.assertLess(self.text.index("_write_json(record_path, record, True)"), self.text.index("duplicate_actor"))
        self.assertIn("save_current_level", self.text)

    def test_request_is_guarded_saved_route(self):
        data = json.loads((HERE / "j119_s2_p01_floor_replace_request.json").read_text(encoding="utf-8"))
        args = data["arguments"]
        self.assertEqual(args["tool_name"], "ExecuteProjectPythonFile")
        self.assertEqual(args["arguments"]["relativeSavedPath"],
                         "CodexConductor/J119S2P01FloorReplace_20261009/j119_s2_p01_floor_replace.py")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "positive_controls": 8, "negative_controls": 8, "passed": result.wasSuccessful()}
    (HERE / "harness_result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("J119_HARNESS|tests=%d|failures=%d|errors=%d|positive_controls=8|negative_controls=8" %
          (result.testsRun, len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
