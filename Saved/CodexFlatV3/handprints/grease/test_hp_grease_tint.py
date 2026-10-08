"""Offline harness for hp_grease_tint.py with +/- controls.   python test_hp_grease_tint.py
Writes test_hp_grease_tint_report.json.  Runs the REAL script (runpy) against fake_unreal_tint.py in a temp project
holding: the pinned grease MI worklist, a verified grease assets record, 143 dummy grease .uassets + texture + umap,
the 1034 grease decals of placement_S03_grease.json on the two wall actors, and a grease place record whose digest
is computed from that fake layer.
"""
from __future__ import annotations

import ast
import json
import re
import runpy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fake_unreal  # noqa: E402
import fake_unreal_tint  # noqa: E402

SCRIPT = HERE / "hp_grease_tint.py"
GREASE_TABLE = HERE.parent / "clamber/placement_S03_grease.json"
WALLS = PROJECT / "DerivedAssets/FlatV3/HandPrints/walls_S03.json"
ATLAS = PROJECT / "DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png"
RESULTS = {}
FORBIDDEN = ("reload_packages", "load_level", "load_map", "delete_asset", "delete_material_expression",
             "delete_all_material_expressions", "save_dirty_packages", "save_all", "EditorLevelLibrary",
             "end_play_map", "request_end_play_map", "rename_asset", "consolidate_assets")
GREASE_DIR = "/Game/Scenes/Scene3/HandPrints/Materials/Grease"
TINT_DIR = "/Game/Scenes/Scene3/HandPrints/Materials/GreaseTint"
MASTER = TINT_DIR + "/M_HP_S03_GreaseTint"


def script_ns():
    """Module-level pure helpers of the script without running main()."""
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, (ast.Assign, ast.FunctionDef))
            and not (isinstance(n, ast.Assign) and "unreal" in ast.get_source_segment(src, n))]
    ns = {"__name__": "ns", "hashlib": __import__("hashlib")}
    ns["require"] = lambda c, m: None
    for n in keep:                       # nodes needing the editor (paths, globals()) are skipped one by one
        try:
            exec(compile(ast.Module(body=[n], type_ignores=[]), str(SCRIPT), "exec"), ns)
        except NameError:
            pass
    return ns, src


NS, SRC = script_ns()


