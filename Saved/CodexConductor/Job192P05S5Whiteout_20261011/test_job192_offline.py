import json
import os
import unittest

import job192_core as core


HERE = os.path.dirname(os.path.abspath(__file__))


class Job192OfflineTests(unittest.TestCase):
    def score(self):
        with open(os.path.join(HERE, "whiteout_score.json"), encoding="utf-8") as handle:
            return core.compile_score(json.load(handle))

    def test_positive_plan_hits_white_at_seam_and_releases(self):
        score = self.score()
        keys = core.key_plan(score, 24000, 1000)
        self.assertIn([24000, 1.0], keys)
        self.assertEqual(keys[-1], [25800, 0.0])
        self.assertEqual(0.95, score["threshold"])

    def test_negative_score_rejects_subwhite_seam(self):
        raw = {"schema": 1, "seam_mean_luminance_threshold": 0.95,
               "fade_from_white_seconds": 1.0,
               "whiteout_keys": [{"seconds_from_seam": -1, "amount": 0},
                                 {"seconds_from_seam": 0, "amount": 0.94},
                                 {"seconds_from_seam": 1, "amount": 0}]}
        with self.assertRaisesRegex(ValueError, "seam"):
            core.compile_score(raw)

    def test_negative_apply_needs_exact_confirmation_and_decider(self):
        with self.assertRaisesRegex(ValueError, "exact confirm"):
            core.validate_args({"mode": "APPLY", "run": "J192-ABC", "confirm": "yes"})
        with self.assertRaisesRegex(ValueError, "decided_by"):
            core.validate_args({"mode": "APPLY", "run": "J192-ABC",
                                "confirm": core.CONFIRM["APPLY"]})

    def test_negative_revert_needs_record(self):
        with self.assertRaisesRegex(ValueError, "record"):
            core.validate_args({"mode": "REVERT", "run": "J192-ABC",
                                "confirm": core.CONFIRM["REVERT"], "decided_by": "Gary"})

    def test_negative_quantized_duplicate_rejected(self):
        score = {"rows": [{"seconds_from_seam": -0.01, "amount": 0},
                          {"seconds_from_seam": 0, "amount": 1},
                          {"seconds_from_seam": 0.01, "amount": 0}]}
        with self.assertRaisesRegex(ValueError, "quantizes"):
            core.key_plan(score, 10, 1)

    def test_positive_live_tool_has_narrow_save_and_markers(self):
        with open(os.path.join(HERE, "job192_p05_s5_whiteout.py"), encoding="utf-8") as handle:
            text = handle.read()
        for token in ("JOB192_DRY_OK", "JOB192_APPLY_OK", "JOB192_REVERT_OK",
                      '"save_packages": [ctx["master_path"], WORLD]', "save_current_level()",
                      'MASTER = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"'):
            self.assertIn(token, text)
        self.assertIn('get_editor_property("master_sequence")', text)
        self.assertNotIn('show, master = unreal.load_asset(SHOW), unreal.load_asset(MASTER)', text)
        self.assertIn('missing_settings_policy', text)
        self.assertNotIn('CUE_DIRECTOR_MISSING_CANNOT_DETERMINE_S5_MODE', text)
        self.assertNotIn("save_asset(SHOW", text)
        self.assertNotIn("save_asset(S5", text)
        self.assertNotIn("delete_asset", text)

    def test_positive_mcp_request_uses_call_tool_envelope(self):
        with open(os.path.join(HERE, "job192_request.json"), encoding="utf-8") as handle:
            request = json.load(handle)
        self.assertEqual("call_tool", request.get("name"))
        self.assertEqual(
            "CodexConductor/Job192P05S5Whiteout_20261011/job192_run.py",
            request.get("arguments", {}).get("arguments", {}).get("relativeSavedPath"))

    def test_positive_held_patch_has_capability_and_timed_alpha(self):
        patch = os.path.abspath(os.path.join(HERE, "..", "..", "..", "Scripts", "patches",
                                              "2026-10-11_job192_s5_fade_from_white.patch"))
        with open(patch, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("InfinityStage.VideoFallback.WhiteFadeSchema", text)
        self.assertIn("fade_from_white_seconds", text)
        self.assertIn("1.0 - Wanted / Duration", text)


if __name__ == "__main__":
    unittest.main()
