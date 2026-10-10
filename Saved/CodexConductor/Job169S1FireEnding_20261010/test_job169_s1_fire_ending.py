"""Offline positive and negative harness for Job 169."""
import importlib.util
import json
import math
import os
import tempfile
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(HERE, "job169_s1_fire_ending.py")
SPEC = importlib.util.spec_from_file_location("job169_under_test", MODULE_PATH)
J = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(J)


def args():
    with open(os.path.join(HERE, "job169_args.json"), "r", encoding="utf-8") as handle:
        return json.load(handle)


class TimingPositive(unittest.TestCase):
    def test_reviewed_timeline(self):
        plan = J.timing_plan(args())
        self.assertEqual(plan["camera_pan"], [3559, 3634])
        self.assertEqual(plan["fire_window"], [3570, 3900])
        self.assertEqual(plan["fire_ramp"], [3570, 3590])
        self.assertEqual(plan["lights_out"], [3800, 3838])
        self.assertEqual(plan["new_end"], 3900)

    def test_pan_is_three_seconds(self):
        plan = J.timing_plan(args())
        self.assertAlmostEqual((plan["camera_pan"][1] - plan["camera_pan"][0]) / plan["fps"], 3.0)

    def test_start_is_exact_klara_frame(self):
        self.assertAlmostEqual(J.source_frame_for_scene(3559), 3666.0)

    def test_start_is_nearest_safe_frame_to_3560(self):
        self.assertLessEqual(abs(3559 - 3560), 1)
        self.assertNotEqual(J.source_frame_for_scene(3560), round(J.source_frame_for_scene(3560)))

    def test_fire_remains_after_lights_out(self):
        plan = J.timing_plan(args())
        self.assertLess(plan["lights_out"][1], plan["fire_window"][1])

    def test_args_green(self):
        self.assertEqual(J.validate_args(args()), [])

    def test_look_rotation_forward(self):
        self.assertEqual(J.look_rotation([0, 0, 0], [100, 0, 0]), [0.0, 0.0, 0.0])

    def test_look_rotation_corner(self):
        roll, pitch, yaw = J.look_rotation([0, 0, 0], [100, 100, 100])
        self.assertAlmostEqual(roll, 0.0); self.assertAlmostEqual(yaw, 45.0)
        self.assertAlmostEqual(pitch, math.degrees(math.atan2(100, math.sqrt(20000))))

    def test_framing_round_trip(self):
        focal = J.target_focal_mm(2200.0, 800.0, 13.365, 0.4, [1.0, 200.0])
        self.assertAlmostEqual(J.projected_fraction(2200.0, 800.0, 13.365, focal), 0.4)

    def test_review_digest_ignores_mode_and_run(self):
        base = {"plan": {}, "layout_authority": {}, "wing": {}, "source_camera": {},
                "before_digest": "a", "guards": {}, "mode": "DRY", "run": "dry"}
        other = dict(base, mode="APPLY", run="apply")
        self.assertEqual(J.review_digest(base), J.review_digest(other))

    def test_retry_artifact_path_preserves_prior_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            first = os.path.join(root, "artifact")
            os.mkdir(first)
            self.assertEqual(J.unique_artifact_path(first), first + "-attempt2")
            os.mkdir(first + "-attempt2")
            self.assertEqual(J.unique_artifact_path(first), first + "-attempt3")


