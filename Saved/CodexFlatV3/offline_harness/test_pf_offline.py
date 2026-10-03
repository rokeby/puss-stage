"""PF offline contract harness. No Unreal, MCP, sockets, or port 8010."""
import json
from pathlib import Path
import sys
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
                 "pf_apply.py", "pf_saved_master_queue_FV3PF_20261003_02.py",
                 "pf_verify.py"]
        for name in names:
            self.assertIn("purge this folder", (KIT / name).read_text(encoding="utf-8"), name)

    def test_brief_ends_at_verify(self):
        brief = (ROOT / "Saved" / "CodexRuns" / "slots" / "PF_P05poles.md").read_text(
            encoding="utf-8")
        self.assertIn("first write; imports NEW `_poles` packages only", brief)
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
