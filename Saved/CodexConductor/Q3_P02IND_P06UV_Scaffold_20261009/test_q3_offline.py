"""Offline positive/negative harness. Explicitly never imports Blender or Unreal modules."""
from __future__ import annotations

import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WING_FBX = "E:/PussStage/DerivedAssets/FlatV3/Realism_20261007/P06_backrooms/26_concrete_panel_wood_v3/hf/builds/P06_rf_26_concrete_panel_wood_L_t5p/SM_FlatV3_P06_rf_26_concrete_panel_wood_L_t5p.fbx"
P02_FBX = "E:/PussStage/DerivedAssets/FlatV3/Overnight/P02Industrial"


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py")); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


D = load("q3_defaults"); F = load("fbx_uv_audit"); P = load("p02_industrial_retexture"); I = load("p06_scaffold_install"); U = load("uasset_string_audit"); B = load("scaffold_bake"); E = load("scaffold_export")


class Harness(unittest.TestCase):
    def test_01_p02_dry_defaults(self): self.assertEqual(D.validate_p02({})["mode"], "DRY")
    def test_02_p02_apply_confirmation_negative(self):
        with self.assertRaisesRegex(D.ConfigError, "CONFIRM"): D.validate_p02({"mode": "APPLY"})
    def test_03_p02_permanent_delete_negative(self):
        with self.assertRaisesRegex(D.ConfigError, "PERMANENT_DELETE"): D.validate_p02({"allow_permanent_asset_delete": True})
    def test_04_p02_bad_source_negative(self):
        with self.assertRaisesRegex(D.ConfigError, "SOURCE_ROOT_DRIFT"): D.validate_p02({"source_root": "C:/wrong"})
    def test_05_p02_sources_are_pot(self):
        rows = P.source_plan(D.validate_p02({})); self.assertEqual(len(rows), 12); self.assertTrue(all(r["pixels"][0] in (2048, 4096) and r["pixels"][0] == r["pixels"][1] for r in rows))
    def test_06_p02_edge_policy_is_hold(self): self.assertEqual(D.P02_TARGETS[0]["slots"]["Edge"], "EDGE_REBUILD_REQUIRED")
    def test_07_wing_fbx_exists(self): self.assertTrue(os.path.isfile(WING_FBX))
    def test_08_wing_front_planar(self):
        rows = F.audit(WING_FBX)["sections"]; front = [r for r in rows if r["material_index"] == 0]; self.assertTrue(front); self.assertTrue(all(r["u_linear_yz"]["max_abs_error"] < 1e-5 and r["v_linear_yz"]["max_abs_error"] < 1e-5 for r in front))
    def test_09_wing_flap_planar(self):
        rows = F.audit(WING_FBX)["sections"]; flap = [r for r in rows if r["material_index"] == 1]; self.assertEqual(len(flap), 1); self.assertLess(flap[0]["v_linear_yz"]["max_abs_error"], 1e-5)
    def test_10_wing_whole_mesh_negative_control(self):
        rows = F.audit(WING_FBX)["sections"]; tiled = [r for r in rows if r["material_index"] == 2]; self.assertTrue(any(r["u_linear_yz"]["max_abs_error"] > 0.1 for r in tiled))
    def test_11_edge_winding_is_not_global_outward(self):
        names = ("FenceTarp_L", "FenceTarp_R", "FenceOpen_L", "FenceOpen_R", "RollerShutter_L", "RollerShutter_R")
        for name in names:
            result = F.winding_audit(os.path.join(P02_FBX, "SM_FlatV3_P02_IND_%s.fbx" % name), 3)
            self.assertTrue(any(r["verdict"] != "outward" for r in result["sections"]), name)
    def test_12_audit_apply_negative(self):
        with self.assertRaises(SystemExit): F.main([WING_FBX, "--mode", "APPLY"])
    def test_13_scaffold_two_bay_default(self): self.assertEqual(D.validate_scaffold({})["variant"], "2bay")
    def test_14_scaffold_three_bay_negative(self):
        with self.assertRaisesRegex(D.ConfigError, "THREE_BAY"): D.validate_scaffold({"variant": "3bay"})
    def test_15_scaffold_target_drift_negative(self):
        with self.assertRaisesRegex(D.ConfigError, "TARGET_ROWS_DRIFT"): D.validate_scaffold({"replace": {}})
    def test_16_scaffold_apply_confirmation_negative(self):
        with self.assertRaisesRegex(D.ConfigError, "CONFIRM"): D.validate_scaffold({"mode": "APPLY"})
    def test_17_export_defaults(self): self.assertEqual(D.validate_export({})["variants"], [2, 3])
    def test_18_export_frame_negative(self):
        with self.assertRaisesRegex(D.ConfigError, "FRAME"): D.validate_export({"front_axis": "+X"})
    def test_19_import_modules_are_offline(self): self.assertIsNone(P.unreal); self.assertIsNone(I.unreal)
    def test_20_no_permanent_delete_calls(self):
        for name in ("p02_industrial_retexture.py", "p06_scaffold_install.py", "scaffold_bake.py", "scaffold_export.py"):
            text = open(os.path.join(HERE, name), encoding="utf-8").read(); self.assertNotIn("delete_asset", text); self.assertNotIn("os.remove", text); self.assertNotIn(".unlink(", text)
    def test_21_live_placeholders_are_64px(self):
        rows = [r for r in U.audit()["assets"] if "source_pixels" in r]; self.assertEqual(len(rows), 3); self.assertTrue(all(r["source_pixels"] == [64, 64] for r in rows))
    def test_22_blender_scripts_import_offline(self): self.assertTrue(callable(B.main) and callable(E.main))
    def test_23_bake_apply_confirmation_negative(self):
        with self.assertRaisesRegex(RuntimeError, "CONFIRM"): B.parse(["--mode", "APPLY"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Harness); result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "marker": "Q3_OFFLINE_HARNESS_OK" if result.wasSuccessful() else "Q3_OFFLINE_HARNESS_FAIL"}
    with open(os.path.join(HERE, "offline_harness_report.json"), "w", encoding="utf-8") as handle: json.dump(report, handle, indent=2)
    print(report["marker"] + "|tests=%d|failures=%d|errors=%d" % (report["tests_run"], report["failures"], report["errors"]))
    raise SystemExit(0 if result.wasSuccessful() else 1)