class NegativeControls(unittest.TestCase):
    def test_bad_confirmation_refused(self):
        value = args(); value["confirm"] = "APPLY JOB169"
        self.assertIn("CONFIRM_MISMATCH", J.validate_args(value))

    def test_wrong_asset_authority_refused(self):
        value = args(); value["klara_level"] = "/Game/Other/L_Animals"
        self.assertIn("ASSET_AUTHORITY_MISMATCH", J.validate_args(value))

    def test_unreviewed_fire_refused(self):
        value = args(); value["fire_system"] = "/Game/Other/NS_Fire"
        self.assertIn("FIRE_SYSTEM_MISMATCH", J.validate_args(value))

    def test_fractional_source_start_refused(self):
        value = args(); value["camera_start_frame"] = 3560
        self.assertIn("CAMERA_START_NOT_EXACT_SOURCE_FRAME", J.validate_args(value))

    def test_nonnegative_tail_bias_refused(self):
        value = args(); value["camera_hierarchical_bias"] = 0
        self.assertIn("TAIL_BIAS_MUST_BE_NEGATIVE", J.validate_args(value))

    def test_fire_outside_pan_refused(self):
        value = args(); value["fire_start_frame"] = 3700
        self.assertIn("FIRE_NOT_DURING_PAN", J.validate_args(value))

    def test_oversize_fire_refused(self):
        value = args(); value["fire_scale"] = 1.0
        self.assertIn("FIRE_NOT_SMALL", J.validate_args(value))

    def test_impossible_geometry_refused(self):
        with self.assertRaises(ValueError):
            J.target_focal_mm(0.0, 100.0, 13.365, 0.4, [18.0, 70.0])


class SourceContract(unittest.TestCase):
    def source(self, name):
        return open(os.path.join(HERE, name), "r", encoding="utf-8").read()

    def test_no_animal_scale_fade(self):
        source = self.source("job169_s1_fire_ending.py")
        self.assertNotIn("JOB168 Animal Scale Fade", source)
        self.assertNotIn("animal_fade", source)
        self.assertNotIn("Pig_anim_RM", source)

    def test_camera_precedence_contract(self):
        source = self.source("job169_s1_fire_ending.py")
        self.assertIn('tail_params.set_editor_property("hierarchical_bias"', source)
        self.assertIn("tail.set_sequence(unreal.load_asset(KLARA))", source)
        self.assertIn("owned_cut.set_camera_binding_id(seq.get_binding_id(camera))", source)

    def test_visibility_binding_contract(self):
        source = self.source("job169_s1_fire_ending.py")
        self.assertIn('set_property_name_and_path("bHidden", "bHidden")', source)
        self.assertNotIn('set_property_name_and_path("bHiddenInGame"', source)
        self.assertIn("True means shown", source)

    def test_klara_never_saved(self):
        source = self.source("job169_s1_fire_ending.py")
        save_calls = [line for line in source.splitlines() if "save_asset(" in line]
        self.assertEqual(len(save_calls), 2)
        self.assertTrue(all("SCENE" in line for line in save_calls))
        self.assertIn("KLARA_ASSET_OR_LEVEL_CHANGED", source)

    def test_level_never_saved(self):
        source = self.source("job169_s1_fire_ending.py")
        self.assertNotIn("save_current_level", source)
        self.assertNotIn("save_map", source)
        self.assertIn('"maps": []', source)

    def test_all_mutating_stages_have_revert(self):
        self.assertIn('"REVERT": run_revert', self.source("job169_s1_fire_ending.py"))
        self.assertIn('"REVERT": namespace["run_revert"]', self.source("job169_stage_lights_out.py"))
        self.assertIn('"REVERT": namespace["run_revert"]', self.source("job169_stage_shrink.py"))

    def test_validator_checks_spawnables_and_bias(self):
        source = self.source("job169_validate.py")
        self.assertIn("OWNED_SPAWNABLES", source)
        self.assertIn("camera_hierarchical_bias", source)
        self.assertIn("HIDDEN_OUTSIDE_WINDOW", source)

    def test_ue58_interpolation_and_component_binding_contract(self):
        source = self.source("job169_s1_fire_ending.py")
        self.assertNotIn("MovieSceneKeyInterpolation.CUBIC", source)
        self.assertIn("MovieSceneKeyInterpolation.AUTO", source)
        self.assertIn("parent.get_child_possessables()", source)
        self.assertIn("unique_artifact_path", source)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    assertions = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    failed = len(result.failures) + len(result.errors)
    print("JOB169_HARNESS|tests=%d|passed=%d|failed=%d|controls=positive+negative+source" %
          (assertions, assertions - failed, failed))
    raise SystemExit(0 if result.wasSuccessful() else 1)
