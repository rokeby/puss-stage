"""PF offline contract harness. No Unreal, MCP, network sockets, or port 8010."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[3]
KIT = ROOT / "Saved" / "CodexFlatV3" / "swapkit"
sys.path.insert(0, str(KIT))
import pf_support as pf


class PFContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = pf.load_config(str(KIT / "run_pf.json"))

    def before(self):
        return {"panel_world_bottom_cm": 325.0, "pole_world_bottom_cm": 225.0,
                "inner_edge_cm": -12.5}

    def after(self):
        return {"panel_world_bottom_cm": 325.0, "pole_world_bottom_cm": -135.0,
                "inner_edge_cm": -12.5}

    def skipped_snapshot(self, mesh="/Game/Legacy/SM_CloudRef03_R"):
        transform = {"location": [1.0, 2.0, 3.0], "rotation": [0.0, 0.0, 0.0],
                     "scale": [1.0, 1.0, 1.0]}
        return {"status": "SKIPPED", "reason": "kept_old_non_v3", "mesh": mesh,
                "panel_local_transform": transform,
                "base_world_transform": transform,
                "instance_world_transform": transform,
                "world_bounds": {"world_min": [-10.0, -20.0, 100.0],
                                 "world_max": [10.0, 20.0, 500.0]}}

    def test_positive_pf_path(self):
        gate = pf.validate_measurement(self.before(), self.after(), self.config, "positive:left")
        self.assertEqual(gate["panel_bottom_delta_cm"], 0.0)
        self.assertEqual(gate["inner_edge_delta_cm"], 0.0)
        self.assertLessEqual(gate["pole_clearance_to_floor_cm"], 1.0)
        self.assertEqual(pf.validate_gap(25.0, 25.0, self.config, "positive"), 0.0)
        self.assertTrue(pf.ensure_fresh_import([]))
        build = json.loads(Path(self.config["build_report"]).read_text(encoding="utf-8"))
        self.assertTrue(build["all_pass"])
        self.assertEqual(build["asset_count"], 16)
        self.assertEqual(build["pole_extension_cm"], 460.0)
        self.assertTrue(all(row["pass"] and row["asset"].endswith("_poles")
                            for row in build["assets"]))
        for row in build["assets"]:
            output = Path(row["fbx"]).parent
            status = json.loads((output / "status.json").read_text(encoding="utf-8"))
            new = json.loads(Path(status["build_manifest"]).read_text(encoding="utf-8"))
            baseline_dir = Path(row["baseline_fbx"]).parent
            baseline = json.loads(next(baseline_dir.glob("*_build.json")).read_text(encoding="utf-8"))
            self.assertEqual(new["art_panel_geometry_contract"],
                             baseline["art_panel_geometry_contract"])
            self.assertEqual(new["triangle_counts"], baseline["triangle_counts"])
            self.assertTrue(row["source_png_sha256"])
            socket = json.loads(Path(status["socket_sidecar"]).read_text(encoding="utf-8"))
            self.assertEqual(socket["baked_pole_geometry"]["bottom_z_cm"], -460.0)

    def test_pole_above_floor_fails(self):
        bad = dict(self.after(), pole_world_bottom_cm=1.01)
        with self.assertRaisesRegex(RuntimeError, "POLE_BOTTOM_ABOVE_FLOOR"):
            pf.validate_measurement(self.before(), bad, self.config, "pole-negative")

    def test_changed_panel_bottom_fails(self):
        bad = dict(self.after(), panel_world_bottom_cm=326.01)
        with self.assertRaisesRegex(RuntimeError, "PANEL_BOTTOM_CHANGED"):
            pf.validate_measurement(self.before(), bad, self.config, "panel-negative")

    def test_reimport_attempt_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "PF_REIMPORT_REFUSED"):
            pf.ensure_fresh_import(["/Game/Scenes/Wings/FlatV3/Passage05/StaticMeshes/Existing_poles"])

    def test_pf_scopes_slot_a_common_inventory_to_p05(self):
        workflow = (KIT / "pf_workflow.py").read_text(encoding="utf-8")
        self.assertIn('module.TARGETS = {"P05": config["destination_root"]}', workflow)
        self.assertIn('module.EXPECTED_COUNTS = {"P05": config["expected_asset_count"]}', workflow)

    def test_real_p05_aged_hash_mismatch_still_fails(self):
        source_path = ROOT / "Saved" / "CodexFlatV3" / "slot_a_import.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        wanted = {"sha256_file", "common_inventory"}
        body = [node for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted]
        module = types.ModuleType("pf_offline_slot_a_hash_gate")
        module.__dict__.update({"hashlib": hashlib, "json": json,
                                "COMMON_AGED": ("T_P05_Aged_Test",),
                                "TARGETS": {"P05": "/Game/P05"}})
        exec(compile(ast.Module(body=body, type_ignores=[]), str(source_path), "exec"),
             module.__dict__)
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / "first.png"
            second = Path(folder) / "second.png"
            first.write_bytes(b"P05-aged-source-A")
            second.write_bytes(b"P05-aged-source-B")
            rows = [
                {"passage": "P05", "sources": {"T_P05_Aged_Test": str(first)}},
                {"passage": "P05", "sources": {"T_P05_Aged_Test": str(second)}},
            ]
            with self.assertRaisesRegex(RuntimeError,
                                        "COMMON_AGED_HASH_MISMATCH\\|passage=P05"):
                module.common_inventory(rows)

    def test_preferred_material_path_reuses_source_mis_and_o2(self):
        contract = pf.source_material_contract(
            self.config["destination_root"], "P05_CloudRef01_L_L",
            self.config["required_texture_suffix"])
        self.assertEqual(
            contract["slot_materials"]["Front"],
            self.config["destination_root"] +
            "/Materials/Instances/MI_FlatV3_P05_CloudRef01_L_L_Front")
        self.assertTrue(all(value.endswith("_o2")
                            for value in contract["texture_parameters"].values()))
        self.assertEqual(
            pf.validate_o2_material_parameters(
                dict(contract["texture_parameters"]), contract["texture_parameters"], "positive"),
            contract["texture_parameters"])
        workflow = (KIT / "pf_workflow.py").read_text(encoding="utf-8")
        inventory_source = workflow[workflow.index("def import_inventory("):
                                    workflow.index("def verify_material_binding(")]
        self.assertNotIn('original, "skin"', inventory_source)
        self.assertIn("def import_mesh_only(", workflow)
        self.assertIn('"new_texture_count": 0, "new_mi_count": 0', workflow)

    def test_non_o2_skincolor_fails_material_verify(self):
        expected = pf.source_material_contract(
            self.config["destination_root"], "P05_CloudRef01_L_L",
            self.config["required_texture_suffix"])["texture_parameters"]
        bad = dict(expected)
        bad["SkinColor"] = bad["SkinColor"].removesuffix("_o2")
        with self.assertRaisesRegex(RuntimeError, "PF_POLES_NON_O2_SKINCOLOR"):
            pf.validate_o2_material_parameters(
                bad, expected, "negative:old-hatched-skin", self.config["required_texture_suffix"])

    def test_kept_old_side_is_skipped_and_unchanged(self):
        old = {"mesh": "/Game/Scenes/Wings/Legacy/SM_CloudRef03_R"}
        skipped = pf.source_policy(old, {}, self.config["destination_root"])
        self.assertEqual(skipped, {"action": "skip", "reason": "kept_old_non_v3",
                                   "mesh": old["mesh"]})
        built_name = "SM_FlatV3_P05_CloudRef03_L_L"
        built = {"mesh": (self.config["destination_root"] +
                          "/StaticMeshes/" + built_name)}
        replacement = pf.source_policy(
            built, {built_name: {"pass": True}}, self.config["destination_root"])
        self.assertEqual(replacement["action"], "replace")
        self.assertEqual(replacement["target_mesh"], built["mesh"] + "_poles")
        gate = pf.validate_skipped_unchanged(
            self.skipped_snapshot(), self.skipped_snapshot(), "positive:kept-old")
        self.assertEqual(gate["status"], "UNCHANGED")

    def test_flat_v3_side_without_build_still_fails(self):
        panel = {"mesh": (self.config["destination_root"] +
                          "/StaticMeshes/SM_FlatV3_P05_Unbuilt_L")}
        with self.assertRaisesRegex(RuntimeError, "PF_SOURCE_NOT_BUILT"):
            pf.source_policy(panel, {}, self.config["destination_root"])

    def test_apply_touching_skipped_side_fails_verify(self):
        before = self.skipped_snapshot()
        after = self.skipped_snapshot(mesh="/Game/Changed/SM_FlatV3_P05_Changed_R")
        with self.assertRaisesRegex(RuntimeError, "PF_SKIPPED_SIDE_CHANGED"):
            pf.validate_skipped_unchanged(before, after, "negative:skip-touched")

    def test_config_has_no_stale_index_authority(self):
        raw = json.loads((KIT / "run_pf.json").read_text(encoding="utf-8"))
        self.assertNotIn("expected_row_index_start", raw)
        self.assertNotIn("expected_row_index_end", raw)
        workflow = (KIT / "pf_workflow.py").read_text(encoding="utf-8")
        self.assertIn("enumerate(cues)", workflow)
        self.assertIn("passage_label_prefix", workflow)
        self.assertIn("len(set(guids))", workflow)

    def test_all_entry_scripts_purge_stale_modules(self):
        names = ["pf_preflight.py", "pf_import.py", "pf_dry.py", "pf_backup.py",
                 "pf_apply.py", "pf_saved_master_queue_FV3PF_20261003_03.py",
                 "pf_verify.py"]
        for name in names:
            source = (KIT / name).read_text(encoding="utf-8")
            self.assertIn("purge this folder", source, name)
            self.assertNotIn("importlib.reload", source, name)

    def test_fresh_ids_are_configured_and_absent_from_every_log(self):
        self.assertEqual(self.config["run_id"], "FV3PF-20261003-03")
        self.assertEqual(self.config["import_run_id"], "FV3PFI-20261003-03")
        logs = sorted((ROOT / "Saved" / "Logs").glob("PussStage*.log"))
        self.assertTrue(logs)
        for path in logs:
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn(self.config["run_id"], text, str(path))
            self.assertNotIn(self.config["import_run_id"], text, str(path))

    def test_brief_ends_at_verify(self):
        brief = (ROOT / "Saved" / "CodexRuns" / "slots" / "PF_P05poles.md").read_text(
            encoding="utf-8")
        self.assertIn("first write; imports NEW `_poles` packages only", brief)
        self.assertIn("reuses the existing source-flat Front/Flap MIs", brief)
        self.assertIn("non-`_o2` `SkinColor`", brief)
        self.assertIn("this is not the end", brief)
        self.assertIn("**END here.**", brief)

    def test_final_verify_is_content_read_only(self):
        source = (KIT / "pf_workflow.py").read_text(encoding="utf-8")
        verify_source = source[source.index("def verify("):]
        for forbidden in ("save_asset(", "save_current_level(", "set_editor_property(",
                          ".modify(", "materialize_passage("):
            self.assertNotIn(forbidden, verify_source, forbidden)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PFContract)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("PF OVERALL: %s" % ("PASS" if result.wasSuccessful() else "FAIL"))
    raise SystemExit(0 if result.wasSuccessful() else 1)
