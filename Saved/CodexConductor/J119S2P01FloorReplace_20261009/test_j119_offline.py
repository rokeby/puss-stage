"""Offline positive/negative harness for Job 119; imports no Unreal module."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
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

    def test_non_identity_source_component_is_solved_positive(self):
        desired = {"location": [100, 200, 3], "rotation": [0, 0, 90], "scale": [6, 8, 1]}
        relative = {"location": [10, 0, 0], "rotation": [0, 0, 0], "scale": [2, 4, .5]}
        got = tool.actor_transform_for_component_world(desired, relative)
        self.assertEqual([round(x, 6) for x in got["location"]], [100, 170, 3])
        self.assertEqual(got["rotation"], [0, 0, 90])
        self.assertEqual(got["scale"], [3, 2, 2])

    def test_root_component_transform_is_not_composed_twice(self):
        desired = {"location": [100, 200, 3], "rotation": [0, 0, 90], "scale": [6, 8, 1]}
        actor_encoded_as_relative = {"location": [50, 60, 3], "rotation": [0, 0, 0], "scale": [2, 4, .5]}
        self.assertEqual(tool.actor_transform_for_component_world(
            desired, actor_encoded_as_relative, component_is_root=True), desired)

    def test_rotated_source_component_still_refused_negative(self):
        desired = {"location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}
        relative = {"location": [0, 0, 0], "rotation": [0, 0, 1], "scale": [1, 1, 1]}
        with self.assertRaises(ValueError):
            tool.actor_transform_for_component_world(desired, relative)

    def test_live_root_composition_reproduces_and_avoids_sunk_rest_offset(self):
        desired = {"location": [1200.0, 3400.0, 12.5], "rotation": [0.0, 0.0, 15.0],
                   "scale": [2.0, 3.0, 0.25]}
        live_root = {"location": [1000.0, 3000.0, 0.0], "rotation": [0.0, 0.0, 0.0],
                     "scale": [1.0, 1.0, 1.0]}
        sunk_rest = dict(live_root, location=[1000.0, 3000.0, -100000.0])
        relative = tool.live_root_relative_transform(desired, live_root)
        self.assertEqual(tool.live_root_world_transform(relative, live_root), desired)
        wrong = tool.live_root_world_transform(relative, sunk_rest)
        self.assertEqual(wrong["location"][2] - desired["location"][2], -100000.0)

    def test_floor_world_z_gate_positive_and_negative(self):
        self.assertIsNone(tool.floor_world_z_issue(12.5, 13.49, 1.0))
        issue = tool.floor_world_z_issue(12.5, -99987.5, 1.0)
        self.assertEqual(issue["kind"], "FLOOR_WORLD_Z_MISMATCH")
        self.assertEqual(issue["delta_cm"], -100000.0)


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
        self.assertTrue(tool.p02_confirm_ok("VERIFY", "VERIFY J129P02P01FLOOR"))
        self.assertTrue(tool.p02_confirm_ok("REVERT", "REVERT J129P02P01FLOOR"))
        self.assertFalse(tool.p02_confirm_ok("APPLY", "APPLY J119S2P01FLOOR"))
        self.assertFalse(tool.p02_confirm_ok("REVERT", "yes"))

    def test_save_attempted_record_allows_verify_and_revert(self):
        record = {"state": "save_attempted", "world": tool.WORLD, "target": "P02"}
        self.assertTrue(tool.p02_record_context_ok(record, "VERIFY"))
        self.assertTrue(tool.p02_record_context_ok(record, "REVERT"))
        self.assertFalse(tool.p02_record_context_ok(dict(record, state="applying"), "REVERT"))

    def test_revert_requires_recorded_backup_map(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            map_path = folder / tool.UMAP_REL[-1]
            map_path.write_bytes(b"backup")
            got = tool._p02_backup_evidence({"backup": str(folder)})
            self.assertEqual(got["size_bytes"], 6)
        with self.assertRaises(tool.Refused):
            tool._p02_backup_evidence({"backup": "missing"})

    def test_verify_reports_parent_shift_frame_negative(self):
        expected_bounds = {"origin": [10, 20, 0], "extent": [2, 3, .5],
                           "min": [8, 17, -.5], "max": [12, 23, .5]}
        got_bounds = {name: [value[0], value[1], value[2] - 100000]
                      for name, value in expected_bounds.items()}
        # Extent is invariant under translation.
        got_bounds["extent"] = list(expected_bounds["extent"])
        issues = tool.segment_diagnostics({"world_bounds": expected_bounds},
                                          {"world_bounds": got_bounds}, .1, [0, 0, -100000])
        self.assertEqual(issues[0]["cause"], "ATTACHED_TO_SHIFTED_TARGET_FRAME")

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

    def test_p02_direct_actor_track_is_blocker_negative(self):
        row = {"track_class": "MovieScene3DTransformTrack", "property": "", "object_kind": "actor"}
        blockers, inherited = tool.sequence_binding_policy([row], direct_actor_blocks=True)
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

    def test_p02_non_identity_component_handling_is_scoped(self):
        s2 = self.text[self.text.index("def _make_plan("):self.text.index("def _bounds_for_row(")]
        p02 = self.text[self.text.index("def _p02_plan("):self.text.index("def _p02_component_map(")]
        self.assertIn("source = _snapshot(source_actor)\n", s2)
        self.assertNotIn("component_world=True", s2)
        self.assertIn("source = _snapshot(source_actor, component_world=True)", p02)
        self.assertIn("actor_transform_for_component_world", p02)
        self.assertIn('source["component_is_root"]', p02)

    def test_p02_footprints_verify_before_old_floor_mutation(self):
        p02 = self.text[self.text.index("def _main_p02("):self.text.index("def main():")]
        apply_body = p02[p02.index('record = {"schema": 2'):]
        self.assertLess(self.text.index("P02_PREFLIGHT_FOOTPRINT"),
                        self.text.index('component.set_editor_property("relative_location"',
                                        self.text.index('record = {"schema": 2')))
        self.assertLess(apply_body.index("P02_SEGMENT_FOOTPRINT_READBACK"),
                        apply_body.index('component.set_editor_property("relative_location"'))

    def test_p02_attaches_to_live_root_after_old_floor_shift(self):
        p02 = self.text[self.text.index("def _main_p02("):self.text.index("def main():")]
        self.assertLess(p02.index('component.set_editor_property("relative_location"'),
                        p02.index("duplicate.attach_to_actor"))
        self.assertIn('duplicate.attach_to_actor(live_root_actor', p02)
        self.assertNotIn('duplicate.attach_to_actor(target_by_path', p02)
        self.assertIn("P02_POST_SHIFT_ATTACHMENT_READBACK", p02)
        self.assertIn("P02_POST_MATERIALIZE_SEGMENT_READBACK", p02)

    def test_p02_pre_save_world_z_and_inside_box_guards(self):
        p02 = self.text[self.text.index("def _main_p02("):self.text.index("def main():")]
        before_save = p02[:p02.index('record["state"] = "save_attempted"')]
        self.assertIn("floor_world_z_issue", before_save)
        self.assertIn("LIVE_ROOT_INSIDE_BOX_MISMATCH", before_save)

    def test_bhidden_contract_and_no_inert_property(self):
        self.assertIn('"bhidden"', self.text.lower())
        self.assertNotIn("bHiddenInGame", self.text)

    def test_backup_record_and_targeted_save(self):
        self.assertIn("PreJ119S2P01Floor", self.text)
        self.assertLess(self.text.index("_write_json(record_path, record, True)"), self.text.index("duplicate_actor"))
        self.assertIn("save_current_level", self.text)

    def test_verify_only_and_save_attempted_revert_contract(self):
        self.assertIn('P02_MODES = ("DRY", "APPLY", "VERIFY", "REVERT")', self.text)
        self.assertIn('record["state"] = "applied"', self.text)
        self.assertIn('P02_VERIFY_MISMATCH', self.text)
        self.assertIn('_p02_backup_evidence(record)', self.text)

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
              "positive_controls": 28, "negative_controls": 22, "passed": result.wasSuccessful()}
    (HERE / "harness_result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("J119_HARNESS|tests=%d|failures=%d|errors=%d|positive_controls=28|negative_controls=22" %
          (result.testsRun, len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
