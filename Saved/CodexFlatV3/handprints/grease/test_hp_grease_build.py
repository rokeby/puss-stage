"""Offline harness for the grease BUILD (assets script, placer, worklist, marble patch) with +/- controls.

  python test_hp_grease_build.py         writes test_hp_grease_build_report.json

Behavioural tests run the REAL hp_place_grease.py (runpy) against fake_unreal.py: a temp project holding copies of
the two tables + walls file, a dummy umap, the 449 stain decals of placement_S03.json and the two wall actors.
Static tests parse the editor scripts (AST / source order).  The marble patch is checked with `git apply --check`
and its new functions are executed against temp records.
"""
from __future__ import annotations

import ast
import copy
import glob
import hashlib
import json
import os
import random
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fake_unreal  # noqa: E402
import hp_grease_worklist as wl  # noqa: E402

PLACER = HERE / "hp_place_grease.py"
ASSETS = HERE / "hp_grease_assets.py"
BENCH = PROJECT / "Saved/CodexConductor/S3MarbleGrime/s3mg_bench.py"
TILING = PROJECT / "Saved/CodexConductor/s3_marble_tiling_apply.py"
PATCH = HERE / "s3_marble_tiling_apply_hp_layer.patch"
GREASE_TABLE = HERE.parent / "clamber/placement_S03_grease.json"
STAIN_TABLE = PROJECT / "DerivedAssets/FlatV3/HandPrints/placement_S03.json"
WALLS = PROJECT / "DerivedAssets/FlatV3/HandPrints/walls_S03.json"
RESULTS = {}
FORBIDDEN = ("reload_packages", "load_level", "load_map", "delete_asset", "delete_material_expression",
             "save_dirty_packages", "save_all", "EditorLevelLibrary", "end_play_map", "request_end_play_map")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def const(src, name):
    return re.search(r'^%s = "([^"]+)"' % name, src, re.M).group(1)


def func_src(src, name):
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return ast.get_source_segment(src, n)
    raise KeyError(name)


def forbidden(src):
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return sorted(n for n in FORBIDDEN if n in names)


# ------------------------------------------------------------------------------------------------ fake project
class Sim:
    def __init__(self, n_stains=449, extra_actor=None):
        self.tmp = Path(tempfile.mkdtemp(prefix="hpg_"))
        p = self.tmp
        for src, rel in ((STAIN_TABLE, "DerivedAssets/FlatV3/HandPrints/placement_S03.json"),
                         (WALLS, "DerivedAssets/FlatV3/HandPrints/walls_S03.json"),
                         (GREASE_TABLE, "Saved/CodexFlatV3/handprints/clamber/placement_S03_grease.json")):
            (p / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, p / rel)
        umap = p / "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
        umap.parent.mkdir(parents=True)
        umap.write_bytes(b"UMAP-dummy")
        grease = json.loads(GREASE_TABLE.read_text(encoding="utf-8"))
        mis = sorted({r["material_instance"] for r in grease["decals"]})
        g = p / "Saved/CodexFlatV3/handprints/grease"
        g.mkdir(parents=True)
        (g / "hp_grease_assets_record.json").write_text(json.dumps(
            {"stages": {"master": {"verified": True}, "mi": {"verified": True, "done": mis}}}), encoding="utf-8")
        self.state = {"project": str(p).replace("\\", "/"), "dirty": False}
        self.u = fake_unreal.make(self.state)
        u = self.u
        self.state["assets"] = {grease["material"]["mi_dir"] + "/" + m for m in mis}
        walls = {}
        for w in json.loads(WALLS.read_text(encoding="utf-8"))["walls"]:
            t = w["actor_transform"]
            a = u.StaticMeshActor(u.Vector(*t["location"]), u.Rotator(*t["rotation_rpy"]))
            a.label = w["attach_actor_label"]
            self.state["actors"].append(a)
            walls[w["id"]] = a
        stain = json.loads(STAIN_TABLE.read_text(encoding="utf-8"))["decals"][:n_stains]
        for d in stain:
            a = u.DecalActor(u.Vector(*d["location"]), u.Rotator(**d["rotation"]))
            a.label, a.folder, a.tags = d["label"], "HandPrints/S03", ["HP_S03", "HP_S03.run.115927"]
            mi = "/Game/Scenes/Scene3/HandPrints/Materials/V3/" + d["material_instance"]
            self.state["assets"].add(mi)
            a.decal.mat = fake_unreal.Asset(mi)
            a.decal.props.update({"decal_size": u.Vector(*d["decal_size"]), "sort_order": d["sort_order"],
                                  "fade_screen_size": 0.0, "mobility": "MOVABLE"})
            a.parent = walls[d["wall"]]
            self.state["actors"].append(a)
        if extra_actor:
            a = u.StaticMeshActor(u.Vector(0, 0, 0), u.Rotator())
            a.label = extra_actor
            self.state["actors"].append(a)
        self.state["dirty"] = False

    def run(self, mode, confirm=None):
        sys.modules["unreal"] = self.u
        g = {"HP_GREASE_MODE": mode}
        if confirm is not None:
            g["HP_GREASE_CONFIRM"] = confirm
        n0 = len(self.u.logs)
        runpy.run_path(str(PLACER), init_globals=g)
        return self.u.logs[n0:]

    def tagged(self, t):
        return [a for a in self.state["actors"] if t in a.tags]

    def stain_view(self):
        """Everything the tools key on, per stain label (object names excluded on purpose)."""
        out = {}
        for a in self.tagged("HP_S03"):
            out[a.label] = (a.folder, tuple(a.tags), tuple(round(v, 3) for v in (a.loc.x, a.loc.y, a.loc.z)),
                            tuple(round(v, 4) for v in (a.rot.roll, a.rot.pitch, a.rot.yaw)),
                            a.parent.label if a.parent else None, a.decal.mat.path,
                            tuple(round(v, 3) for v in (a.decal.props["decal_size"].x, a.decal.props["decal_size"].y,
                                                         a.decal.props["decal_size"].z)),
                            a.decal.props["sort_order"], a.decal.props["fade_screen_size"])
        return out

    def record(self):
        return self.tmp / "Saved/CodexFlatV3/handprints/grease/hp_place_grease_record.json"


