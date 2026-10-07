"""Offline harness for the P06 realism v2 import kit (system Python; no Unreal).

  python test_p06_import_offline.py   -> PASS/FAIL per check, writes test_p06_import_offline_report.json

The REAL plan is built from the real manifest / build report / sidecars / validation / mi_params / edge probes on disk
(positive control).  Faults are injected by patching core.load_json / core.sha_file for one file (negative controls).
A FakeOps stands in for UnrealOps to drive the DRY / APPLY / VERIFY / UNDO_LIST orchestration, with a fault switch
per gate.  What this harness CANNOT prove [inf]: that Interchange honours the LodGroup, that the slot_a / pilot
helpers behave in UE 5.8 as they did on 2 Oct, the texture-property string forms, the collision count, or memory
use -- the live DRY (read APIs exercised on the reference mesh) and each batch's asserted read-back exist for that.
"""
import ast
import copy
import importlib.util
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load("p06imp_core_t", os.path.join(HERE, "p06_import_core.py"))
app = _load("p06imp_app_t", os.path.join(HERE, "p06_import.py"))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append({"check": name, "pass": bool(cond), "detail": str(detail)[:300]})
    print("%s  %s %s" % ("PASS" if cond else "FAIL", name, ("" if cond else str(detail)[:300])))


def expect_stop(name, fn, token):
    try:
        fn()
    except core.PlanError as exc:
        check(name, token in str(exc), exc)
        return str(exc)
    check(name, False, "did not stop (wanted %s)" % token)
    return None


class Patch:
    """Patch core.load_json / core.sha_file for paths ending with `suffix`."""

    def __init__(self, suffix, mutate=None, sha=None):
        self.suffix, self.mutate, self.sha = suffix.replace("\\", "/"), mutate, sha

    def __enter__(self):
        self.lj, self.sf = core.load_json, core.sha_file
        lj, sf = self.lj, self.sf

        def load_json(path):
            doc = lj(path)
            if self.mutate and path.replace("\\", "/").endswith(self.suffix):
                doc = copy.deepcopy(doc)
                self.mutate(doc)
            return doc

        def sha_file(path):
            if self.sha and path.replace("\\", "/").endswith(self.suffix):
                return self.sha
            return sf(path)
        core.load_json, core.sha_file = load_json, sha_file
        return self

    def __exit__(self, *a):
        core.load_json, core.sha_file = self.lj, self.sf


def refusals_with(suffix, mutate=None, sha=None, **kw):
    with Patch(suffix, mutate, sha):
        return core.build_plan(PROJECT, **kw)["refusals"]


# =====================================================================================================================
# Fake editor
# =====================================================================================================================

GOOD_REF = {"mesh_slots": [["Front", "/Game/x/MI_Front_o2p"], ["Flap", "/Game/x/MI_Flap"],
                           ["Timber", core.PARENTS["Timber"]], ["Edge", core.PARENTS["Edge"]]],
            "collision_count": 0, "num_lods": 2, "socket_names": ["SOCKET_Hinge", "SOCKET_Pivot", "SOCKET_Pole_1"],
            "edge_geometry": [{"lod": 0, "front_x": [-15.0, -15.0], "edge_x": [-15.0, -10.0]},
                              {"lod": 1, "front_x": [-15.0, -15.0], "edge_x": [-15.0, -10.0]}],
            "lod0_triangles": 5000, "Front_parent": core.PARENTS["Front"], "Flap_parent": core.PARENTS["Flap"],
            "textures": {k: {p: "v" for p in core.TEXTURE_CMP} for k in core.TEXTURE_KINDS},
            "texture_kind_errors": {}, "parents_exist": {p: True for p in sorted(core.PARENTS.values())}}