class Sim:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hpt_"))
        p = self.tmp
        g = p / "Saved/CodexFlatV3/handprints/grease"
        g.mkdir(parents=True)
        shutil.copy2(HERE / "hp_grease_mi_worklist.json", g / "hp_grease_mi_worklist.json")
        (g / "hp_grease_assets_record.json").write_text(json.dumps(
            {"stages": {"master": {"verified": True}, "mi": {"verified": True}}}), encoding="utf-8")
        umap = p / "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
        umap.parent.mkdir(parents=True)
        umap.write_bytes(b"UMAP-dummy")
        work = json.loads((HERE / "hp_grease_mi_worklist.json").read_text(encoding="utf-8"))
        gdir = p / ("Content/" + GREASE_DIR[len("/Game/"):])
        gdir.mkdir(parents=True)
        (gdir / "M_HP_S03_Grease.uasset").write_bytes(b"GREASE-MASTER")
        for i in work["instances"]:
            (gdir / (i["name"] + ".uasset")).write_bytes(i["name"].encode())
        tex = p / "Content/Scenes/Scene3/HandPrints/Textures/T_HP_S03_GreaseAtlas.uasset"
        tex.parent.mkdir(parents=True)
        tex.write_bytes(b"TEX")
        self.state = {"project": str(p).replace("\\", "/"), "dirty": False}
        self.state["assets"] = {GREASE_DIR + "/M_HP_S03_Grease", "/Game/Scenes/Scene3/HandPrints/Textures/T_HP_S03_GreaseAtlas"}
        self.state["assets"] |= {i["path"] for i in work["instances"]}
        self.u = u = fake_unreal_tint.make(self.state)
        walls = {}
        for w in json.loads(WALLS.read_text(encoding="utf-8"))["walls"]:
            t = w["actor_transform"]
            a = u.StaticMeshActor(u.Vector(*t["location"]), u.Rotator(*t["rotation_rpy"]))
            a.label = w["attach_actor_label"]
            self.state["actors"].append(a)
            walls[w["id"]] = a
        rows = json.loads(GREASE_TABLE.read_text(encoding="utf-8"))["decals"]
        for r in rows:
            a = u.DecalActor(u.Vector(*r["location"]), u.Rotator(**r["rotation"]))
            a.label, a.folder, a.tags = r["label"], "HandPrints/S03_Grease", ["HP_S03G", "HP_S03G.run.x"]
            a.decal.mat = fake_unreal.Asset(GREASE_DIR + "/" + r["material_instance"])
            a.decal.props.update({"decal_size": u.Vector(*r["decal_size"]), "sort_order": r["sort_order"],
                                  "fade_screen_size": 0.0, "mobility": "MOVABLE"})
            a.parent = walls[r["wall"]]
            self.state["actors"].append(a)
        self.n_grease = len(rows)
        (g / "hp_place_grease_record.json").write_text(json.dumps(
            {"mode": "APPLY", "saved": True, "count_after_save": len(rows),
             "grease_digest_after": self.grease_digest()}), encoding="utf-8")
        self.calls = 0

    def grease_digest(self):
        return NS["hp_digest"]([{"object_path": a.get_path_name(), "parent_label": a.parent.label,
                                 "location": [a.loc.x, a.loc.y, a.loc.z], "rotation": [a.rot.roll, a.rot.pitch, a.rot.yaw],
                                 "scale": [a.scale.x, a.scale.y, a.scale.z]} for a in self.tagged("HP_S03G")])

    def run(self, stage, dry=False, confirm=None):
        sys.modules["unreal"] = self.u
        self.calls += 1
        self.state["call"] = self.calls
        gl = {"HP_TINT_STAGE": stage, "HP_TINT_RUN_ID": "R%03d" % self.calls}
        if dry:
            gl["HP_DRY_RUN"] = True
        if confirm is not None:
            gl["HP_TINT_CONFIRM"] = confirm
        n0 = len(self.u.logs)
        runpy.run_path(str(SCRIPT), init_globals=gl)
        return self.u.logs[n0:]

    def tagged(self, t):
        return [a for a in self.state["actors"] if t in a.tags]

    def grease_view(self):
        return sorted((a.label, round(a.loc.x, 3), round(a.loc.y, 3), round(a.loc.z, 3), a.rot.roll, a.rot.pitch,
                       a.rot.yaw, a.parent.label, a.decal.mat.path, a.decal.props["sort_order"])
                      for a in self.tagged("HP_S03G"))

    def rec(self, name="hp_grease_tint_record.json"):
        f = self.tmp / "Saved/CodexFlatV3/handprints/grease" / name
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None

    def build_assets(self):
        assert ok(self.run("master"), "HP_TINT_MASTER_BUILT")
        assert ok(self.run("master_verify"), "HP_TINT_MASTER_SUCCESS")
        for _ in range(8):
            assert ok(self.run("mi_batch"), "HP_TINT_MI_BATCH_DONE")
        assert ok(self.run("mi_verify"), "HP_TINT_MI_SUCCESS")


def ok(logs, prefix):
    return any(k != "error" and m.startswith(prefix) for k, m in logs)


def err(logs):
    return [m for k, m in logs if k == "error"]


def smoothstep_ref(m, s, lo, hi):
    t = min(1.0, max(0.0, (m - lo) / (hi - lo)))
    return s * t * t * (3 - 2 * t)