def marker(logs, prefix):
    return [m for k, m in logs if m.startswith(prefix)]


# ------------------------------------------------------------------------------------------------ tests
class Placer(unittest.TestCase):
    def test_01_dry_mutates_nothing(self):
        s = Sim()
        before = s.stain_view()
        logs = s.run("DRY")
        self.assertTrue(marker(logs, "HP_S03G_DRY_OK"), logs)
        self.assertEqual(s.stain_view(), before)
        self.assertFalse(s.state["dirty"])
        self.assertFalse((s.tmp / "Backups").exists())
        RESULTS["dry"] = {"ok": True, "marker": marker(logs, "HP_S03G_DRY_OK")[0][:90]}

    def test_02_confirm_gate(self):
        s = Sim()
        logs = s.run("APPLY")
        self.assertTrue(any("CONFIRM_MISSING" in m for _, m in logs))                   # + control
        self.assertEqual(len(s.tagged("HP_S03")), 449)
        self.assertFalse(s.state["dirty"])
        RESULTS["confirm_gate"] = {"refused_without_confirm": True}

    def test_03_apply_then_revert_exact(self):
        s = Sim()
        before = s.stain_view()
        logs = s.run("APPLY", "APPLY HPS03G")
        ok = marker(logs, "HP_S03G_APPLY_SUCCESS")
        self.assertTrue(ok, logs[-3:])
        grease = json.loads(GREASE_TABLE.read_text(encoding="utf-8"))["decals"]
        self.assertEqual(len(s.tagged("HP_S03")), 0)
        self.assertEqual(len(s.tagged("HP_S03G")), len(grease))
        self.assertEqual(s.state["saves"], 1)
        self.assertFalse(s.state["dirty"])
        rec = json.loads(s.record().read_text(encoding="utf-8"))
        self.assertTrue(rec["saved"] and len(rec["stain_snapshot"]) == 449)
        self.assertTrue(list((s.tmp / "Backups").glob("PreHPS03Grease-*")))
        walls = {a.label: a for a in s.state["actors"] if a.label.startswith("S3 Hangar")}
        g0 = next(a for a in s.tagged("HP_S03G") if a.label == grease[0]["label"])
        self.assertIs(g0.parent, walls[grease[0]["attach_actor_label"]])
        self.assertEqual(g0.folder, "HandPrints/S03_Grease")
        self.assertEqual(g0.decal.mat.path, json.loads(GREASE_TABLE.read_text(encoding="utf-8"))["material"]["mi_dir"]
                         + "/" + grease[0]["material_instance"])
        logs = s.run("GREASE_REVERT", "GREASE_REVERT HPS03G")
        self.assertTrue(marker(logs, "HP_S03G_REVERT_SUCCESS"), logs[-3:])
        self.assertEqual(s.stain_view(), before)                                       # exact restore
        self.assertEqual(len(s.tagged("HP_S03G")), 0)
        self.assertEqual(s.state["saves"], 2)
        arch = glob.glob(str(s.record()) + ".reverted-*")
        self.assertEqual(len(arch), 1)
        a = json.loads(Path(arch[0]).read_text(encoding="utf-8"))
        self.assertNotEqual(a["stain_digest_after_restore"], a["stain_digest_before"])   # object names are new
        RESULTS["apply_revert"] = {"apply_marker": ok[0][:80], "grease": len(grease), "stain_restored_exact": True,
                                   "saves": 2, "digest_before_vs_after_restore_differ_by_object_path": True}

    def test_04_revert_readback_fails_closed(self):
        s = Sim()
        s.run("APPLY", "APPLY HPS03G")
        s.state["fault_drop_tag"] = "HP_S03.run.115927"                                # + control: a lossy restore
        logs = s.run("GREASE_REVERT", "GREASE_REVERT HPS03G")
        self.assertTrue(any("RESTORE_READBACK" in m for _, m in logs), logs[-2:])
        self.assertEqual(s.state["saves"], 1)                                          # nothing saved
        self.assertTrue(s.state["dirty"])
        self.assertEqual(len(s.tagged("HP_S03")), 0)                                   # restored ones destroyed
        RESULTS["revert_fault"] = {"caught": "RESTORE_READBACK", "saved": False}

    def test_05_apply_fault_before_save(self):
        s = Sim()
        first = json.loads(STAIN_TABLE.read_text(encoding="utf-8"))["decals"][100]["label"]
        s.state["fault_destroy"] = first                                               # + control
        logs = s.run("APPLY", "APPLY HPS03G")
        self.assertTrue(any("DESTROY_FAILED" in m for _, m in logs))
        self.assertEqual(s.state.get("saves", 0), 0)
        self.assertEqual(len(s.tagged("HP_S03G")), 0)
        self.assertTrue(list(s.record().parent.glob("hp_place_grease_record.json.failed-*")))
        self.assertFalse(s.record().exists())
        s2 = Sim(extra_actor="ZZ_bench_leftover")                                      # + control: ZZ_ guard
        logs = s2.run("APPLY", "APPLY HPS03G")
        self.assertTrue(any("TEMP_ACTORS_PRESENT_REFUSING_SAVE" in m for _, m in logs))
        self.assertEqual(s2.state.get("saves", 0), 0)
        RESULTS["apply_faults"] = {"destroy_fault_not_saved": True, "zz_actor_refuses_save": True}

    def test_06_refuses_wrong_stain_layer(self):
        s = Sim(n_stains=448)                                                          # - control
        logs = s.run("DRY")
        self.assertTrue(any("STAIN_COUNT" in m for _, m in logs))
        s = Sim()
        s.state["actors"][0].loc = fake_unreal.Vector(s.state["actors"][0].loc.x + 3, s.state["actors"][0].loc.y,
                                                       s.state["actors"][0].loc.z)
        logs = s.run("DRY")
        self.assertTrue(any("WALL_MOVED_SINCE_TABLE" in m for _, m in logs))
        RESULTS["stain_layer_gates"] = {"448_refused": True, "wall_moved_refused": True}


