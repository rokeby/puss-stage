import importlib.util
import json
import os
import tempfile
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("i2_polish_under_test", os.path.join(HERE, "i2_polish.py"))
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)


def scene(n=2, tails=1):
    nested = []
    for index in range(tails):
        nested.append({"range": [376, 3891], "active": True, "sequence": "/Game/Nested%d" % index,
                       "final_camera": "Replacement Final Camera %d" % index,
                       "locator": {"track_index": index, "section_index": 0,
                                   "track_class": "MovieSceneCinematicShotTrack",
                                   "sub_sequence": "/Game/Nested%d" % index}})
    return {"scene": n, "sequence": "/Game/Scene%d" % n, "playback": [0, 3891],
            "root_cuts": [{"range": [3866, 3891], "active": True, "camera": "Exit Handoff Camera"}],
            "nested": nested}


def channel(ident="A", interpolation=None):
    return {"id": ident, "binding_guid": "ABC", "binding": "Camera", "track_index": 0,
            "track": "Transform", "section_index": 0, "channel_index": 0,
            "channel": "Location.Z", "keys": [[0, 500.0], [1675, 500.0], [1800, 300.0], [1949, 250.0]],
            "interpolation": interpolation or ["LINEAR"], "sequence": TOOL.I2_PATH}


class FakeBackend(object):
    def __init__(self, root):
        self.root = root
        self.logs = []
        self.applied = False
        self.before_end = 3891

    def log(self, message):
        self.logs.append(message)

    def fail(self, message):
        raise TOOL.Stop(message)

    def census(self):
        return {"content": [], "maps": []}

    def preflight(self, mode, run, confirm):
        if confirm != TOOL.CONFIRMS[mode]:
            raise TOOL.Stop("CONFIRM")

    def build_report(self, params, run):
        boundary = TOOL.boundary_plan(scene(), 1)
        boundary["before_end"] = self.before_end
        boundary["after_end"] = self.before_end + int(params["boundary_extend_frames"])
        boundary["probe"] = {"supports_fix": True}
        guarded = TOOL.plan_relevant_inputs(params, [boundary], [], {"selected": []}, [0, 1950])
        return {"schema_version": 1, "tool_version": TOOL.TOOL_VERSION, "run": run, "params": params,
                "apply_ready": True, "refusals": [],
                "boundary": [boundary],
                "f17": {"status": "OK"}, "f17_fix_steps": [],
                "f18": {"candidates": [], "selected": [], "refusals": []},
                "runon": {"source_guaranteed": True}, "input_digest": TOOL.digest(guarded),
                "digest_inputs": guarded,
                "census": self.census(), "proof": {"tier": "measured"}}

    def apply(self, report, run):
        self.applied = True
        return {"boundary": [1], "f17": [], "f18": [], "packages": ["/Game/Scene2"],
                "backup": "Backups/PreI2Polish-" + run}

    def revert(self, run):
        self.applied = False
        return {"packages": ["/Game/Scene2"], "backup": "Backups/PreI2PolishRevert-" + run,
                "archived_record": "record.reverted"}


