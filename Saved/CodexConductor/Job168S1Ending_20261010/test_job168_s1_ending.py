"""Offline positive and negative harness for Job 168."""
import importlib.util
import json
import os
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(HERE, "job168_s1_ending.py")
SPEC = importlib.util.spec_from_file_location("job168_under_test", MODULE_PATH)
J = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(J)


def args():
    return json.load(open(os.path.join(HERE, "job168_args.json"), "r", encoding="utf-8"))


class TimingPositive(unittest.TestCase):
    def test_reviewed_timeline(self):
        p = J.timing_plan(args())
        self.assertEqual(p["animal_fade"], [3525, 3600])
        self.assertEqual(p["lights_out"], [3800, 3838])
        self.assertEqual(p["exit_handoff"], [3875, 3900])
        self.assertEqual(p["new_end"], 3900)

    def test_exact_three_seconds(self):
        p = J.timing_plan(args())
        self.assertEqual(p["animal_fade"][1] - p["animal_fade"][0], 75)
        self.assertAlmostEqual(75 / p["fps"], 3.0)

    def test_klara_exit_maps_just_before_3600(self):
        # The captured exit transforms finish at her frames 3500/3501/3513.
        mapped = [J.source_to_scene_frame(frame) for frame in (3500, 3501, 3513)]
        self.assertTrue(all(3400.0 < value < 3450.0 for value in mapped))
        self.assertTrue(max(mapped) < 3600.0)

    def test_handoff_cut_maps_to_source_4046(self):
        exact = J.scene_to_source_frame(3875)
        self.assertAlmostEqual(exact, 4045.2)
        self.assertEqual(__import__("math").ceil(exact), 4046)

    def test_args_green(self):
        self.assertEqual(J.validate_args(args()), [])

    def test_review_digest_ignores_mode_and_run(self):
        base = {"plan": {}, "animal_author": {}, "material_audit": {}, "before_digest": "a",
                "klara_guard": {}, "exit_cut_before": {}, "klara_content_past_new_wrapper_end": {},
                "run": "dry", "mode": "DRY"}
        other = dict(base, run="apply", mode="APPLY")
        self.assertEqual(J.review_digest(base), J.review_digest(other))
        changed = dict(base, before_digest="b")
        self.assertNotEqual(J.review_digest(base), J.review_digest(changed))

    def test_author_is_klara_transform(self):
        rows = []
        for owner in args()["animal_labels"]:
            rows.append({"owner": owner, "class": "MovieScene3DTransformTrack", "late_additive": True})
        verdict = J.author_verdict(rows)
        self.assertEqual(verdict["authority"], "KLARA_COPY_TRANSFORM")
        self.assertEqual(len(verdict["exit_transforms"]), 3)
        self.assertEqual(verdict["visibility_tracks"], [])


class TimingNegative(unittest.TestCase):
    def test_bad_confirmation_refused(self):
        value = args(); value["confirm"] = "APPLY JOB168"
        self.assertIn("CONFIRM_MISMATCH", J.validate_args(value))

    def test_bad_asset_authority_refused(self):
        value = args(); value["klara_copy"] = "/Game/KK_S1_Animals/LS_Animals_1"
        self.assertIn("ASSET_AUTHORITY_MISMATCH", J.validate_args(value))

    def test_duplicate_animals_refused(self):
        value = args(); value["animal_labels"][2] = value["animal_labels"][0]
        self.assertIn("ANIMAL_LABELS_REQUIRE_THREE_UNIQUE", J.validate_args(value))

    def test_material_strategy_not_silently_changed(self):
        value = args(); value["animal_fade_strategy"] = "MID"
        self.assertIn("UNREVIEWED_FADE_STRATEGY", J.validate_args(value))

    def test_overlapping_lights_refused(self):
        value = args(); value["lights_out_start_frame"] = 3590
        self.assertIn("ANIMAL_LIGHTS_ORDER", J.validate_args(value))

    def test_overlapping_handoff_refused(self):
        value = args(); value["exit_handoff_frames"] = 80
        self.assertIn("LIGHTS_HANDOFF_OVERLAP", J.validate_args(value))

    def test_visibility_makes_author_unclear(self):
        rows = []
        for owner in args()["animal_labels"]:
            rows.append({"owner": owner, "class": "MovieScene3DTransformTrack", "late_additive": True})
        rows.append({"owner": "Pig_anim_RM", "class": "MovieSceneVisibilityTrack", "late_additive": False})
        self.assertEqual(J.author_verdict(rows)["authority"], "UNCLEAR")

    def test_missing_one_exit_makes_author_unclear(self):
        rows = [{"owner": owner, "class": "MovieScene3DTransformTrack", "late_additive": True}
                for owner in args()["animal_labels"][:2]]
        self.assertEqual(J.author_verdict(rows)["authority"], "UNCLEAR")


class SourceContract(unittest.TestCase):
    def source(self, name):
        return open(os.path.join(HERE, name), "r", encoding="utf-8").read()

    def test_visibility_binding_contract(self):
        source = self.source("job168_s1_ending.py")
        self.assertIn('set_property_name_and_path("bHidden", "bHidden")', source)
        self.assertNotIn('set_property_name_and_path("bHiddenInGame"', source)
        self.assertIn("True means visible", source)

    def test_klara_never_saved(self):
        source = self.source("job168_s1_ending.py")
        save_calls = [line for line in source.splitlines() if "save_asset(" in line]
        self.assertEqual(len(save_calls), 2)
        self.assertTrue(all("SCENE" in line for line in save_calls))
        self.assertIn("KLARA_ASSET_CHANGED", source)

    def test_level_never_saved(self):
        source = self.source("job168_s1_ending.py")
        self.assertNotIn("save_current_level", source)
        self.assertNotIn("save_map", source)
        self.assertIn('"maps": []', source)

    def test_scale_is_additive(self):
        source = self.source("job168_s1_ending.py")
        self.assertIn("MovieSceneBlendType.ADDITIVE", source)
        self.assertIn("-1.0", source)
        self.assertIn("RESTORE_STATE", source)

    def test_each_stage_has_revert(self):
        self.assertIn('"REVERT": run_revert', self.source("job168_s1_ending.py"))
        self.assertIn('"REVERT": namespace["run_revert"]', self.source("job168_stage_lights_out.py"))
        self.assertIn('"REVERT": namespace["run_revert"]', self.source("job168_stage_shrink.py"))

    def test_shrink_record_is_job_scoped(self):
        source = self.source("job168_stage_shrink.py")
        self.assertIn('job168_s1_shrink_record.json', source)
        self.assertIn('new_end_frame', source)

    def test_final_validator_checks_three_hangar_bindings(self):
        source = self.source("job168_validate.py")
        for label in ("S1 Hangar Root", "S1 Hangar Roof Hinge", "S1 Hangar Lattice Fly"):
            self.assertIn(label, source)
        self.assertIn("show_master_match", source)
        self.assertIn("KLARA_HASH_CHANGED", source)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    assertions = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("JOB168_HARNESS|tests=%d|passed=%d|failed=%d|controls=positive+negative+source" %
          (assertions, assertions - len(result.failures) - len(result.errors),
           len(result.failures) + len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
