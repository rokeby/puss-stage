"""Offline positive/negative harness for Codex job 93. No Unreal import or project mutation."""
import copy
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = load("p93_core_test", os.path.join(HERE, "p93_core.py"))
live = load("p93_live_test", os.path.join(HERE, "p93_live.py"))

GUIDS = [
    "B8AE7B1FDF410C9B9F2A83BDA94DA489", "0ED8CD9770436E3F130C8D85C3637BE2",
    "C82F2CC5BD4EF34E9C3BDFACB10C35CB", "8D58B97EDF4136FDBE50549E3625C0DF",
    "3DC9D2BC0445FD5D87E5428D6C467C86", "FC0C59529D4588FCEFC84F9FD09C68A3",
    "7230D0A9AD4491A8CBFB788DC5A7D95C", "7742F44B2A42B6A7203114874CAD3E5B",
    "84C1E90ADF41D6E38AB76EADD2179FE6", "0C81EB2D824B7C77E674BBA604B985A7",
    "5606A2F1DC449E7E3FAC5E866173DD7F", "0780796E60484341D039F5B00A6008FB",
    "622946E51046353D4D27EF8B20389CE3", "300EDBEC62425BC6687C5E86503FC8E1",
    "65711AE75E4F1BB66477C1A75052C245", "686F7D11CA4DC4681D962CBAF664FAD8",
    "53675A61CE474C46CE0F42890F785DE0", "B668CE90914EC39B4A510A9EE1A02F51",
    "1D832ADD2745EC4745DA81B968DAC5A8", "37A6207F3244F31A88BAEC943AAF31C6",
    "F98DD3DCF845CF8E62CC9B835FC7F8B0",
]
LABELS = ["P03 Wing 001", "P03 Wing 003", "P03 Wing 002"] + ["P03 Wing %03d" % i for i in range(4, 22)]


def rows():
    out = []
    for i, (guid, label) in enumerate(zip(GUIDS, LABELS)):
        old = i < 3
        root = core.OLD_MESH_ROOT if old else "/Game/Scenes/Wings/FlatV3/Realism/T5P/SM_FlatV3_P03_green_"
        out.append({"cue_guid": guid, "label": label, "type": "<InfinityCueType.WING_PAIR: 0>",
                    "enabled": True, "show_index": 76 + i, "interval_ticks": 1000 + i,
                    "gap_cm": 500.0 + i, "L_mesh": root + "L", "R_mesh": root + "R",
                    "mechanism_sha": "mech-%02d" % i, "attachments_sha": "att-%02d" % i,
                    "cue_text": "cue-%02d" % i})
    return out


class FakeOps:
    def __init__(self):
        self.rows = rows()
        self.meta = {"passage_guid": "P03GUID", "first_cue_guid": GUIDS[0], "last_cue_guid": GUIDS[-1],
                     "first_show_index": 76, "settings_count": 6}
        self.dirty = {"content": [], "maps": []}
        self.logs = []
        self.floor_material = "/Game/EnvironmentPacks/4K_WoodFlooring_Vol_02/Materials/" + \
                              "M_Walnut_Hrrngbn_02_Mat_Inst_Dup.M_Walnut_Hrrngbn_02_Mat_Inst_Dup"
        self.floor_transform = "(Translation=(X=1,Y=2,Z=3))"
        self.backups = []

    def log(self, value): self.logs.append(value)
    def fail(self, run, reason): raise core.GateError(reason)
    def census(self): return copy.deepcopy(self.dirty)
    def read_wings(self): return copy.deepcopy(self.rows), copy.deepcopy(self.meta)
    def write_wings(self, plan):
        by = {r["cue_guid"]: r for r in self.rows}
        self.rows = []
        for p in plan["rows"]:
            r = by[p["cue_guid"]]; r["interval_ticks"] = p["interval_ticks"]; r["gap_cm"] = p["gap_cm"]
            self.rows.append(r)
        self.dirty = {"content": [core.SHOW_PATH], "maps": []}
    def restore_wing_order_and_slots(self, record):
        by = {r["cue_guid"]: r for r in self.rows}; self.rows = []
        for guid in record["plan"]["before_guids"]:
            r = by[guid]; r.update(record["original_slots_by_guid"][guid]); self.rows.append(r)
        self.dirty = {"content": [core.SHOW_PATH], "maps": []}
    def materialize(self, passage_guid):
        assert passage_guid == "P03GUID"
        self.dirty = {"content": [core.SHOW_PATH], "maps": [core.WORLD_PATH]}; return 21
    def backup(self, name, include_show):
        self.backups.append((name, include_show)); return "/backup/" + name, [{"sha256": "abc"}]
    def save_wings(self): self.dirty = {"content": [], "maps": []}
    def floor(self):
        plan = core.floor_plan(self.floor_material, self.floor_transform, "/Level/Floor.Component")
        return object(), object(), plan
    def set_floor_material(self, path):
        self.floor_material = path + ".MI_Floor_DarkWet" if "." not in path else path
        self.dirty = {"content": [], "maps": [core.WORLD_PATH]}
        return self.floor()[2]
    def save_floor(self): self.dirty = {"content": [], "maps": []}


