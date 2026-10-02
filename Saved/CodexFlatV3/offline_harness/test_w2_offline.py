"""Offline fake-Unreal coverage for the W2 fresh-import/swap/verify/revert kit."""
import importlib
import json
import math
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent
SWAPKIT = HERE.parent / "swapkit"
for path in (str(HERE), str(SWAPKIT)):
    if path not in sys.path:
        sys.path.insert(0, path)

fake = importlib.import_module("w2_fake_unreal")
sys.modules["unreal"] = fake

import import_failure_cleanup as ifc
import w2_common as c
import w2_apply
import w2_import
import w2_preflight
import w2_revert
import w2_verify


CONFIG = str(SWAPKIT / "run_w2.json")


class W2OfflineTests(unittest.TestCase):
    def setUp(self):
        fake.reset()
        self.reports = {}
        c.write_report = self._write_report
        c.read_report = self._read_report
        c.log_paths = lambda: []
        c.log_has = lambda text: any(text in line for line in fake.STATE.logs)
        c.assert_run_unused = self._assert_run_unused
        ifc.package_exists_on_disk = lambda path: path in fake.STATE.disk_packages
        w2_import.load_slot_a_library = lambda: fake.FakeSlotA

    def _write_report(self, _config, phase, payload, failure=False):
        self.reports[(phase, failure)] = payload
        if not failure:
            self.reports[phase] = payload
        return "FAKE_REPORT_%s%s.json" % (phase, "_FAILURE" if failure else "")

    def _read_report(self, _config, phase):
        return self.reports[phase]

    @staticmethod
    def _assert_run_unused(run_id):
        if any(run_id in line for line in fake.STATE.logs):
            raise RuntimeError("W2_RUN_ID_ALREADY_USED|run=" + run_id)

    def run_through_apply(self):
        w2_import.main(CONFIG)
        w2_preflight.main(CONFIG)
        w2_apply.main(CONFIG)

    def test_positive_full_path_import_apply_verify_revert(self):
        imported = w2_import.main(CONFIG)
        self.assertEqual(imported["status"], "PASS")
        self.assertEqual(len(imported["saved_roots"]), 42)
        preflight = w2_preflight.main(CONFIG)
        self.assertEqual(preflight["actor_count"], 6)
        applied = w2_apply.main(CONFIG)
        self.assertEqual(applied["saved_roots"], [fake.WORLD])
        verified = w2_verify.main(CONFIG)
        self.assertEqual(verified["actor_count"], 6)
        reverted = w2_revert.main(CONFIG)
        self.assertEqual(reverted["new_mesh_referencers"], {})
        self.assertEqual(fake.STATE.content_dirty, set())
        self.assertEqual(fake.STATE.map_dirty, set())
        self.assertTrue(any("FLATV3_W2_IMPORT_OK" in line for line in fake.STATE.logs))
        self.assertTrue(any("FLATV3_W2_OK" in line for line in fake.STATE.logs))
        self.assertTrue(any("FLATV3_SLOT_RELEASED run=FV3W2-20261002-01 status=REVERTED"
                            in line for line in fake.STATE.logs))
        for actor in fake.STATE.actors:
            self.assertTrue(actor.component.mesh.path.startswith("/Game/Legacy/"))
        config = c.load_config(CONFIG)
        self.assertTrue(set(c.all_destination_paths(config)).issubset(fake.STATE.disk_packages))

    def test_seventh_wave_actor_fails_exact_count(self):
        w2_import.main(CONFIG)
        template = fake.STATE.actors[0]
        fake.STATE.actors.append(fake.Actor(
            "S3 Wave Row7 X", fake.WORLD + ":PersistentLevel.ExtraWave",
            template.component.mesh, template.transform))
        with self.assertRaisesRegex(RuntimeError, "W2_ACTOR_COUNT_FAIL.*actual=7"):
            w2_preflight.main(CONFIG)

    def test_actor_transform_change_fails_verify(self):
        self.run_through_apply()
        fake.STATE.actors[0].transform.translation.x += 0.02
        with self.assertRaisesRegex(RuntimeError, "W2_VERIFY_TRANSFORM_FAIL"):
            w2_verify.main(CONFIG)

    def test_ls_devscene_03_dirty_fails_verify(self):
        self.run_through_apply()
        fake.STATE.content_dirty.add(fake.LS)
        with self.assertRaisesRegex(RuntimeError, "W2_LS_DEVSCENE_03_DIRTY"):
            w2_verify.main(CONFIG)

    def test_import_failure_cleans_exact_created_packages(self):
        config = c.load_config(CONFIG)
        rows, _planned = w2_import.inventory(config, fake.FakeSlotA)
        first_paths = fake.FakeSlotA.asset_paths(rows[0])
        expected_created = set(first_paths[:3])
        fake.FakeSlotA.fail_key = rows[0]["key"]
        fake.FakeSlotA.fail_created_count = 3
        with self.assertRaisesRegex(RuntimeError, "FAKE_IMPORT_FAILURE"):
            w2_import.main(CONFIG)
        self.assertEqual(set(fake.STATE.deleted_assets), expected_created)
        self.assertFalse(expected_created & set(fake.STATE.assets))
        cleanup = self.reports[("import", True)]["cleanup"]
        self.assertEqual(set(cleanup["created"]), expected_created)
        self.assertEqual(set(cleanup["deleted"]), expected_created)
        self.assertEqual(cleanup["status"], "CLEAN")

    def test_ext3_variant_fails_lod1_timber_gate_after_srgb_conversion(self):
        # Basis: the approved design records the P04 fresh-import measurement as
        # linear Timber R=0.5. ext2 stores the matching sRGB-encoded byte value;
        # ext3 stores 0.5 as if it were linear, so Interchange conversion yields
        # about 0.214 and must fail the [0.49, 0.51] imported read-back gate.
        ext2_linear = fake.srgb_to_linear(0.7353569830524495)
        ext3_linear = fake.srgb_to_linear(0.5)
        self.assertAlmostEqual(ext2_linear, 0.5, places=6)
        self.assertAlmostEqual(ext3_linear, 0.21404114048223255, places=6)
        config = c.load_config(CONFIG)
        source_row = w2_import.inventory(config, fake.FakeSlotA)[0][0]
        ext3_row = dict(source_row)
        ext3_row["folder"] = source_row["folder"].replace("flats_ext2", "flats_ext3")
        ext3_row["destinations"] = {
            name: path.replace(config["destination_root"], "/Game/FakeExt3")
            for name, path in source_row["destinations"].items()
        }
        fake.FakeSlotA.import_asset(ext3_row)
        ext3_mesh = fake.EditorAssetLibrary.load_asset(ext3_row["destinations"]["mesh"])
        with self.assertRaisesRegex(RuntimeError, "W2_LOD1_TIMBER_R_FAIL"):
            w2_import.lod1_timber_gate(fake.FakeSlotA, ext3_mesh, ext3_mesh.path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
