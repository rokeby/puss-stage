"""Offline +/- harness for Job 98.  No Unreal import, editor, Blender or network."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("s5gt", os.path.join(HERE, "s5_girder_texture.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


class Harness(unittest.TestCase):
    def test_positive_default_dry(self):
        self.assertEqual(S.validate_args({})["mode"], "DRY")

    def test_positive_apply_confirm(self):
        self.assertEqual(S.validate_args({"mode": "apply", "confirm": "APPLY S5GIRDERTEXTURE"})["mode"], "APPLY")

    def test_positive_revert_confirm(self):
        self.assertEqual(S.validate_args({"mode": "REVERT", "confirm": "REVERT S5GIRDERTEXTURE"})["mode"], "REVERT")

    def test_negative_mode(self):
        with self.assertRaisesRegex(S.ToolError, "MODE"):
            S.validate_args({"mode": "RUN"})

    def test_negative_apply_confirm(self):
        with self.assertRaisesRegex(S.ToolError, "CONFIRM"):
            S.validate_args({"mode": "APPLY", "confirm": "YES"})

    def test_negative_revert_confirm(self):
        with self.assertRaisesRegex(S.ToolError, "CONFIRM"):
            S.validate_args({"mode": "REVERT"})

    def test_positive_look_defaults(self):
        args = S.validate_args({})
        self.assertEqual(args["rig_scalars"]["ChipAmount"], 1.0)
        self.assertEqual(args["vectors"]["RustColor"], [0.22, 0.075, 0.025])

    def test_negative_look_range(self):
        bad = dict(S.RIG_SCALARS); bad["GrimeAmount"] = 2.0
        with self.assertRaisesRegex(S.ToolError, "RANGE"):
            S.validate_args({"rig_scalars": bad})

    def test_positive_exact_selector(self):
        labels = ["S5 Hangar Lattice Beam 01", "S5 Hangar Lattice Rail 2", "S5 Hangar Roof"]
        self.assertEqual(S.select_hangar_labels(labels), labels[:2])

    def test_negative_selector_excludes_near_matches(self):
        labels = ["S5 Hangar Lattice Beam 1", "S5 Hangar Lattice Rail A", "S4 Hangar Lattice Beam 01",
                  "S5 Hangar Lattice Beam 01 TEMP", "S5 Hangar Left Wall"]
        self.assertEqual(S.select_hangar_labels(labels), [])

    def test_positive_selection_counts(self):
        chosen, kinds, problems = S.selection_problems(
            ["S5 Hangar Lattice Beam 01", "S5 Hangar Lattice Beam 02", "S5 Hangar Lattice Rail 1"])
        self.assertEqual((len(chosen), kinds, problems), (3, {"beam": 2, "rail": 1}, []))

    def test_negative_selection_needs_beam(self):
        self.assertIn("no S5 lattice beams", S.selection_problems(["S5 Hangar Lattice Rail 1"])[2])

    def test_negative_selection_needs_rail(self):
        self.assertIn("no S5 lattice rails", S.selection_problems(["S5 Hangar Lattice Beam 01"])[2])

    def test_positive_assignment_match(self):
        self.assertEqual(S.assignment_mismatch({"a": "/M"}, {"a": "/M"}), [])

    def test_negative_assignment_drift(self):
        self.assertEqual(S.assignment_mismatch({"a": "/M", "b": "/N"}, {"a": "/X"}), ["a", "b"])

    def test_positive_scalar_tolerance(self):
        self.assertEqual(S.scalar_mismatch({"x": 0.5}, {"x": 0.50005}), [])

    def test_negative_scalar_tolerance(self):
        self.assertEqual(S.scalar_mismatch({"x": 0.5}, {"x": 0.5002}), ["x"])

    def test_positive_dirty_scope(self):
        self.assertEqual(S.dirty_problems([S.MI_RIG, S.MI_HANGAR], [S.WORLD], S.TARGET_MIS), [])

    def test_negative_dirty_content(self):
        self.assertIn("unexpected content", S.dirty_problems(["/Game/Other"], [S.WORLD], S.TARGET_MIS)[0])

    def test_negative_dirty_map(self):
        self.assertIn("dirty maps", S.dirty_problems([], ["/Game/OtherMap"], [], S.WORLD)[0])

    def test_scope_has_three_structure_fields(self):
        self.assertEqual(len(S.STRUCT_FIELDS), 3)

    def test_scope_does_not_name_fog_or_light(self):
        scope = " ".join(".".join(x) for x in S.STRUCT_FIELDS).lower()
        self.assertNotIn("fog", scope)
        self.assertNotIn("light", scope)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Harness)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("S5_GIRDER_TEXTURE_HARNESS_%s|tests=%d|failures=%d|errors=%d" %
          ("PASS" if result.wasSuccessful() else "FAIL", result.testsRun, len(result.failures), len(result.errors)))
    sys.exit(0 if result.wasSuccessful() else 1)