class FakeOps:
    def __init__(self):
        self.core = core
        self.logs, self.errors, self.events = [], [], []
        self.assets, self.disk = set(), set()
        self.dirty = {"content": [], "maps": []}
        self.pie = False
        self.ram = 40.0
        self.ref = copy.deepcopy(GOOD_REF)
        self.aged_fail = None
        self.fail_import_at = None        # (owner, reason)
        self.foreign_dirty_on_import = False
        self.fail_save = None             # path
        self.fail_readback = None         # owner
        self.created = []
        self.gc = 0
        self.imports = 0

    def log(self, m):
        self.logs.append(m)
        self.events.append(("log", m))

    def log_error(self, m):
        self.errors.append(m)
        self.events.append(("err", m))

    def project_dir(self):
        return PROJECT

    def guard_context(self):
        if self.pie:
            raise core.PlanError("PIE_OR_SIE_ACTIVE (refused; this tool never ends PIE)")

    def census(self):
        return {"content": sorted(self.dirty["content"]), "maps": sorted(self.dirty["maps"])}

    def free_ram_gb(self):
        return self.ram

    def asset_exists(self, p):
        return p in self.assets

    def package_on_disk(self, p):
        return p in self.disk

    def reference_state(self):
        self.events.append(("ref", None))
        return copy.deepcopy(self.ref)

    def common_aged_state(self):
        if self.aged_fail:
            raise RuntimeError(self.aged_fail)
        return {n: {"ok": True} for n in core.COMMON_AGED}

    def created_packages(self):
        return list(self.created)

    def import_wing(self, w, ref):
        self.imports += 1
        for p in w["packages"]:
            if self.fail_import_at and self.fail_import_at[0] == w["owner"] and "/Materials/" in p:
                raise RuntimeError(self.fail_import_at[1])
            self.assets.add(p)
            self.dirty["content"].append(p)
            self.created.append(p)
            self.events.append(("create", p))
        if self.foreign_dirty_on_import:
            self.dirty["content"].append("/Game/Someone/Else")
        return {"ok": w["owner"]}

    def save_package(self, p):
        self.events.append(("save", p))
        if p == self.fail_save:
            return False
        if p in self.dirty["content"]:
            self.dirty["content"].remove(p)
        self.disk.add(p)
        return True

    def readback_wing(self, w, ref):
        self.events.append(("readback", w["owner"]))
        if self.fail_readback == w["owner"]:
            raise RuntimeError("SLOT_MATERIAL_READBACK_FAIL|fake")
        if not all(p in self.disk for p in w["packages"]):
            raise RuntimeError("FAKE_NOT_ON_DISK")
        return {"ok": True}

    def collect_garbage(self):
        self.gc += 1
        self.events.append(("gc", None))


def fresh():
    return FakeOps(), tempfile.mkdtemp(prefix="p06imp_")


def dry(ops, d, run="P06IMP-T-DRY"):
    return app.run_dry(ops, core, {"mode": "DRY", "confirm": "DRY P06IMPORT"}, run, d)


def apply_(ops, d, plan, k, run=None):
    a = {"mode": "APPLY", "batch": k, "confirm": core.confirm_for("APPLY", plan, k)}
    core.validate_args(a, plan)
    return app.run_apply(ops, core, a, plan, run or "P06IMP-T-B%d" % k, d, k)