class Static(unittest.TestCase):
    def test_10_pins(self):
        p, a = PLACER.read_text(encoding="utf-8"), ASSETS.read_text(encoding="utf-8")
        self.assertEqual(const(p, "TABLE_SHA256"), sha(GREASE_TABLE))
        self.assertEqual(const(p, "STAIN_TABLE_SHA256"), sha(STAIN_TABLE))
        self.assertEqual(const(a, "WORKLIST_SHA256"), sha(HERE / "hp_grease_mi_worklist.json"))
        self.assertEqual(const(a, "ATLAS_PNG_SHA256"),
                         sha(PROJECT / "DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png"))
        RESULTS["pins"] = {"all_match": True}

    def test_11_graph_is_the_bench_graph(self):
        a, b = ASSETS.read_text(encoding="utf-8"), BENCH.read_text(encoding="utf-8")
        ga, gb = {}, {}
        exec(compile(ast.Module(body=[n for n in ast.parse(a).body if isinstance(n, ast.Assign) and
                                      n.targets[0].id in ("CUSTOM", "GREASE", "ATLAS_PARAMS", "MASTER_SCALARS")],
                                type_ignores=[]), "a", "exec"), ga)
        exec(compile(ast.Module(body=[n for n in ast.parse(b).body if isinstance(n, ast.Assign) and
                                      getattr(n.targets[0], "id", "") in ("CUSTOM", "GREASE", "ATLAS_PARAMS", "MASTER_SCALARS")],
                                type_ignores=[]), "b", "exec"), gb)
        for k in ("CUSTOM", "GREASE", "ATLAS_PARAMS", "MASTER_SCALARS"):
            self.assertEqual(ga[k], gb[k], k)
        body = func_src(a, "build_master")
        props = re.findall(r"g\.prop\([^)]*MP\.(MP_\w+)\)", body)
        self.assertEqual(sorted(props), ["MP_NORMAL", "MP_OPACITY", "MP_ROUGHNESS"])
        doctored = body.replace('g.prop(nn, "", MP.MP_NORMAL)', 'g.prop(nn, "", MP.MP_NORMAL)\n    g.prop(op, "", MP.MP_BASE_COLOR)')
        self.assertIn("MP_BASE_COLOR", re.findall(r"g\.prop\([^)]*MP\.(MP_\w+)\)", doctored))   # + control
        self.assertLess(body.index("BLEND_TRANSLUCENT"), body.index("MD_DEFERRED_DECAL"))
        self.assertIn("MP_BASE_COLOR) is None", func_src(a, "stage_master_verify"))
        RESULTS["graph"] = {"custom_nodes_equal_bench": True, "outputs": sorted(props), "base_color": "none"}

    def test_12_forbidden_calls_and_order(self):
        for f in (PLACER, ASSETS):
            self.assertEqual(forbidden(f.read_text(encoding="utf-8")), [], f.name)
        self.assertEqual(forbidden("unreal.EditorLoadingAndSavingUtils.reload_packages([x])"), ["reload_packages"])
        p = PLACER.read_text(encoding="utf-8")
        apply_src = func_src(p, "do_apply")
        self.assertLess(apply_src.index("backup_level("), apply_src.index("write_record(rec, exclusive=True)"))
        self.assertLess(apply_src.index("write_record(rec, exclusive=True)"), apply_src.index("destroy_actor"))
        gate = func_src(p, "save_level_gated")
        self.assertLess(gate.index("TEMP_ACTORS_PRESENT_REFUSING_SAVE"), gate.index("save_current_level"))
        for fn, mk in (("do_apply", "HP_S03G_APPLY_SUCCESS"), ("do_revert", "HP_S03G_REVERT_SUCCESS")):
            s = func_src(p, fn)
            self.assertGreater(s.index(mk), s.rindex("require("), fn)
        a = ASSETS.read_text(encoding="utf-8")
        for fn, mk in (("stage_texture_verify", "HP_GREASE_TEXTURE_SUCCESS"),
                       ("stage_master_verify", "HP_GREASE_MASTER_SUCCESS"), ("stage_mi_verify", "HP_GREASE_MI_SUCCESS")):
            s = func_src(a, fn)
            self.assertGreater(s.index(mk), s.rindex("require("), fn)
        for fn in ("stage_texture", "stage_master", "stage_mi_batch"):         # create calls never claim SUCCESS
            self.assertNotIn("SUCCESS", func_src(a, fn), fn)
            s = func_src(a, fn)
            self.assertLess(s.index("write_record(rec)"),
                            min(s.index(x) for x in ("import_asset_tasks", "build_master(", "create_asset(") if x in s))
        tex = func_src(a, "stage_texture")
        self.assertEqual(tex.count("AssetImportTask()"), 1)                     # one import per call
        for fn in ("stage_texture_verify", "stage_master_verify", "stage_mi_verify"):
            self.assertNotIn("EditorAssetLibrary.load_asset", func_src(a, fn), fn)   # unreal.load_asset only
        RESULTS["static"] = {"forbidden": 0, "record_before_mutation": True, "zz_before_save": True,
                             "markers_after_asserts": True, "create_calls_never_claim_success": True}

    def test_13_worklist(self):
        doc = wl.build()
        self.assertEqual(wl.dumps(doc), (HERE / "hp_grease_mi_worklist.json").read_bytes())
        grease = json.loads(GREASE_TABLE.read_text(encoding="utf-8"))
        names = {i["name"]: i for i in doc["instances"]}
        self.assertEqual(set(names), {r["material_instance"] for r in grease["decals"]})
        for r in grease["decals"]:
            i = names[r["material_instance"]]
            self.assertEqual([i["scalars"][k] for k in ("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize")], r["grease_uv_rect"])
        sizes = {}
        for i in doc["instances"]:
            sizes[i["batch"]] = sizes.get(i["batch"], 0) + 1
        self.assertLessEqual(max(sizes.values()), 20)
        bad = copy.deepcopy(grease)
        bad["decals"][1]["material_instance"] = bad["decals"][0]["material_instance"]
        bad["decals"][1]["grease_uv_rect"] = [0.0, 0.0, 0.5, 0.5]
        tmp = Path(tempfile.mkdtemp()) / "t.json"
        tmp.write_text(json.dumps(bad), encoding="utf-8")
        if bad["decals"][0]["grease_uv_rect"] != [0.0, 0.0, 0.5, 0.5]:
            with self.assertRaises(SystemExit):                                  # + control: inconsistent rows
                wl.build(tmp)
        RESULTS["worklist"] = {"count": doc["count"], "batches": doc["batches"], "max_batch": max(sizes.values())}