class PolishTests(unittest.TestCase):
    def test_positive_clock_centiseconds(self):
        self.assertAlmostEqual(66.09, TOOL.parse_clock("1:06.09"))

    def test_positive_go_explicit_pass(self):
        self.assertEqual("PASS", TOOL.parse_go_marker("GO 20 PASS next cue")["mode"])

    def test_positive_go_defaults_hold(self):
        self.assertEqual("HOLD", TOOL.parse_go_marker("GO 20 next cue")["mode"])

    def test_positive_runon_explicit_pass(self):
        params = TOOL.merged_params({})
        rep = TOOL.runon_report([{"frame": 1652, "label": "GO 20 PASS next cue"}], [], 25, 10000, params)
        self.assertTrue(rep["source_guaranteed"])

    def test_positive_unpausable_demotes_hold(self):
        params = TOOL.merged_params({})
        rep = TOOL.runon_report([{"frame": 1652, "label": "GO 20 HOLD next cue"}], [], 25, 10000, params, True)
        self.assertTrue(rep["source_guaranteed"])

    def test_positive_boundary_one_frame_extension(self):
        plan = TOOL.boundary_plan(scene(), 1)
        self.assertEqual(("READY", 3892), (plan["status"], plan["after_end"]))

    def test_positive_boundary_probe_churn_supports_fix(self):
        probe = {"seams": [{"left": "Scene 2", "right": "Interaction 2"}],
                 "rows": [{"seam_index": 0, "offset": -2, "view_target": "Nested"},
                          {"seam_index": 0, "offset": -1, "view_target": "Exit"},
                          {"seam_index": 0, "offset": 0, "view_target": "I2"}]}
        self.assertTrue(TOOL.boundary_probe_evidence(probe, 2)["supports_fix"])

    def test_positive_hold_key_plan(self):
        plan = TOOL.hold_key_plan(channel()["keys"], 1675, 1950)
        self.assertEqual([[0, 500.0], [1675, 500.0], [1949, 500.0]], plan["after"])
        self.assertTrue(plan["changed"])

    def test_positive_movement_selected(self):
        plan = TOOL.movement_plan([channel()], 1675, 1950, ["A"])
        self.assertEqual(1, len(plan["selected"]))

    def test_positive_fix_visibility_bools(self):
        rows = TOOL.validate_fix_steps([{"id": "hide", "kind": "LIGHT_HIDE", "actor_label": "Lamp",
                                         "keys": [[0, True], [1250, False]]}], 1950)
        self.assertEqual(2, len(rows[0]["keys"]))

    def test_positive_fix_ppv(self):
        rows = TOOL.validate_fix_steps([{"id": "ppv", "kind": "PPV_WEIGHT", "actor_label": "PPV",
                                         "keys": [[0, 0.0], [1950, 0.0]]}], 1950)
        self.assertEqual("PPV_WEIGHT", rows[0]["kind"])

    def test_positive_digest_order_independent(self):
        self.assertEqual(TOOL.digest({"a": 1, "b": 2}), TOOL.digest({"b": 2, "a": 1}))

    def test_positive_guid_uses_value_converter_not_struct_address(self):
        class AddressRepr(object):
            def __init__(self, address):
                self.address = address

            def __str__(self):
                return "<STRUCT 'GUID' (0X%s)>" % self.address

        converter = lambda unused: "12345678-1234-1234-1234-1234567890ab"
        self.assertEqual(TOOL._guid(AddressRepr("AAA"), converter),
                         TOOL._guid(AddressRepr("BBB"), converter))

    def test_positive_logged_boundary_only_ignores_disabled_f17_audit(self):
        # B1H-I2POLISH-BOUNDARY-DRY-20261009-092652: boundary enabled,
        # F17 fixes empty, F18 targets empty, and the F17 audit was unavailable.
        params = TOOL.merged_params({"boundary_scenes": [2], "boundary_apply": True,
                                     "f17_fix_steps": [], "f18_target_ids": []})
        old_refusals = ["F17_AUDIT_UNAVAILABLE|PlanError: F17_CAMERA_TRANSFORM_COUNT|I2 Hangar Hold Camera|0"]
        self.assertFalse(not old_refusals)  # old apply_ready = not refusals
        self.assertEqual([], TOOL.gate_refusals(params, [], [], old_refusals, [],
                                                {"boundary": 1, "f17": 0, "f18": 0}))

    def test_positive_logged_master_i2_custom_track_regression(self):
        # B1E-I2POLISH-DRY-20261009-0858: the rebuilt Master uses the
        # plugin's managed scene track, which the former exact-name filter skipped.
        rows = [{"track_class": "MovieSceneInfinitySceneTrack",
                 "track": "Infinity Stage Scenes", "section_index": 7,
                 "sequence": TOOL.I2_PATH, "active": True,
                 "start": 16929600, "end": 18801600}]
        legacy = ("MovieSceneSubTrack", "MovieSceneCinematicShotTrack")
        with self.assertRaisesRegex(TOOL.PlanError, r"MASTER_I2_SECTION_COUNT\|0"):
            TOOL.master_i2_start_from_rows(rows, track_classes=legacy)
        self.assertEqual(16929600, TOOL.master_i2_start_from_rows(rows))

    def test_positive_main_dry(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend(root)
            TOOL.main({"mode": "DRY", "run_id": "T-DRY", "confirm": "DRY I2POLISH"}, backend=backend)
            self.assertTrue(os.path.isfile(os.path.join(root, TOOL.PLAN)))
            self.assertTrue(any(line.startswith("I2_POLISH_DRY_OK") for line in backend.logs))

    def test_positive_main_dry_apply_allows_only_envelope_changes_then_revert(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend(root)
            TOOL.main({"mode": "DRY", "run_id": "T-DRY", "confirm": "DRY I2POLISH"}, backend=backend)
            TOOL.main({"mode": "APPLY", "run_id": "T-APPLY", "confirm": "APPLY I2POLISH"}, backend=backend)
            TOOL.main({"mode": "REVERT", "run_id": "T-REV", "confirm": "REVERT I2POLISH"}, backend=backend)
            self.assertFalse(backend.applied)

    def test_negative_lowercase_go_is_not_runtime_marker(self):
        self.assertIsNone(TOOL.parse_go_marker("go 20 PASS"))

    def test_negative_runon_missing_go_refused(self):
        rep = TOOL.runon_report([], [], 25, 10000, TOOL.merged_params({}))
        self.assertIn("NO_GO_MARKER_NEAR_TARGET", rep["blockers"])

    def test_negative_runon_hold_refused(self):
        rep = TOOL.runon_report([{"frame": 1652, "label": "GO 20 HOLD"}], [], 25, 10000, TOOL.merged_params({}))
        self.assertIn("TARGET_GO_IS_HOLD", rep["blockers"])

    def test_negative_runon_vamp_refused(self):
        markers = [{"frame": 1600, "label": "InfinityStage.VampStart"},
                   {"frame": 1700, "label": "InfinityStage.VampEnd"},
                   {"frame": 1652, "label": "GO 20 PASS"}]
        rep = TOOL.runon_report(markers, [], 25, 10000, TOOL.merged_params({}))
        self.assertIn("TARGET_INSIDE_VAMP", rep["blockers"])

    def test_negative_boundary_without_nested_is_unclear(self):
        self.assertEqual("NO_TERMINAL_NESTED_CAMERA", TOOL.boundary_plan(scene(tails=0))["status"])

    def test_negative_boundary_ambiguous_refused(self):
        self.assertEqual("AMBIGUOUS_TERMINAL_NESTED", TOOL.boundary_plan(scene(tails=2))["status"])

    def test_negative_boundary_probe_single_transition_not_fix(self):
        probe = {"seams": [{"left": "Scene 2", "right": "Interaction 2"}],
                 "rows": [{"seam_index": 0, "offset": -1, "view_target": "Nested"},
                          {"seam_index": 0, "offset": 0, "view_target": "I2"}]}
        self.assertFalse(TOOL.boundary_probe_evidence(probe, 2)["supports_fix"])

    def test_negative_unknown_movement_target(self):
        rep = TOOL.movement_plan([channel()], 1675, 1950, ["missing"])
        self.assertTrue(rep["refusals"])

    def test_negative_nonlinear_movement_target(self):
        rep = TOOL.movement_plan([channel(interpolation=["RCIM_CUBIC"])], 1675, 1950, ["A"])
        self.assertTrue(rep["refusals"])

    def test_negative_fix_shape(self):
        with self.assertRaises(TOOL.PlanError):
            TOOL.validate_fix_steps([{"id": "bad"}], 1950)

    def test_negative_visibility_float_refused(self):
        with self.assertRaises(TOOL.PlanError):
            TOOL.validate_fix_steps([{"id": "bad", "kind": "LIGHT_HIDE", "actor_label": "Lamp",
                                      "keys": [[0, 0.0]]}], 1950)

    def test_negative_fix_outside_playback_refused(self):
        with self.assertRaises(TOOL.PlanError):
            TOOL.validate_fix_steps([{"id": "bad", "kind": "LIGHT_DIM", "actor_label": "Lamp",
                                      "keys": [[1951, 0.0]]}], 1950)

    def test_negative_enabled_f17_unavailable_still_refused(self):
        params = TOOL.merged_params({"f17_fix_steps": [{"id": "x"}]})
        got = TOOL.gate_refusals(params, [], [], ["F17_AUDIT_UNAVAILABLE|x"], [],
                                 {"boundary": 1, "f17": 1, "f18": 0})
        self.assertIn("F17_AUDIT_UNAVAILABLE|x", got)

    def test_negative_disabled_part_would_mutate_refused(self):
        params = TOOL.merged_params({"f17_fix_steps": [], "f18_target_ids": []})
        got = TOOL.gate_refusals(params, [], [], [], [],
                                 {"boundary": 1, "f17": 1, "f18": 0})
        self.assertIn("DISABLED_PART_WOULD_MUTATE|F17|1", got)

    def test_negative_boundary_extend_zero_refused(self):
        with self.assertRaises(TOOL.PlanError):
            TOOL.merged_params({"boundary_extend_frames": 0})

    def test_negative_master_i2_genuinely_missing_still_refused(self):
        rows = [{"track_class": "MovieSceneInfinitySceneTrack",
                 "sequence": "/Game/InfinityStage/Interactions/LS_Interaction_03_ForgetsHisName",
                 "active": True, "start": 10}]
        with self.assertRaisesRegex(TOOL.PlanError, r"MASTER_I2_SECTION_COUNT\|0"):
            TOOL.master_i2_start_from_rows(rows)

    def test_negative_wrong_confirm_refused(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(TOOL.Stop):
                TOOL.main({"mode": "DRY", "run_id": "T", "confirm": "yes"}, backend=FakeBackend(root))

    def test_negative_apply_drift_refused(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend(root)
            TOOL.main({"mode": "DRY", "run_id": "T-DRY", "confirm": "DRY I2POLISH"}, backend=backend)
            backend.before_end = 3892
            with self.assertRaisesRegex(TOOL.Stop, "DRY_STATE_DRIFT"):
                TOOL.main({"mode": "APPLY", "run_id": "T-APPLY", "confirm": "APPLY I2POLISH"}, backend=backend)

    def test_negative_apply_changed_fix_key_refused(self):
        with tempfile.TemporaryDirectory() as root:
            backend = FakeBackend(root)
            dry_params = {"boundary_apply": False, "f17_fix_steps": [{
                "id": "lamp", "kind": "LIGHT_DIM", "actor_label": "Lamp", "keys": [[0, 1.0]]}]}
            TOOL.main({"mode": "DRY", "run_id": "T-DRY", "confirm": "DRY I2POLISH",
                       "params": dry_params}, backend=backend)
            apply_params = {"boundary_apply": False, "f17_fix_steps": [{
                "id": "lamp", "kind": "LIGHT_DIM", "actor_label": "Lamp", "keys": [[0, 0.5]]}]}
            with self.assertRaisesRegex(TOOL.Stop, "DRY_ARGS_DRIFT"):
                TOOL.main({"mode": "APPLY", "run_id": "T-APPLY", "confirm": "APPLY I2POLISH",
                           "params": apply_params}, backend=backend)


class CountingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super(CountingResult, self).__init__(*args, **kwargs)
        self.passed = []

    def addSuccess(self, test):
        super(CountingResult, self).addSuccess(test)
        self.passed.append(test.id().split(".")[-1])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PolishTests)
    runner = unittest.TextTestRunner(verbosity=2, resultclass=CountingResult)
    result = runner.run(suite)
    positive = sorted(name for name in result.passed if name.startswith("test_positive_"))
    negative = sorted(name for name in result.passed if name.startswith("test_negative_"))
    payload = {"total": suite.countTestCases(), "passed": len(result.passed),
               "failed": len(result.failures), "errors": len(result.errors),
               "positive_passed": positive, "negative_passed": negative}
    with open(os.path.join(HERE, "harness_result.json"), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("HARNESS_RESULT|positive=%d/%d|negative=%d/%d|total=%d/%d" % (
        len(positive), 17, len(negative), 19, len(result.passed), suite.countTestCases()))
    print("HARNESS_STATUS|%s" % ("PASS" if result.wasSuccessful() and len(positive) == 17 and len(negative) == 19 else "FAIL"))
    raise SystemExit(0 if result.wasSuccessful() else 1)