class P93Harness(unittest.TestCase):
    def test_pos_plan_exact_census(self):
        p = core.build_relayout(rows())
        self.assertEqual(p["count"], 21); self.assertEqual(p["old_square_count"], 3)
        self.assertEqual(p["newer_count"], 18); self.assertEqual(p["refusals"], [])

    def test_pos_interleave_ordinals(self):
        p = core.build_relayout(rows())
        got = [r["new_ordinal"] for r in p["rows"] if r["label"] in core.OLD_LABELS]
        self.assertEqual(got, [1, 8, 15])

    def test_pos_slot_timing_preserved(self):
        before = rows(); p = core.build_relayout(before)
        self.assertEqual([(r["interval_ticks"], r["gap_cm"]) for r in p["rows"]],
                         [(r["interval_ticks"], r["gap_cm"]) for r in before])

    def test_pos_cue_identity_travels(self):
        p = core.build_relayout(rows())
        row = next(x for x in p["rows"] if x["label"] == "P03 Wing 003")
        self.assertEqual((row["cue_guid"], row["mechanism_sha"], row["attachments_sha"]),
                         (GUIDS[1], "mech-01", "att-01"))

    def test_pos_enum_normalization(self):
        self.assertEqual(core.enum_name("<InfinityCueType.WING_PAIR: 0>"), "WING_PAIR")
        self.assertEqual(core.enum_name("InfinityCueType.WING_PAIR"), "WING_PAIR")

    def test_neg_count(self):
        with self.assertRaisesRegex(core.GateError, "P03_CUE_COUNT"): core.build_relayout(rows()[:-1])

    def test_neg_duplicate_guid(self):
        r = rows(); r[-1]["cue_guid"] = r[0]["cue_guid"]
        with self.assertRaisesRegex(core.GateError, "DUPLICATE"): core.build_relayout(r)

    def test_neg_enum(self):
        r = rows(); r[4]["type"] = "<InfinityCueType.SCENE: 1>"
        with self.assertRaisesRegex(core.GateError, "NON_WINGPAIR"): core.build_relayout(r)

    def test_neg_disabled(self):
        r = rows(); r[4]["enabled"] = False
        with self.assertRaisesRegex(core.GateError, "DISABLED"): core.build_relayout(r)

    def test_neg_old_mesh_drift(self):
        r = rows(); r[1]["L_mesh"] = "/drift"
        self.assertTrue(any("OLD_ROW_MESH_DRIFT" in x for x in core.build_relayout(r)["refusals"]))

    def test_neg_old_guid_drift(self):
        r = rows(); r[1]["cue_guid"] = "A" * 32
        self.assertTrue(any("OLD_ROW_GUID_DRIFT" in x for x in core.build_relayout(r)["refusals"]))

    def test_pos_readback(self):
        original = rows(); p = core.build_relayout(original); by = {r["cue_guid"]: r for r in original}
        after = []
        for want in p["rows"]:
            r = copy.deepcopy(by[want["cue_guid"]]); r.update({"interval_ticks": want["interval_ticks"], "gap_cm": want["gap_cm"]})
            after.append(r)
        self.assertEqual(core.validate_relayout_readback(after, p), [])

    def test_neg_readback_mechanism(self):
        p = core.build_relayout(rows()); after = rows(); after[0]["mechanism_sha"] = "changed"
        self.assertTrue(core.validate_relayout_readback(after, p))

    def test_pos_owned_revert_gate_allows_foreign_mechanism_edit(self):
        original = rows(); p = core.build_relayout(original); by = {r["cue_guid"]: r for r in original}; after = []
        for want in p["rows"]:
            r = copy.deepcopy(by[want["cue_guid"]]); r.update({"interval_ticks": want["interval_ticks"], "gap_cm": want["gap_cm"]})
            after.append(r)
        after[5]["mechanism_sha"] = "later-owner-edit"
        self.assertEqual(core.validate_applied_owned(after, p), [])

    def test_neg_owned_revert_gate_timing_drift(self):
        original = rows(); p = core.build_relayout(original); by = {r["cue_guid"]: r for r in original}; after = []
        for want in p["rows"]:
            r = copy.deepcopy(by[want["cue_guid"]]); r.update({"interval_ticks": want["interval_ticks"], "gap_cm": want["gap_cm"]})
            after.append(r)
        after[5]["gap_cm"] += 2.0
        self.assertTrue(core.validate_applied_owned(after, p))

    def test_pos_floor_plan(self):
        p = core.floor_plan("/X/M_Walnut_Hrrngbn_02_Mat_Inst_Dup.Asset", "xf", "comp")
        self.assertTrue(p["expected_walnut"]); self.assertFalse(p["already_target"])

    def test_neg_floor_null(self):
        with self.assertRaisesRegex(core.GateError, "FLOOR_SLOT0_NULL"): core.floor_plan(None, "xf", "comp")

    def test_pos_wings_dry_apply_revert(self):
        with tempfile.TemporaryDirectory() as temp:
            old = live.HERE; live.HERE = temp
            try:
                ops = FakeOps(); live.dry_wings(ops, "DRYRUN", {"confirm": "DRY P93WINGS"})
                dry = live.read_json(os.path.join(temp, "p93_wings_dry_latest.json"))
                live.apply_wings(ops, "APPLYRUN", {"confirm": "APPLY P93WINGS " + dry["plan"]["confirm_token"]})
                self.assertEqual([r["label"] for r in ops.rows if r["label"] in core.OLD_LABELS], list(core.OLD_LABELS))
                live.revert_wings(ops, "REVERTRUN", {"confirm": "REVERT P93WINGS APPLYRUN"})
                self.assertEqual([r["cue_guid"] for r in ops.rows], GUIDS)
                self.assertEqual(ops.dirty, {"content": [], "maps": []})
            finally: live.HERE = old

    def test_neg_wings_confirm(self):
        with tempfile.TemporaryDirectory() as temp:
            old = live.HERE; live.HERE = temp
            try:
                with self.assertRaisesRegex(live.core.GateError, "CONFIRM"):
                    live.dry_wings(FakeOps(), "X", {"confirm": "NO"})
            finally: live.HERE = old

    def test_neg_wings_dirty(self):
        ops = FakeOps(); ops.dirty["maps"] = ["/Game/Other"]
        with self.assertRaisesRegex(live.core.GateError, "DIRTY_AT_START"): live.dry_wings(ops, "X", {"confirm": "DRY P93WINGS"})

    def test_pos_floor_dry_apply_revert(self):
        with tempfile.TemporaryDirectory() as temp:
            old = live.HERE; live.HERE = temp
            try:
                ops = FakeOps(); live.dry_floor(ops, "FDRY", {"confirm": "DRY P93FLOOR"})
                dry = live.read_json(os.path.join(temp, "p93_floor_dry_latest.json"))
                live.apply_floor(ops, "FAPPLY", {"confirm": "APPLY P93FLOOR " + dry["plan"]["confirm_token"]})
                self.assertEqual(ops.floor_material.split(".")[0], core.FLOOR_TARGET)
                live.revert_floor(ops, "FREVERT", {"confirm": "REVERT P93FLOOR FAPPLY"})
                self.assertIn(core.FLOOR_OLD_EXPECTED_TOKEN, ops.floor_material)
                self.assertEqual(ops.dirty, {"content": [], "maps": []})
            finally: live.HERE = old

    def test_neg_floor_unexpected_source(self):
        with tempfile.TemporaryDirectory() as temp:
            old = live.HERE; live.HERE = temp
            try:
                ops = FakeOps(); ops.floor_material = "/Unexpected.Material"
                with self.assertRaisesRegex(live.core.GateError, "UNEXPECTED_SOURCE_MATERIAL"):
                    live.dry_floor(ops, "X", {"confirm": "DRY P93FLOOR"})
            finally: live.HERE = old

    def test_neg_floor_transform_drift_on_revert(self):
        with tempfile.TemporaryDirectory() as temp:
            old = live.HERE; live.HERE = temp
            try:
                ops = FakeOps(); live.dry_floor(ops, "D", {"confirm": "DRY P93FLOOR"})
                d = live.read_json(os.path.join(temp, "p93_floor_dry_latest.json"))
                live.apply_floor(ops, "A", {"confirm": "APPLY P93FLOOR " + d["plan"]["confirm_token"]})
                ops.floor_transform = "changed"
                with self.assertRaisesRegex(live.core.GateError, "FOREIGN_TRANSFORM_DRIFT"):
                    live.revert_floor(ops, "R", {"confirm": "REVERT P93FLOOR A"})
            finally: live.HERE = old


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(P93Harness)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "positive_and_negative_controls": True, "ok": result.wasSuccessful()}
    with open(os.path.join(HERE, "offline_harness_report.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, sort_keys=True); handle.write("\n")
    print("P93_OFFLINE_HARNESS_%s|tests=%d|failures=%d|errors=%d" %
          ("PASS" if result.wasSuccessful() else "FAIL", result.testsRun, len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
