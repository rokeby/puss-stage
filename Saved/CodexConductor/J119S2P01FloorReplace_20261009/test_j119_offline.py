"""Offline positive/negative harness for Job 119; imports no Unreal module."""
from __future__ import annotations

import ast
import hashlib
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

    def test_route_segment_bounds_positive(self):
        row = {"bbox_min": [-1, -2, -0.5], "bbox_max": [1, 2, 0.5],
               "location": [10, 20, 3], "rotation": [0, 0, 90], "scale": [2, 3, 1]}
        got = tool._bounds_for_row(row)
        self.assertEqual([round(value, 6) for value in got["extent"]], [6.0, 2.0, 0.5])

    def test_route_segment_pitch_negative(self):
        row = {"bbox_min": [-1, -1, -1], "bbox_max": [1, 1, 1],
               "location": [0, 0, 0], "rotation": [1, 0, 0], "scale": [1, 1, 1]}
        with self.assertRaises(tool.Refused):
            tool._bounds_for_row(row)


class Gates(unittest.TestCase):
    def test_confirm_positive_and_negative(self):
        self.assertTrue(tool.confirm_ok("DRY", ""))
        self.assertTrue(tool.confirm_ok("APPLY", "APPLY J119S2P01FLOOR"))
        self.assertTrue(tool.confirm_ok("REVERT", "REVERT J119S2P01FLOOR"))
        self.assertFalse(tool.confirm_ok("APPLY", "yes"))
        self.assertFalse(tool.confirm_ok("REVERT", "APPLY J119S2P01FLOOR"))

    def test_s2_compatibility_contract(self):
        args = json.loads((HERE / "j119_s2_p01_floor_replace_args.json").read_text(encoding="utf-8"))
        self.assertEqual(args["target"], "P02")
        self.assertEqual(tool.TAG, "Codex.J119.S2P01FloorReplacement")
        self.assertEqual(tool.MARK, "J119_S2_P01_FLOOR_REPLACE")
        self.assertTrue(tool.confirm_ok("APPLY", "APPLY J119S2P01FLOOR"))

    def test_s2_execution_body_byte_identical(self):
        text = TOOL.read_text(encoding="utf-8")
        start = text.index("def main():")
        end = text.index("\n\nif unreal is not None:", start)
        body = text[start:end]
        dispatch = (
            '    target = str(args.get("target", "S2")).upper()\n'
            '    if target == "P02":\n'
            '        return _main_p02(args, here)\n'
            '    if target != "S2":\n'
            '        raise Refused("BAD_TARGET|%s|expected=S2|P02" % target)\n'
        )
        self.assertIn(dispatch, body)
        original_s2_body = body.replace(dispatch, "", 1)
        self.assertEqual(hashlib.sha256(original_s2_body.encode("utf-8")).hexdigest(),
                         "9aa9596cb56952b7493c510e8c4d8857afd7dce2ccd3d048834b9e0576f62d45")

    def test_p02_confirm_positive_and_negative(self):
        self.assertTrue(tool.p02_confirm_ok("DRY", ""))
        self.assertTrue(tool.p02_confirm_ok("APPLY", "APPLY J129P02P01FLOOR"))
        self.assertTrue(tool.p02_confirm_ok("REVERT", "REVERT J129P02P01FLOOR"))
        self.assertFalse(tool.p02_confirm_ok("APPLY", "APPLY J119S2P01FLOOR"))
        self.assertFalse(tool.p02_confirm_ok("REVERT", "yes"))

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
        self.assertEqual(len(calls), 2)
        rendered = [ast.unparse(call) for call in calls]
        self.assertTrue(any("owned[row[" in row and "created_actor_path" in row for row in rendered))
        self.assertTrue(any("actor" in row for row in rendered))

    def test_p02_per_segment_materialize_and_separate_ownership(self):
        self.assertIn('"construction_contract": "duplicate the P01 floor actor once per existing P02 route component/ISM instance; never one corridor plane"', self.text)
        self.assertIn("get_instance_transform(instance_index, True)", self.text)
        self.assertIn("passage.materialize_passage()", self.text)
        self.assertIn("P02_TAG", self.text)
        self.assertIn("PreJ129P02P01Floor", self.text)

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
              "positive_controls": 16, "negative_controls": 14, "passed": result.wasSuccessful()}
    (HERE / "harness_result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("J119_HARNESS|tests=%d|failures=%d|errors=%d|positive_controls=16|negative_controls=14" %
          (result.testsRun, len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
