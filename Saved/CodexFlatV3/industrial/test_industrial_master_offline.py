"""Offline +/- harness for make_industrial_master.py using a fake unreal module."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest


HERE = os.path.dirname(os.path.abspath(__file__))


def load_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


F = load_path("fake_unreal_industrial", os.path.join(HERE, "fake_unreal_industrial.py"))


def load_tool(fake):
    old = sys.modules.get("unreal")
    sys.modules["unreal"] = fake
    try:
        return load_path("make_industrial_master_%d" % id(fake), os.path.join(HERE, "make_industrial_master.py"))
    finally:
        if old is None:
            sys.modules.pop("unreal", None)
        else:
            sys.modules["unreal"] = old


class Harness(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = self.temp.name
        self.state_dir = os.path.join(self.project, "Saved", "CodexFlatV3", "industrial")
        self.backups = os.path.join(self.project, "Backups")

    def tearDown(self):
        self.temp.cleanup()

    def tool(self, faults=None):
        fake = F.make(self.project, faults=faults)
        return load_tool(fake), fake

    def test_01_dry_defaults_positive(self):
        tool, _ = self.tool()
        args = tool.validate_args({})
        self.assertEqual(args["mode"], "DRY")
        self.assertTrue(args["two_sided"])

    def test_02_apply_confirmation_negative(self):
        tool, _ = self.tool()
        with self.assertRaisesRegex(tool.PlanError, "CONFIRM"):
            tool.validate_args({"mode": "APPLY"})

    def test_03_revert_confirmation_negative(self):
        tool, _ = self.tool()
        with self.assertRaisesRegex(tool.PlanError, "CONFIRM"):
            tool.validate_args({"mode": "REVERT"})

    def test_04_permanent_delete_negative(self):
        tool, _ = self.tool()
        with self.assertRaisesRegex(tool.PlanError, "PERMANENT_DELETE"):
            tool.validate_args({"allow_permanent_asset_delete": True})

    def test_05_flap_two_sided_negative(self):
        tool, _ = self.tool()
        with self.assertRaisesRegex(tool.PlanError, "FLAT_V3_FLAP"):
            tool.validate_args({"two_sided": False})

    def test_06_dry_fake_unreal_positive(self):
        tool, fake = self.tool()
        result = tool.execute({}, run="TEST-DRY", state_dir=self.state_dir, backup_root=self.backups)
        self.assertEqual(result["marker"], "INDUSTRIAL_MASTER_DRY_OK")
        self.assertEqual(fake._state["saves"], [])
        self.assertEqual(fake._state["dirty"], set())

    def test_07_dirty_census_negative(self):
        tool, fake = self.tool()
        fake._state["dirty"].add("/Game/Other/Dirty")
        with self.assertRaisesRegex(tool.PlanError, "DIRTY_CENSUS"):
            tool.execute({}, run="TEST-DIRTY", state_dir=self.state_dir, backup_root=self.backups)

    def test_08_apply_build_save_readback_positive(self):
        tool, fake = self.tool()
        args = {"mode": "APPLY", "confirm": "APPLY INDUSTRIALMASTER"}
        result = tool.execute(args, run="TEST-APPLY", state_dir=self.state_dir, backup_root=self.backups)
        self.assertEqual(result["marker"], "INDUSTRIAL_MASTER_APPLY_OK")
        self.assertEqual(fake._state["saves"], [tool.MASTER])
        self.assertTrue(os.path.isfile(fake._content_file(tool.MASTER)))
        self.assertEqual(result["readback"]["expression_count"], 8)
        self.assertTrue(result["readback"]["flags"]["two_sided"])
        self.assertTrue(os.path.isfile(os.path.join(self.backups, "PreIndustrialMaster-TEST-APPLY", "prechange.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.state_dir, tool.RECORD_NAME)))

    def test_09_create_only_existing_negative(self):
        tool, _ = self.tool()
        args = {"mode": "APPLY", "confirm": "APPLY INDUSTRIALMASTER"}
        tool.execute(args, run="TEST-FIRST", state_dir=self.state_dir, backup_root=self.backups)
        with self.assertRaisesRegex(tool.PlanError, "CREATE_ONLY_EXISTS"):
            tool.execute(args, run="TEST-SECOND", state_dir=os.path.join(self.project, "other"),
                         backup_root=self.backups)

    def test_10_material_setter_lie_negative(self):
        tool, _ = self.tool({"material_setter_lies": "two_sided"})
        args = {"mode": "APPLY", "confirm": "APPLY INDUSTRIALMASTER"}
        with self.assertRaisesRegex(tool.PlanError, "MATERIAL_PROPERTY_READBACK"):
            tool.execute(args, run="TEST-LIE", state_dir=self.state_dir, backup_root=self.backups)

    def test_11_compile_error_negative_no_save(self):
        tool, fake = self.tool({"compile_errors": ["simulated Failed to compile"]})
        args = {"mode": "APPLY", "confirm": "APPLY INDUSTRIALMASTER"}
        with self.assertRaisesRegex(tool.PlanError, "RECOMPILE_ERRORS"):
            tool.execute(args, run="TEST-COMPILE", state_dir=self.state_dir, backup_root=self.backups)
        self.assertEqual(fake._state["saves"], [])

    def test_12_revert_is_delete_list_positive(self):
        tool, fake = self.tool()
        tool.execute({"mode": "APPLY", "confirm": "APPLY INDUSTRIALMASTER"}, run="TEST-APPLY",
                     state_dir=self.state_dir, backup_root=self.backups)
        before = os.path.isfile(fake._content_file(tool.MASTER))
        result = tool.execute({"mode": "REVERT", "confirm": "REVERT INDUSTRIALMASTER"}, run="TEST-REVERT",
                              state_dir=self.state_dir, backup_root=self.backups)
        self.assertEqual(result["marker"], "INDUSTRIAL_MASTER_REVERT_DELETE_LIST_OK")
        self.assertEqual(result["deleted_assets"], [])
        self.assertEqual(len(result["delete_list"]), 1)
        self.assertTrue(before and os.path.isfile(fake._content_file(tool.MASTER)))
        self.assertEqual(fake._state["delete_calls"], 0)

    def test_13_mask_samplers_are_linear_grayscale(self):
        tool, _ = self.tool()
        self.assertEqual(tool.TEXTURE_SAMPLERS["RoughnessTexture"], "SAMPLERTYPE_LINEAR_GRAYSCALE")
        self.assertEqual(tool.TEXTURE_SAMPLERS["AOTexture"], "SAMPLERTYPE_LINEAR_GRAYSCALE")

    def test_14_uv1_metres_contract(self):
        tool, _ = self.tool()
        self.assertIn("UV1Metres.x * 100.0", tool.CUSTOM_CODE)
        self.assertIn("TileSizeCmU", tool.CUSTOM_CODE)
        self.assertEqual(tool.CUSTOM_INPUTS[0], "UV1Metres")

    def test_15_no_delete_api_calls(self):
        source = open(os.path.join(HERE, "make_industrial_master.py"), encoding="utf-8").read()
        self.assertNotIn("delete_asset(", source)
        self.assertNotIn("delete_assets(", source)
        self.assertNotIn("os.remove(", source)

    def test_16_request_transport_positive(self):
        request = json.load(open(os.path.join(HERE, "industrial_master_request.json"), encoding="utf-8"))
        self.assertEqual(request["toolset_name"], "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset")
        self.assertEqual(request["tool_name"], "ExecuteProjectPythonFile")
        self.assertEqual(request["arguments"]["relativeSavedPath"],
                         "CodexFlatV3/industrial/industrial_master_run.py")

    def test_17_runner_purges_before_tool_positive(self):
        source = open(os.path.join(HERE, "industrial_master_run.py"), encoding="utf-8").read()
        purge_call = 'runpy.run_path(os.path.join(SAVED, "CodexConductor", "purge_saved_module_cache.py"))'
        tool_call = 'runpy.run_path(os.path.join(SAVED, "CodexFlatV3", "industrial", "make_industrial_master.py")'
        self.assertLess(source.index(purge_call), source.index(tool_call))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Harness)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped),
              "marker": "INDUSTRIAL_MASTER_OFFLINE_HARNESS_OK" if result.wasSuccessful()
              else "INDUSTRIAL_MASTER_OFFLINE_HARNESS_FAIL"}
    with open(os.path.join(HERE, "offline_harness_report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    print("%s|tests=%d|failures=%d|errors=%d" %
          (report["marker"], report["tests_run"], report["failures"], report["errors"]))
    raise SystemExit(0 if result.wasSuccessful() else 1)
