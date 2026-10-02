"""Offline C3 contract harness.  No Unreal, MCP, sockets, or port 8010."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[3]
KIT = ROOT / "Saved" / "CodexFlatV3" / "swapkit"
sys.path.insert(0, str(KIT))
import c3_support as c3
import c3_compare as compare


class Outer:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


class Asset:
    def __init__(self, package):
        self.package = package

    def get_outermost(self):
        return Outer(self.package)


class CleanupState:
    def __init__(self):
        self.assets = {}
        self.dirty = set()
        self.maps = set()
        self.refs = {}
        self.deleted = []
        self.logs = []


def cleanup_module(state):
    fake = types.ModuleType("unreal")
    fake.Paths = types.SimpleNamespace(
        convert_relative_path_to_full=lambda value: value,
        project_content_dir=lambda: str(ROOT / "Content"),
    )
    fake.find_object = lambda _outer, object_path: state.assets.get(object_path.split(".", 1)[0])

    class EditorAssetLibrary:
        @staticmethod
        def find_package_referencers_for_asset(path, _load):
            return sorted(state.refs.get(path, set()))

        @staticmethod
        def delete_loaded_asset(asset):
            path = asset.package
            if path not in state.assets:
                return False
            del state.assets[path]
            state.dirty.discard(path)
            state.deleted.append(path)
            return True

        @staticmethod
        def does_asset_exist(path):
            return path in state.assets

    fake.EditorAssetLibrary = EditorAssetLibrary
    fake.log_error = state.logs.append
    previous = sys.modules.get("unreal")
    sys.modules["unreal"] = fake
    try:
        spec = importlib.util.spec_from_file_location(
            "c3_import_failure_cleanup_harness", KIT / "import_failure_cleanup.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            del sys.modules["unreal"]
        else:
            sys.modules["unreal"] = previous
    module.package_exists_on_disk = lambda _path: False
    return module


class C3OfflineHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = c3.load_config(str(KIT / "run_c3.json"))

    def test_positive_exact_twelve_row_path(self):
        targets = self.config["targets"]
        with open(self.config["source_c_dry_plan"], encoding="utf-8") as handle:
            source = json.load(handle)
        source_targets = [{"cue_index": row["cue_index"], "cue_guid": row["cue_guid"],
                           "cue_label": row["cue_label"]}
                          for row in source["rows"]
                          if row["cue_label"] == "P05 Wing 002" and
                          row["left"]["mesh"] == self.config["old_left_mesh"]]
        keys = c3.validate_target_rows(source_targets, targets, 12)
        self.assertEqual(len(keys), 12)
        donor = next(row for row in source["rows"]
                     if row["cue_index"] == self.config["donor"]["cue_index"] and
                     row["cue_guid"] == self.config["donor"]["cue_guid"])
        self.assertEqual(compare.facing_key(donor["left"]["facing_policy"]),
                         "PRESERVE_ASSET")
        self.assertFalse(donor["left"]["flip_image_horizontally"])
        gap_rows = []
        for row in targets:
            expected = c3.target_height(self.config, row["cue_guid"], "left")
            self.assertEqual(c3.assert_bottom(expected, expected, 1.0, row["cue_guid"]),
                             expected)
            gap_rows.append({**row, "gap_old_cm": 240.0, "gap_new_cm": 240.0})
        self.assertEqual(c3.minimum_gap_gate(gap_rows, 2.0)["row_count"], 12)

    def test_negative_thirteenth_target_fails(self):
        rows = list(self.config["targets"]) + [{
            "cue_index": 212, "cue_guid": "13TH", "cue_label": "P05 Wing 002"}]
        with self.assertRaisesRegex(RuntimeError, "C3_TARGET_COUNT_FAIL"):
            c3.validate_target_rows(rows, self.config["targets"], 12)

    def test_negative_bottom_not_equal_h_fails(self):
        row = self.config["targets"][0]
        expected = c3.target_height(self.config, row["cue_guid"], "left")
        with self.assertRaisesRegex(RuntimeError, "C3_BOTTOM_NOT_H"):
            c3.assert_bottom(expected + 1.01, expected, 1.0, row["cue_guid"])

    def test_negative_onstage_inner_move_fails(self):
        with self.assertRaisesRegex(RuntimeError, "C3_ONSTAGE_INNER_MOVE"):
            c3.validate_offstage_move("left", 0.25)

    def test_negative_import_failure_cleans_exact_created_packages(self):
        state = CleanupState()
        helper = cleanup_module(state)
        paths = [
            "/Game/C3/StaticMeshes/SM_Created",
            "/Game/C3/Materials/Instances/MI_Created",
            "/Game/C3/Textures/T_Created",
        ]
        keep = "/Game/Existing/Keep"

        def census():
            return {"content": sorted(state.dirty), "maps": sorted(state.maps)}

        state.assets[keep] = Asset(keep)
        tracker = helper.ImportRunTracker("C3", paths, census(), census)
        for path in paths:
            state.assets[path] = Asset(path)
            state.dirty.add(path)
        tracker.observe_created()
        state.refs[paths[1]] = {paths[0]}
        state.refs[paths[2]] = {paths[1]}
        result, error = helper.cleanup_after_failure(
            "C3", "FV3C3I-HARNESS", tracker, census)
        self.assertIsNone(error)
        self.assertEqual(result["status"], "CLEAN")
        self.assertEqual(result["created"], sorted(paths))
        self.assertEqual(result["deleted"], paths)
        self.assertEqual(state.deleted, paths)
        self.assertEqual(census(), {"content": [], "maps": []})
        self.assertIn(keep, state.assets)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(C3OfflineHarness)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"suite": "C3_OFFLINE", "tests": result.testsRun,
                      "failures": len(result.failures), "errors": len(result.errors),
                      "passed": result.wasSuccessful()}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