def main():
    plan = core.build_plan(PROJECT)
    W = plan["wings"]
    # ---------------------------------------------------------------- P: the real plan
    check("P1 POS real manifest: file gates pass", plan["gates_ok"], plan["refusals"])
    check("P1 POS 15 wings = picks 1 2 3 6 7 8 9 10 25 26 30 33 35 38 39",
          sorted(int(k) for k in W) == list(core.EXPECTED_PICKS))
    check("P1 POS 105 packages (7 per wing), all distinct, all under the Realism root",
          plan["package_count"] == 105 and len({p for w in W.values() for p in w["packages"]}) == 105 and
          all(p.startswith(core.ROOT + "/") for w in W.values() for p in w["packages"]))
    check("P1 POS 5 batches, <= 3 wings each, each pick once", len(plan["batches"]) == 5 and
          all(len(b["picks"]) <= 3 for b in plan["batches"]) and
          sorted(p for b in plan["batches"] for p in b["picks"]) == list(core.EXPECTED_PICKS))
    check("P1 POS mesh folder by variant (rz_build_one.py:296 convention): 10 x T5P, 5 x T5J (30 33 38 39 10)",
          sorted(int(k) for k, w in W.items() if "/Realism/T5J/" in w["destinations"]["mesh"]) == [10, 30, 33, 38, 39]
          and all(w["destinations"]["mesh"].endswith("/" + w["asset"]) for w in W.values()))
    check("P1 POS pick 10 owner is P06_real_10_building_under_construct_R (t5j)",
          W["10"]["owner"] == "P06_real_10_building_under_construct_R" and W["10"]["variant"] == "t5j")
    check("P1 POS pick 1 takes the hole-filled SkinColor_o2p, others _o2 (as the manifest says)",
          W["1"]["destinations"]["SkinColor"].endswith("_SkinColor_o2p") and
          all(w["destinations"]["SkinColor"].endswith("_SkinColor_o2") for k, w in W.items() if k != "1"))
    check("P1 POS chain slabs 26 30 25 in batch 1", plan["batches"][0]["picks"] == [26, 30, 25])
    check("P1 POS slot materials = Front MI, Flap MI, CanvasEdge v1 (Timber), CanvasEdge v3 (Edge)",
          all(w["expected"]["slot_materials"][2:] == [core.PARENTS["Timber"], core.PARENTS["Edge"]] and
              w["expected"]["slot_materials"][3].endswith("M_Wing_CanvasEdge_Master_v3") for w in W.values()))
    check("P1 POS picks 2 and 3 carry the socket_contract note (sidecar + baked poles have Pole_2)",
          W["2"]["notes"] and W["3"]["notes"] and not W["1"]["notes"])
    check("P1 POS heights: every wing bounds z -100..1020 (= manifest 1000 + pole 20, foot -100)",
          all(not core.height_gate(w["expected"]["bounds_cm"], w["height_cm"], w["expected"]["pole"]) for w in W.values()))
    rec = core.load_json(os.path.join(PROJECT, core.COMMON_AGED_RECORD_REL))["common_hashes"]["P06"]
    check("P2 MEAS aged Common PNGs byte-identical to the set FV3P06I-20261002-04 imported (reuse is lossless)",
          all(rec[n] == [core.sha_file(os.path.join(PROJECT, os.path.dirname(w["sources"]["AgedStencil"]["rel"]), n + ".png"))]
              for w in W.values() for n in core.COMMON_AGED))
    # ---------------------------------------------------------------- N: file-gate negative controls
    mrel = core.MANIFEST_REL

    def m_fbx_sha(doc):
        doc["meshes"][0]["fbx_sha256"] = "0" * 64
    r = refusals_with(mrel, m_fbx_sha)
    check("N1 NEG manifest FBX sha tampered -> SOURCE_HASH_MISMATCH", any("SOURCE_HASH_MISMATCH" in x for x in r), r)
    r = refusals_with(W["26"]["sources"]["SkinMask"]["rel"], sha="f" * 64)
    check("N1 NEG a texture changed on disk after the manifest -> SOURCE_HASH_MISMATCH",
          any("SOURCE_HASH_MISMATCH pick 26 SkinMask" in x for x in r), r)
    r = core.build_plan(PROJECT, batches=((26, 30, 25, 35), (38, 39), (33, 1, 3), (6, 7, 2), (8, 9, 10)))["refusals"]
    check("N2 NEG a 4-wing batch -> BATCH_TOO_BIG", any("BATCH_TOO_BIG" in x for x in r), r)
    r = core.build_plan(PROJECT, batches=((26, 30, 25), (35, 38, 39), (33, 1, 3), (6, 7, 2), (8, 9)))["refusals"]
    check("N2 NEG a pick left out of the batches -> BATCHES_DO_NOT_COVER_PICKS_ONCE", any("COVER" in x for x in r), r)

    def m_drop(doc):
        doc["meshes"] = doc["meshes"][1:]
    r = refusals_with(mrel, m_drop)
    check("N3 NEG manifest missing a pick -> PICKS_MISMATCH", any("PICKS_MISMATCH" in x for x in r), r)
    mip = W["30"]["sources"]["mi_params"]["rel"]
    r = refusals_with(mip, lambda d: d["parents"].update({"Front": core.BB + "MI_Billboard_Front_v4"}))
    check("N4 NEG mi_params names a v4 parent -> MI_PARENT_MISMATCH", any("MI_PARENT_MISMATCH pick 30" in x for x in r), r)
    r = refusals_with(core.COMMON_AGED_RECORD_REL,
                      lambda d: d["common_hashes"]["P06"].update({"T_FlatV3_AgedSteel_Color": ["0" * 64]}))
    check("N5 NEG aged Common no longer identical to the P06 set -> AGED_COMMON_HASH",
          sum("AGED_COMMON_HASH" in x for x in r) == 15, r[:2])
    ep = W["35"]["sources"]["edge_probe"]["rel"]

    def m_edge(doc):
        for o in doc[0]["objects"].values():
            o["slots"]["Edge"]["x_max"] = -12.5
    r = refusals_with(ep, m_edge)
    check("N6 NEG edge probe: Edge section not x -15..-10 -> EDGE_PROBE", any("EDGE_PROBE pick 35" in x for x in r), r)
    sc = W["25"]["sources"]["socket"]["rel"]

    def m_pivot(doc):
        [s for s in doc["sockets"] if s["name"] == "SOCKET_Pivot"][0]["relative_location_cm"][2] = 480.0
    r = refusals_with(sc, m_pivot)
    check("N7 NEG pivot socket not at half the manifest height -> PIVOT_Z_VS_MANIFEST_HEIGHT",
          any("PIVOT_Z_VS_MANIFEST_HEIGHT pick 25" in x for x in r), r)
    sc2 = W["2"]["sources"]["socket"]["rel"]
    r = refusals_with(sc2, lambda d: d.update({"sockets": [s for s in d["sockets"] if s["name"] != "SOCKET_Pole_2"]}))
    check("N8 NEG sidecar loses a pole the geometry has -> SOCKET_SIDECAR_VS_BAKED_POLES",
          any("SOCKET_SIDECAR_VS_BAKED_POLES pick 2" in x for x in r), r)
    vrel = W["39"]["sources"]["validation"]["rel"]
    r = refusals_with(vrel, lambda d: d["bounds_m"]["max"].__setitem__(2, 9.9))
    check("N9 NEG validation bounds top 990 cm (not manifest 1000 + 20) -> HEIGHT_VS_MANIFEST",
          any("HEIGHT_VS_MANIFEST" in x and "pick 39" in x for x in r), r)
    r = refusals_with(vrel, lambda d: (d["bounds_m"]["min"].__setitem__(1, 0.5), d["bounds_m"]["max"].__setitem__(1, 4.0)))
    check("N10 NEG an L wing whose geometry extends to -Y (R) -> SIDE_EXTENSION", any("SIDE_EXTENSION pick 39" in x for x in r), r)
    # ---------------------------------------------------------------- G: pure gate helpers
    good = [{"lod": 0, "front_x": [-15, -15], "edge_x": [-15, -10]}, {"lod": 1, "front_x": [-15, -15], "edge_x": [-15, -10]}]
    bad = copy.deepcopy(good)
    bad[1]["edge_x"] = [-15, -12.5]
    check("G1 POS/NEG edge_geometry_ok", core.edge_geometry_ok(good)[0] and not core.edge_geometry_ok(bad)[0] and
          not core.edge_geometry_ok([{"lod": 0, "front_x": [-15, -15], "edge_x": None}])[0])
    check("G2 POS/NEG census_exact: only this batch's packages, no map",
          core.census_exact({"content": ["/b", "/a"], "maps": []}, ["/a", "/b"]) and
          not core.census_exact({"content": ["/a", "/b", "/c"], "maps": []}, ["/a", "/b"]) and
          not core.census_exact({"content": ["/a", "/b"], "maps": ["/m"]}, ["/a", "/b"]) and
          not core.census_exact({"content": ["/a"], "maps": []}, ["/a", "/b"]))
    # ---------------------------------------------------------------- A: args
    expect_stop("A1 NEG DRY confirm mismatch", lambda: core.validate_args({"mode": "DRY", "confirm": "DRY"}), "CONFIRM_MISMATCH")
    expect_stop("A2 NEG APPLY batch 0", lambda: core.validate_args({"mode": "APPLY", "batch": 0, "confirm": "x"}, plan),
                "BATCH_INVALID")
    expect_stop("A2 NEG APPLY batch 6", lambda: core.validate_args({"mode": "APPLY", "batch": 6, "confirm": "x"}, plan),
                "BATCH_INVALID")
    expect_stop("A2 NEG APPLY batch 'next'", lambda: core.validate_args({"mode": "APPLY", "batch": "next"}, plan),
                "BATCH_INVALID")
    expect_stop("A3 NEG APPLY confirm of another batch", lambda: core.validate_args(
        {"mode": "APPLY", "batch": 2, "confirm": core.confirm_for("APPLY", plan, 1)}, plan), "CONFIRM_MISMATCH")
    check("A4 POS APPLY confirm carries the plan hash", core.validate_args(
        {"mode": "APPLY", "batch": 3, "confirm": "APPLY P06IMPORT BATCH 3 #" + plan["inputs_hash"][:8]}, plan) == ("APPLY", 3))
    expect_stop("A5 NEG unknown mode", lambda: core.validate_args({"mode": "REVERT", "confirm": "x"}), "MODE_INVALID")
    # ---------------------------------------------------------------- D: DRY
    ops, d = fresh()
    ops.dirty["content"] = ["/Game/Other"]
    expect_stop("D1 NEG dirty census at start", lambda: dry(ops, d), "DIRTY_CENSUS")
    ops, d = fresh()
    ops.pie = True
    expect_stop("D2 NEG PIE running", lambda: dry(ops, d), "PIE_OR_SIE_ACTIVE")
    for label, mut, token in (
            ("a target already exists", lambda o: o.assets.add(W["7"]["destinations"]["Flap"]), "CREATE_ONLY_TARGETS_EXIST"),
            ("reference Edge slot still v1", lambda o: o.ref["mesh_slots"][3].__setitem__(1, core.PS + "M_Wing_CanvasEdge_Master"),
             "REFERENCE_TIMBER_EDGE"),
            ("reference Front MI moved to v4", lambda o: o.ref.update({"Front_parent": core.BB + "MI_Billboard_Front_v4"}),
             "REFERENCE_MI_PARENT"),
            ("a parent asset missing", lambda o: o.ref["parents_exist"].update({core.PARENTS["Edge"]: False}), "PARENT_MISSING"),
            ("reference texture breaks the kind rule", lambda o: o.ref["texture_kind_errors"].update({"SkinMask": "TEXTURE_SETTINGS_FAIL"}),
             "REFERENCE_TEXTURE_KIND"),
            ("reference edge read gives nonsense", lambda o: o.ref["edge_geometry"][0].update({"edge_x": None}), "REFERENCE_EDGE_GEOMETRY"),
            ("aged Common missing", lambda o: setattr(o, "aged_fail", "LOAD_FAIL|Common"), "AGED_COMMON_NOT_READY"),
            ("low RAM", lambda o: setattr(o, "ram", 6.0), "LOW_RAM")):
        ops, d = fresh()
        mut(ops)
        expect_stop("D3 NEG DRY refuses: %s -> %s" % (label, token), lambda: dry(ops, d), token)
        lat = app._read_json(os.path.join(d, app.DRY_LATEST))
        check("D3 NEG ... DRY record written REFUSED (APPLY cannot use it)", lat and lat["status"] == "REFUSED", lat and lat["status"])
    ops, d = fresh()
    doc = dry(ops, d)
    check("D4 POS DRY marker with run id + 5 per-batch confirms logged", any(
        m.startswith("FLATV3_P06IMPORT_DRY_OK|run=P06IMP-T-DRY|wings=15|packages=105") for m in ops.logs) and
        sum("DRY_CONFIRM|run=P06IMP-T-DRY|batch=" in m for m in ops.logs) == 5, ops.logs[:2])
    check("D4 POS DRY left nothing created or dirty", not ops.assets and ops.census() == {"content": [], "maps": []}
          and ops.imports == 0)
    # ---------------------------------------------------------------- X: APPLY negatives
    ops, d = fresh()
    expect_stop("X1 NEG APPLY with no DRY", lambda: apply_(ops, d, plan, 1), "NO_PASSING_DRY")
    ops, d = fresh()
    dry(ops, d)
    lat = app._read_json(os.path.join(d, app.DRY_LATEST))
    lat["inputs_hash"] = "deadbeef" + lat["inputs_hash"][8:]
    app._write_json(os.path.join(d, app.DRY_LATEST), lat)
    expect_stop("X2 NEG plan changed since DRY -> PLAN_STALE", lambda: apply_(ops, d, plan, 1), "PLAN_STALE")
    ops, d = fresh()
    dry(ops, d)
    ops.assets.add(plan["batches"][0]["packages"][4])
    expect_stop("X3 NEG CREATE-ONLY: a batch target appeared after DRY", lambda: apply_(ops, d, plan, 1), "CREATE_ONLY_TARGETS_EXIST")
    check("X3 NEG ... nothing imported", ops.imports == 0)
    ops, d = fresh()
    dry(ops, d)
    ops.ram = 8.0
    expect_stop("X4 NEG free RAM under the floor -> LOW_RAM, before any import", lambda: apply_(ops, d, plan, 1), "LOW_RAM")
    check("X4 NEG ... nothing imported", ops.imports == 0)
    ops, d = fresh()
    dry(ops, d)
    ops.ref["collision_count"] = 1
    expect_stop("X5 NEG reference changed since DRY -> REFERENCE_DRIFT", lambda: apply_(ops, d, plan, 1), "REFERENCE_DRIFT_SINCE_DRY")
    ops, d = fresh()
    dry(ops, d)
    ops.dirty["content"] = ["/Game/Other"]
    expect_stop("X6 NEG dirty census at APPLY start", lambda: apply_(ops, d, plan, 1), "DIRTY_CENSUS")
    ops, d = fresh()
    dry(ops, d)
    ops.fail_import_at = ("P06_real_30_rusty_metal_door_L", "LOD_COUNT_FAIL|fake|1 (FBX LodGroup not honoured?)")
    expect_stop("X7 NEG import gate fails on the 2nd wing -> STOPPED IMPORT_GATE", lambda: apply_(ops, d, plan, 1), "IMPORT_GATE")
    fail = app._read_json(os.path.join(d, "p06_import_apply_b1_P06IMP-T-B1_FAILURE.json"))
    check("X7 NEG ... saved nothing, failure record lists the unsaved packages and asks for a Don't-Save restart",
          not any(e[0] == "save" for e in ops.events) and fail and fail["saved"] == [] and len(fail["created_unsaved"]) >= 7
          and "Don't Save" in fail["next"] and not any("APPLY_OK" in m for m in ops.logs), fail and fail.get("status"))
    check("X7 NEG ... STOPPED marker carries run and batch", any(
        m.startswith("FLATV3_P06IMPORT_STOPPED|run=P06IMP-T-B1|batch=1|") for m in ops.errors), ops.errors[-1:])
    ops, d = fresh()
    dry(ops, d)
    ops.foreign_dirty_on_import = True
    expect_stop("X8 NEG a foreign package dirtied during the import -> DIRTY_SET_NOT_EXACT, nothing saved",
                lambda: apply_(ops, d, plan, 2), "DIRTY_SET_NOT_EXACT")
    check("X8 NEG ... no save call", not any(e[0] == "save" for e in ops.events))
    ops, d = fresh()
    dry(ops, d)
    ops.fail_save = sorted(plan["batches"][0]["packages"])[2]
    expect_stop("X9 NEG save returns False on the 3rd package -> SAVE_OR_READBACK", lambda: apply_(ops, d, plan, 1), "SAVE_FAIL")
    led = app._read_json(os.path.join(d, app.LEDGER_NAME))
    check("X9 NEG ... ledger FAILED_AFTER_SAVE with exactly the 2 saved packages; no OK marker",
          led["batches"]["1"]["status"] == "FAILED_AFTER_SAVE" and len(led["batches"]["1"]["saved"]) == 2 and
          not any("APPLY_OK" in m for m in ops.logs), led)
    ops.fail_save = None
    expect_stop("X9 NEG ... before a restart the editor is still dirty -> refused", lambda: apply_(ops, d, plan, 1), "DIRTY_CENSUS")
    ops.assets, ops.dirty = set(ops.disk), {"content": [], "maps": []}     # Don't-Save restart: unsaved ones vanish
    expect_stop("X9 NEG ... after the restart, re-running that batch is refused (CREATE-ONLY: 2 are on disk)", lambda: apply_(ops, d, plan, 1), "CREATE_ONLY_TARGETS_EXIST")
    ops, d = fresh()
    dry(ops, d)
    ops.fail_readback = "P06_real_25_concrete_wall_with_L"
    expect_stop("X10 NEG read-back fails after the save -> no success marker", lambda: apply_(ops, d, plan, 1), "SAVE_OR_READBACK")
    check("X10 NEG ... no APPLY_OK marker", not any("APPLY_OK" in m for m in ops.logs))
    # ---------------------------------------------------------------- Y: APPLY positive, all 5 batches, VERIFY, UNDO
    ops, d = fresh()
    dry(ops, d)
    v0 = app.run_verify(ops, core, {}, "P06IMP-T-V0", d)
    check("Y0 POS VERIFY before any APPLY -> INCOMPLETE (15 missing), not OK", v0["status"] == "INCOMPLETE" and
          len(v0["missing"]) == 15 and any("VERIFY_INCOMPLETE|run=P06IMP-T-V0" in m for m in ops.errors))
    rec = apply_(ops, d, plan, 1)
    b1 = plan["batches"][0]["packages"]
    saves = [e[1] for e in ops.events if e[0] == "save"]
    check("Y1 POS batch 1 saved exactly its 21 packages, nothing else", sorted(saves) == sorted(b1) and len(b1) == 21, saves[:3])
    ok_i = max(i for i, e in enumerate(ops.events) if e[0] == "log" and "APPLY_OK" in e[1])
    last_save = max(i for i, e in enumerate(ops.events) if e[0] == "save")
    last_rb = max(i for i, e in enumerate(ops.events) if e[0] == "readback")
    gc_i = max(i for i, e in enumerate(ops.events) if e[0] == "gc")
    check("Y1 POS success marker AFTER the last save, the read-back and the GC",
          ok_i > last_save and ok_i > last_rb and ok_i > gc_i and ops.gc == 1, (ok_i, last_save, last_rb, gc_i))
    check("Y1 POS marker = FLATV3_P06IMPORT_APPLY_OK|run=..|batch=1", any(
        m.startswith("FLATV3_P06IMPORT_APPLY_OK|run=P06IMP-T-B1|batch=1|") for m in ops.logs))
    check("Y1 POS census clean after, ledger SAVED", ops.census() == {"content": [], "maps": []} and
          app._read_json(os.path.join(d, app.LEDGER_NAME))["batches"]["1"]["status"] == "SAVED")
    expect_stop("Y2 NEG same batch again -> BATCH_ALREADY_SAVED", lambda: apply_(ops, d, plan, 1, "P06IMP-T-B1b"),
                "BATCH_ALREADY_SAVED")
    v1 = app.run_verify(ops, core, {}, "P06IMP-T-V1", d)
    check("Y3 POS VERIFY after batch 1 -> 3 ok, 12 missing, INCOMPLETE", v1["status"] == "INCOMPLETE" and
          len(v1["ok"]) == 3 and len(v1["missing"]) == 12)
    u = app.run_undo_list(core, PROJECT, d, ops.log)
    check("U1 POS UNDO_LIST after batch 1: 21 packages, MIs first, then the mesh, then textures; auto_delete False",
          not u["auto_delete"] and len(u["batches"]) == 1 and len(u["batches"][0]["delete_in_order"]) == 21 and
          all("/Materials/Instances/" in p for p in u["batches"][0]["delete_in_order"][:6]) and
          all("/T5" in p for p in u["batches"][0]["delete_in_order"][6:9]), u["batches"][0]["delete_in_order"][:8])
    check("U1 POS ... the undo deleted nothing", len([p for p in b1 if p in ops.assets]) == 21)
    for k in (2, 3, 4, 5):
        apply_(ops, d, plan, k)
    v2 = app.run_verify(ops, core, {}, "P06IMP-T-V2", d)
    check("Y4 POS all 5 batches -> VERIFY_OK wings=15", v2["status"] == "PASS" and any(
        m.startswith("FLATV3_P06IMPORT_VERIFY_OK|run=P06IMP-T-V2|wings=15") for m in ops.logs), v2["status"])
    check("Y4 POS 105 packages on disk, 5 GCs, every APPLY marker names its batch",
          len(ops.disk) == 105 and ops.gc == 5 and
          sorted(int(m.split("|batch=")[1].split("|")[0]) for m in ops.logs if "APPLY_OK" in m) == [1, 2, 3, 4, 5])
    ops.ref["Front_parent"] = "/Game/x"
    expect_stop("Y5 NEG VERIFY refuses on a moved reference", lambda: app.run_verify(ops, core, {}, "P06IMP-T-V3", d), "REFERENCE")
    # ---------------------------------------------------------------- S: static source rules
    src = open(os.path.join(HERE, "p06_import.py"), encoding="utf-8").read()
    check("S1 no delete / reload / Save All anywhere in the kit", not any(t in src for t in (
        "delete_asset", "reload_packages", "save_dirty_packages", "save_all", "SaveAll", "delete_directory")))
    tree = ast.parse(src)
    glob_unreal = [n.lineno for n in tree.body if isinstance(n, ast.Assign) and "unreal." in ast.unparse(n.value)]
    check("S2 no unreal object in a module global", not glob_unreal, glob_unreal)
    run_src = open(os.path.join(HERE, "p06_import_run.py"), encoding="utf-8").read()
    check("S3 runner purges the Saved module cache BEFORE running the kit",
          run_src.index("purge_saved_module_cache.py") < run_src.index("p06_import.py\""))
    req = json.load(open(os.path.join(HERE, "p06_import_request.json"), encoding="utf-8"))
    check("S4 request = guarded loopback route, our runner", req["arguments"]["toolset_name"] ==
          "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset" and req["arguments"]["tool_name"] == "ExecuteProjectPythonFile"
          and req["arguments"]["arguments"]["relativeSavedPath"] == "CodexFlatV3/p06import/p06_import_run.py")
    args = json.load(open(os.path.join(HERE, "p06_import_args.json"), encoding="utf-8"))
    check("S5 shipped args = DRY; the confirms it lists match this plan's hash",
          args["mode"] == "DRY" and args["confirm"] == "DRY P06IMPORT" and all(
              v == core.confirm_for("APPLY", plan, int(k)) for k, v in args["expected_confirms_for_this_plan_hash"].items()))
    rep = {"plan_hash": plan["inputs_hash"], "checks": RESULTS, "passed": sum(r["pass"] for r in RESULTS),
           "failed": sum(not r["pass"] for r in RESULTS)}
    with open(os.path.join(HERE, "test_p06_import_offline_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print("RESULT %d passed, %d failed" % (rep["passed"], rep["failed"]))
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