class MarblePatch(unittest.TestCase):
    def test_20_patch_applies_and_behaves(self):
        r = subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=str(PROJECT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        tmp = Path(tempfile.mkdtemp())
        shutil.copy2(TILING, tmp / "s3_marble_tiling_apply.py")
        r = subprocess.run(["git", "apply", "--unsafe-paths", "--directory=" + str(tmp).replace("\\", "/"),
                            "-p3", str(PATCH)], cwd=str(tmp), capture_output=True, text=True)
        if r.returncode != 0:                                                    # fallback: plain patch on the copy
            r = subprocess.run(["git", "apply", "-p3", str(PATCH)], cwd=str(tmp), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        src = (tmp / "s3_marble_tiling_apply.py").read_text(encoding="utf-8")
        ast.parse(src)
        self.assertEqual(TILING.read_text(encoding="utf-8").count("HP_GREASE_TAG"), 0)   # working tree untouched
        rec = tmp / "grease_record.json"
        ns = {"os": os, "json": json, "hashlib": hashlib, "PlanError": ValueError, "HP_TAG": "HP_S03",
              "HP_EXPECTED": 449, "HP_GREASE_TAG": "HP_S03G", "HP_GREASE_RECORD": str(rec)}
        for fn in ("hp_layer", "hp_restored_digest_ok", "_hp_gate", "hp_digest"):
            exec(func_src(src, fn), ns)
        self.assertEqual(ns["hp_layer"](), ("HP_S03", 449))
        rec.write_text(json.dumps({"saved": True, "count_after_save": 1034}), encoding="utf-8")
        self.assertEqual(ns["hp_layer"](), ("HP_S03G", 1034))
        rows = [{"tag": "HP_S03G", "label": "x%d" % i} for i in range(1034)]
        ns["_hp_gate"](rows)
        with self.assertRaises(ValueError):                                      # + control: a stain decal left over
            ns["_hp_gate"](rows[:-1] + [{"tag": "HP_S03", "label": "HP_S03 L 0001"}])
        with self.assertRaises(ValueError):
            ns["_hp_gate"](rows[:-1])
        rec.unlink()
        Path(str(rec) + ".reverted-20261008-010101").write_text(json.dumps(
            {"stain_digest_before": "A", "stain_digest_after_restore": "B"}), encoding="utf-8")
        self.assertTrue(ns["hp_restored_digest_ok"]("B", "A"))
        self.assertFalse(ns["hp_restored_digest_ok"]("C", "A"))                  # + control
        # the placer's digest is byte-identical to the tiling tool's
        pl = {"hashlib": hashlib}
        exec(func_src(PLACER.read_text(encoding="utf-8"), "hp_digest"), pl)
        rng = random.Random(7)
        rows = [{"object_path": "p%d" % i, "parent_label": "W", "location": [rng.uniform(-1e4, 1e4) for _ in range(3)],
                 "rotation": [rng.uniform(-180, 180) for _ in range(3)], "scale": [1.0, 1.0, 1.0]} for i in range(50)]
        self.assertEqual(pl["hp_digest"](rows), ns["hp_digest"](rows))
        rows[3]["location"][0] += 0.02
        self.assertNotEqual(pl["hp_digest"](rows), ns["hp_digest"](rows[:3] + [dict(rows[3], location=[rows[3]["location"][0] - 0.02] + rows[3]["location"][1:])] + rows[4:]))
        RESULTS["marble_patch"] = {"git_apply_check": True, "parses": True, "layer_switch": True,
                                   "foreign_layer_refused": True, "restore_chain": True, "digest_identical": True}


if __name__ == "__main__":
    prog = unittest.main(exit=False, verbosity=1)
    res = prog.result
    rep = {"ran": res.testsRun, "failures": len(res.failures), "errors": len(res.errors), "results": RESULTS}
    (HERE / "test_hp_grease_build_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("HP_GREASE_BUILD_TESTS|ran=%d|fail=%d|err=%d" % (res.testsRun, len(res.failures), len(res.errors)))
    sys.exit(0 if res.wasSuccessful() else 1)