def hlsl_to_py(code):
    """Transliterate TINT_ALPHA_CODE (two statements) to Python so the SHIPPED string is what is tested."""
    body = code.replace("float t =", "t =").replace(";", "")
    body = body.replace("return ", "_out = ")
    ns = {"saturate": lambda x: min(1.0, max(0.0, x)), "max": max}
    return body, ns


class Gate(unittest.TestCase):
    def test_01_tint_gate_maths(self):
        body, base = hlsl_to_py(NS["TINT_ALPHA_CODE"])
        grid = [i / 200.0 for i in range(201)]
        worst_py, worst_hlsl = 0.0, 0.0
        for lo, hi, s in ((0.40, 0.70, 0.35), (0.65, 0.95, 0.35), (0.1, 0.2, 1.0)):
            for m in grid:
                ref = smoothstep_ref(m, s, lo, hi)
                worst_py = max(worst_py, abs(NS["tint_alpha"](m, s, lo, hi) - ref))
                ns = dict(base, M=type("M", (), {"r": m})(), Lo=lo, Hi=hi, Strength=s)
                exec(body, ns)
                worst_hlsl = max(worst_hlsl, abs(ns["_out"] - ref))
        self.assertLess(worst_py, 1e-12)
        self.assertLess(worst_hlsl, 1e-12)
        d = NS["TINT_SCALARS"]
        self.assertEqual(NS["tint_alpha"](d["TintLo"], d["TintStrength"], d["TintLo"], d["TintHi"]), 0.0)
        self.assertAlmostEqual(NS["tint_alpha"](1.0, d["TintStrength"], d["TintLo"], d["TintHi"]), d["TintStrength"])
        self.assertLessEqual(max(NS["TINT_COLOR"][:3]), 0.3)                 # faint, dark red
        # negative control: a linear ramp impostor must FAIL the same comparison
        impostor = lambda m, s, lo, hi: s * min(1.0, max(0.0, (m - lo) / (hi - lo)))
        self.assertGreater(max(abs(impostor(m, 0.35, 0.4, 0.7) - smoothstep_ref(m, 0.35, 0.4, 0.7)) for m in grid), 0.01)
        cov = {}
        try:
            import numpy as np
            from PIL import Image
            r = np.asarray(Image.open(ATLAS)).astype(float)[..., 0] / 255.0
            r = r[r > 0.02]
            for lo, hi in ((d["TintLo"], d["TintHi"]), (0.65, 0.95)):
                t = np.clip((r - lo) / (hi - lo), 0, 1)
                a = d["TintStrength"] * t * t * (3 - 2 * t)
                cov["%.2f-%.2f" % (lo, hi)] = {"frac_tinted": round(float((a > 0).mean()), 4),
                                              "frac_over_half": round(float((a > d["TintStrength"] / 2).mean()), 4),
                                              "max_alpha": round(float(a.max()), 3)}
        except Exception as exc:                                              # measurement only, not a gate
            cov["error"] = str(exc)
        RESULTS["tint_gate"] = {"py_max_err": worst_py, "hlsl_string_max_err": worst_hlsl,
                                "impostor_rejected": True, "atlas_coverage": cov}


