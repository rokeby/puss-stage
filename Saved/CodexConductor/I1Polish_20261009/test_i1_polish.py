import importlib.util
import json
import math
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("i1_polish_tested", os.path.join(HERE, "i1_polish.py"))
TOOL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TOOL)


class FakeBackend(object):
    def __init__(self, root):
        self.root, self.messages = root, []

    def preflight(self, mode, run, confirm):
        if confirm != TOOL.CONFIRMS[mode]:
            raise TOOL.Stop("CONFIRM")

    def census(self):
        return {"content": [], "maps": []}

    def log(self, value):
        self.messages.append(value)

    def fail(self, value):
        raise TOOL.Stop(value)

    def build_report(self, params, run):
        guarded = {"params": params, "state": "fixture"}
        return {"run": run, "params": params, "apply_ready": True, "refusals": [],
                "camera_fit": {"distance_cm": 2850.0}, "f17": {},
                "f18": {"inventory": [1], "selected": [1]}, "input_digest": TOOL.digest(guarded)}

    def apply(self, report, run):
        return {"camera_fit": [1] * 6, "f17": [], "f18": [1], "backup": "B"}

    def revert(self, run):
        return {"backup": "BR", "archived_record": "R"}


class Job90Tests(unittest.TestCase):
    def test_positive_enum_normalises_angle_repr(self):
        self.assertEqual("RCIM_LINEAR", TOOL.enum_token("<RichCurveInterpMode.RCIM_LINEAR: 1>"))

    def test_positive_enum_normalises_plain_repr(self):
        self.assertEqual("LINEAR", TOOL.enum_token("MovieSceneKeyInterpolation.LINEAR"))

    def test_positive_channel_numeric_suffix(self):
        self.assertEqual("Location.Z", TOOL.channel_base("Location.Z_0"))

    def test_positive_channel_type_suffix(self):
        self.assertEqual("Rotation.Y", TOOL.channel_base("Rotation.Y (Double)"))

    def test_positive_fit_horizontal_governs_i1(self):
        got = TOOL.fit_distance([1880.0, 1000.0], 35.0, [23.76, 13.365], 1.03)
        self.assertAlmostEqual(2852.4410774410776, got)

    def test_positive_fit_centres_and_pulls_back(self):
        got = TOOL.fitted_camera({"loc": [-1200, 80000, 510], "yaw": 0}, 1200, 2850, 10)
        self.assertEqual([-2850.0, 80000.0, 520.0], got["after"]["loc"])
        self.assertEqual([-1650.0, 0.0, 10.0], got["delta"])

    def test_positive_fit_rotates_behind_drape(self):
        got = TOOL.fitted_camera({"loc": [100, 200, 500], "yaw": 90}, 500, 1500, 0)
        self.assertAlmostEqual(100.0, got["after"]["loc"][0], places=6)
        self.assertAlmostEqual(-800.0, got["after"]["loc"][1], places=6)

    def test_positive_hold_removes_terminal_ramp(self):
        got = TOOL.hold_plan([[0, 0.0], [1675, 2.0], [2182, -5.0]], 1675, 2183)
        self.assertTrue(got["changed"])
        self.assertEqual([[0, 0.0], [1675, 2.0], [2182, 2.0]], got["after"])

    def test_positive_defaults_do_not_enable_look_fix(self):
        self.assertEqual([], TOOL.merged_params({})["f17_fix_steps"])

    def test_positive_visibility_bool_accepted(self):
        got = TOOL.BASE.validate_fix_steps([{"id": "x", "kind": "ACTOR_HIDE", "actor_label": "A",
                                             "keys": [[1249, True], [1250, False]]}], TOOL.EXPECTED_END)
        self.assertEqual(2, len(got[0]["keys"]))

    def test_positive_guid_converter_stable(self):
        class Bad(object):
            def __str__(self):
                return "Struct address 0x123"
        self.assertEqual("AABBCCDD", TOOL.BASE._guid(Bad(), lambda _: "{aa-bb-cc-dd}"))

    def test_positive_main_dry_writes_plan(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend(root)
            TOOL.main({"mode": "DRY", "run_id": "T", "confirm": "DRY I1POLISH"}, backend=backend)
            self.assertTrue(os.path.isfile(os.path.join(root, TOOL.PLAN)))
            self.assertIn("I1_POLISH_DRY_OK", backend.messages[-1])

    def test_positive_main_apply_checks_matching_dry(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend(root)
            args = {"mode": "DRY", "run_id": "D", "confirm": "DRY I1POLISH"}
            TOOL.main(args, backend=backend)
            args.update({"mode": "APPLY", "run_id": "A", "confirm": "APPLY I1POLISH"})
            got = TOOL.main(args, backend=backend)
            self.assertEqual(6, len(got["camera_fit"]))

    def test_positive_main_revert(self):
        with tempfile.TemporaryDirectory() as root:
            got = TOOL.main({"mode": "REVERT", "run_id": "R", "confirm": "REVERT I1POLISH"},
                            backend=FakeBackend(root))
            self.assertEqual("R", got["archived_record"])

    def test_positive_job89_timing_is_out_of_scope(self):
        source = open(os.path.join(HERE, "i1_polish.py"), "r", encoding="utf-8").read()
        for forbidden in ("set_playback_end(", "set_start_frame(", "set_end_frame(",
                          "add_marked_frame(", "delete_marked_frame("):
            self.assertNotIn(forbidden, source)

    def test_negative_bad_bounds(self):
        with self.assertRaisesRegex(TOOL.PlanError, "CURTAIN_BOUNDS_INVALID"):
            TOOL.merged_params({"curtain_bounds_cm": [0, 1000]})

    def test_negative_bad_margin_low(self):
        with self.assertRaisesRegex(TOOL.PlanError, "CAMERA_MARGIN"):
            TOOL.merged_params({"camera_fit_margin": 0.9})

    def test_negative_bad_margin_high(self):
        with self.assertRaisesRegex(TOOL.PlanError, "CAMERA_MARGIN"):
            TOOL.merged_params({"camera_fit_margin": 1.5})

    def test_negative_hold_outside_playback(self):
        with self.assertRaisesRegex(TOOL.PlanError, "F18_HOLD"):
            TOOL.merged_params({"f18_hold_frame": 2183})

    def test_negative_visibility_float_refused(self):
        with self.assertRaises(TOOL.BASE.PlanError):
            TOOL.BASE.validate_fix_steps([{"id": "x", "kind": "ACTOR_HIDE", "actor_label": "A",
                                           "keys": [[1250, 0.0]]}], TOOL.EXPECTED_END)

    def test_negative_fix_outside_i1_refused(self):
        with self.assertRaises(TOOL.BASE.PlanError):
            TOOL.BASE.validate_fix_steps([{"id": "x", "kind": "LIGHT_DIM", "actor_label": "A",
                                           "keys": [[2184, 0.0]]}], TOOL.EXPECTED_END)

    def test_negative_wrong_confirm(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(TOOL.Stop):
                TOOL.main({"mode": "DRY", "run_id": "T", "confirm": "yes"}, backend=FakeBackend(root))

    def test_negative_apply_args_drift(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend(root)
            TOOL.main({"mode": "DRY", "run_id": "D", "confirm": "DRY I1POLISH"}, backend=backend)
            with self.assertRaisesRegex(TOOL.Stop, "DRY_ARGS_DRIFT"):
                TOOL.main({"mode": "APPLY", "run_id": "A", "confirm": "APPLY I1POLISH",
                           "params": {"camera_fit_margin": 1.04}}, backend=backend)

    def test_negative_unknown_mode(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(TOOL.Stop):
                TOOL.main({"mode": "FIX", "run_id": "T"}, backend=FakeBackend(root))


class CountingResult(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self._active = test._testMethodName

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed = getattr(self, "passed", []) + [self._active]


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Job90Tests)
    runner = unittest.TextTestRunner(verbosity=2, resultclass=CountingResult)
    result = runner.run(suite)
    passed = getattr(result, "passed", [])
    positive = [x for x in passed if x.startswith("test_positive_")]
    negative = [x for x in passed if x.startswith("test_negative_")]
    payload = {"total": suite.countTestCases(), "passed": len(passed), "failed": len(result.failures),
               "errors": len(result.errors), "positive_passed": sorted(positive),
               "negative_passed": sorted(negative)}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("HARNESS_RESULT|positive=%d/15|negative=%d/9|total=%d/24" %
          (len(positive), len(negative), len(passed)))
    print("HARNESS_STATUS|%s" % ("PASS" if result.wasSuccessful() and len(positive) == 15 and len(negative) == 9 else "FAIL"))
    raise SystemExit(0 if result.wasSuccessful() else 1)