class Flow(unittest.TestCase):
    def test_10_full_path_and_revert(self):
        s = Sim()
        before = s.grease_view()
        self.assertTrue(ok(s.run("master", dry=True), "HP_TINT_MASTER_DRY_RUN_OK"))
        self.assertFalse(s.state["created"])
        self.assertTrue(ok(s.run("master"), "HP_TINT_MASTER_BUILT"))
        self.assertTrue((s.tmp / "Backups/PreHPS03Tint-R002").is_dir())
        # same-call read-back refused: forge the verify run id == build run id
        sys.modules["unreal"] = s.u
        n0 = len(s.u.logs)
        runpy.run_path(str(SCRIPT), init_globals={"HP_TINT_STAGE": "master_verify", "HP_TINT_RUN_ID": "R002"})
        self.assertTrue(any("SAME_CALL_AS_BUILD" in m for m in err(s.u.logs[n0:])))
        s.state["ps_zero"] = True
        logs = s.run("master_verify")
        self.assertTrue(any(m.startswith("HP_TINT_MASTER_PENDING") for k, m in logs) and not ok(logs, "HP_TINT_MASTER_SUCCESS"))
        s.state["ps_zero"] = False
        self.assertTrue(ok(s.run("master_verify"), "HP_TINT_MASTER_SUCCESS"))
        m = s.state["objs"][MASTER]
        self.assertEqual(sorted(m.inputs), ["MP_BASE_COLOR", "MP_OPACITY"])
        for b in range(8):
            want = "HP_TINT_MI_BATCH_DONE|run=R%03d|batch=%d" % (s.calls + 1, b)
            self.assertTrue(ok(s.run("mi_batch"), want))
        self.assertTrue(ok(s.run("mi_batch"), "HP_TINT_MI_BATCH_NOTHING_TO_DO"))
        want = "HP_TINT_MI_SUCCESS|run=R%03d|verified=142" % (s.calls + 1)
        self.assertTrue(ok(s.run("mi_verify"), want))
        self.assertTrue(all(p.startswith(TINT_DIR + "/") for p in s.state["created"] + s.state["saved_assets"]))
        self.assertTrue(ok(s.run("place", dry=True), "HP_TINT_PLACE_DRY_OK"))
        self.assertFalse(s.tagged("HP_S03T"))
        self.assertTrue(any("CONFIRM_MISSING" in m for m in err(s.run("place"))))
        self.assertFalse(s.tagged("HP_S03T"))
        self.assertTrue(ok(s.run("place", confirm="APPLY HPS03T"), "HP_TINT_PLACE_SUCCESS"))
        self.assertEqual(len(s.tagged("HP_S03T")), s.n_grease)
        self.assertEqual(s.state.get("saves"), 1)
        want = "HP_TINT_PLACE_VERIFY_SUCCESS|run=R%03d|paired=%d" % (s.calls + 1, s.n_grease)
        self.assertTrue(ok(s.run("place_verify"), want))
        t0 = s.tagged("HP_S03T")[0]
        self.assertTrue(t0.decal.mat.path.startswith(TINT_DIR + "/MI_HP_S03_t1_"))
        self.assertTrue(any("CONFIRM_MISSING" in m for m in err(s.run("revert"))))
        self.assertTrue(ok(s.run("revert", dry=True), "HP_TINT_REVERT_DRY_OK"))
        self.assertTrue(ok(s.run("revert", confirm="REVERT HPS03T"), "HP_TINT_REVERT_SUCCESS"))
        self.assertFalse(s.tagged("HP_S03T"))
        self.assertEqual(s.grease_view(), before)
        self.assertEqual(s.state.get("saves"), 2)
        self.assertFalse(s.state["dirty"] or s.state["dirty_content"])
        RESULTS["full_path"] = {"twins": s.n_grease, "mis": 142, "saves": 2, "grease_identical_after_revert": True,
                                "same_call_readback_refused": True, "pending_not_success": True}

    def test_11_census_refusal(self):
        s = Sim()
        s.state["dirty_content"].add("/Game/Someone/Else")
        logs = s.run("master")
        self.assertTrue(any("DIRTY_AT_START" in m for m in err(logs)))
        self.assertFalse(s.state["created"])
        s.state["dirty_content"].clear()
        s.state["dirty"] = True                                              # dirty map refuses too
        self.assertTrue(any("DIRTY_AT_START" in m for m in err(s.run("master"))))
        s.state["dirty"] = False
        self.assertTrue(ok(s.run("master"), "HP_TINT_MASTER_BUILT"))         # positive control
        # unexpected content package dirtied mid-place -> no save, twins removed, record .failed
        s2 = Sim()
        s2.build_assets()
        s2.state["fault_dirty_content_on_spawn"] = "/Game/Unexpected/Pkg"
        logs = s2.run("place", confirm="APPLY HPS03T")
        self.assertTrue(any("CENSUS_NOT_EXACT_LEVEL" in m for m in err(logs)))
        self.assertFalse(s2.state.get("saves"))
        self.assertFalse(s2.tagged("HP_S03T"))
        self.assertTrue(list((s2.tmp / "Saved/CodexFlatV3/handprints/grease").glob("hp_grease_tint_place_record.json.failed-*")))
        RESULTS["census"] = {"dirty_content_refused": True, "dirty_map_refused": True, "clean_passes": True,
                             "unexpected_dirty_before_save_refused": True}

    def test_12_record_before_change_and_resume(self):
        s = Sim()
        assert ok(s.run("master"), "HP_TINT_MASTER_BUILT")
        assert ok(s.run("master_verify"), "HP_TINT_MASTER_SUCCESS")
        work = json.loads((HERE / "hp_grease_mi_worklist.json").read_text(encoding="utf-8"))
        b0 = [NS["TINT_MI_PREFIX"] + i["name"][len("MI_HP_S03_g1_"):] for i in work["instances"] if i["batch"] == 0]
        s.state["fault_create"] = b0[2]
        logs = s.run("mi_batch")
        self.assertTrue(any("MI_CREATE_FAILED" in m for m in err(logs)))
        st = s.rec()["stages"]["mi"]
        self.assertEqual(sorted(st["in_progress"]), sorted(b0))              # recorded BEFORE the first create
        self.assertEqual(len([p for p in s.state["created"] if "/MI_" in p]), 2)
        s.state["fault_create"] = None
        s.state["dirty_content"].clear()                                    # (= Don't-Save restart)
        self.assertTrue(ok(s.run("mi_batch"), "HP_TINT_MI_BATCH_DONE|run=R004|batch=0|created=20"))
        mis = [p for p in s.state["created"] if "/MI_" in p]
        self.assertEqual(len(mis), len(set(mis)), "duplicate create")
        self.assertEqual(len(mis), 20)
        # negative control: an existing asset NOT in the record is refused
        b1 = [i for i in work["instances"] if i["batch"] == 1][0]
        s.state["assets"].add(TINT_DIR + "/" + NS["TINT_MI_PREFIX"] + b1["name"][len("MI_HP_S03_g1_"):])
        self.assertTrue(any("MI_EXISTS_UNRECORDED" in m for m in err(s.run("mi_batch"))))
        # place: record + umap backup exist although the FIRST spawn failed
        s2 = Sim()
        s2.build_assets()
        s2.state["fault_spawn_n"] = 1
        logs = s2.run("place", confirm="APPLY HPS03T")
        self.assertTrue(any("SPAWN_FAILED" in m for m in err(logs)))
        failed = list((s2.tmp / "Saved/CodexFlatV3/handprints/grease").glob("hp_grease_tint_place_record.json.failed-*"))
        self.assertEqual(len(failed), 1)
        rec = json.loads(failed[0].read_text(encoding="utf-8"))
        self.assertTrue(Path(rec["backup"], "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap").is_file())
        self.assertEqual(rec["spawned"], 0)
        # static order: the record write precedes the first mutation in both writers
        for fn, rec_call, first in (("stage_place", "write_json(PLACE_RECORD, rec, exclusive=True)", "spawn_twin("),
                                    ("stage_mi_batch", "write_record(rec)", "create_asset("),
                                    ("stage_master", "write_record(rec)", "build_master(")):
            body = SRC[SRC.index("def %s(" % fn):]
            body = body[:body.index("\ndef ", 1)]
            self.assertLess(body.index(rec_call), body.index(first), fn)
        RESULTS["record_before_change"] = {"mi_in_progress_recorded": True, "resume_no_duplicates": True,
                                           "unrecorded_existing_refused": True, "place_record_and_backup_before_spawn": True,
                                           "static_order": True}

    def test_13_revert_faults_and_gates(self):
        s = Sim()
        s.build_assets()
        moved = s.tagged("HP_S03G")[7]
        moved.loc.x += 1.0                                                  # negative: grease layer changed
        self.assertTrue(any("GREASE_LAYER_CHANGED_SINCE_APPLY" in m for m in err(s.run("place", dry=True))))
        moved.loc.x -= 1.0
        s.state["pie"] = True
        self.assertTrue(any("PIE_OR_SIE_ACTIVE" in m for m in err(s.run("place", dry=True))))
        s.state["pie"] = False
        assert ok(s.run("place", confirm="APPLY HPS03T"), "HP_TINT_PLACE_SUCCESS")
        s.state["fault_destroy"] = s.tagged("HP_S03T")[10].label
        logs = s.run("revert", confirm="REVERT HPS03T")
        self.assertTrue(any("DESTROY_FAILED" in m for m in err(logs)))
        self.assertEqual(s.state.get("saves"), 1)                           # nothing saved
        self.assertTrue(s.state["dirty"])                                   # left for a Don't-Save restart
        RESULTS["revert_gates"] = {"grease_moved_refused": True, "pie_refused": True, "destroy_fault_not_saved": True}

    def test_20_static(self):
        names = set()
        for node in ast.walk(ast.parse(SRC)):
            if isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Name):
                names.add(node.id)
        bad = sorted(n for n in FORBIDDEN if n in names)
        self.assertEqual(bad, [])
        self.assertNotIn("EditorAssetLibrary.load_asset", SRC)
        self.assertNotIn("M_HP_S03_Grease\"", SRC.replace('GREASE_MASTER = ROOT + "/Materials/Grease/M_HP_S03_Grease"', ""))
        # markers only after their asserts: each SUCCESS/BUILT/DONE log is the last log call in its function
        for fn, mk in (("stage_master", "HP_TINT_MASTER_BUILT"), ("stage_master_verify", "HP_TINT_MASTER_SUCCESS"),
                       ("stage_mi_batch", "HP_TINT_MI_BATCH_DONE"), ("stage_mi_verify", "HP_TINT_MI_SUCCESS"),
                       ("stage_place", "HP_TINT_PLACE_SUCCESS"), ("stage_revert", "HP_TINT_REVERT_SUCCESS")):
            body = SRC[SRC.index("def %s(" % fn):]
            body = body[:body.index("\ndef ", 1)]
            tail = body[body.index(mk):]
            self.assertNotIn("require(", tail, fn)
            if fn != "stage_master_verify":
                self.assertLess(body.rindex("end_clean()"), body.index(mk), fn)
        work = json.loads((HERE / "hp_grease_mi_worklist.json").read_text(encoding="utf-8"))
        names = [NS["TINT_MI_PREFIX"] + i["name"][len("MI_HP_S03_g1_"):] for i in work["instances"]]
        self.assertEqual(len(set(names)), 142)
        self.assertLessEqual(max(sum(1 for i in work["instances"] if i["batch"] == b) for b in range(8)), 20)
        for f in HERE.glob("hp_grease_tint_*_request.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(d["arguments"]["tool_name"], "ExecuteProjectPythonFile")
            self.assertTrue((HERE.parents[2] / d["arguments"]["arguments"]["relativeSavedPath"]).is_file(), f.name)
        RESULTS["static"] = {"forbidden": 0, "markers_after_asserts": True, "names_unique": 142, "requests_resolve": True}


if __name__ == "__main__":
    r = unittest.main(exit=False, verbosity=1).result
    rep = {"ran": r.testsRun, "failures": len(r.failures), "errors": len(r.errors), "results": RESULTS}
    (HERE / "test_hp_grease_tint_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("HP_TINT_HARNESS|ran=%d|failures=%d|errors=%d" % (r.testsRun, len(r.failures), len(r.errors)))
