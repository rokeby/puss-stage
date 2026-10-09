"""Offline harness for the RZIMPORT kit (system Python; no Unreal).

  python test_rzimport_offline.py   -> PASS/FAIL per check, writes test_rzimport_offline_report.json

POSITIVE controls on REAL files: the P06 v2 manifest (already imported 7 Oct: the plan must equal the P06 kit's
destinations exactly AND refuse with DESTINATION_CLASH_WITH_P06_IMPORT -- itself a negative control), and the v1 root
IMPORT_MANIFEST.json (two P02 12 m wings, never imported) which must pass every file gate at 1200 cm.
SYNTHETIC fixtures (temp dir, absolute paths; aged textures = the real P06 PNGs so the hash gate is exercised for
real): a P02 manifest (12 m L + R wings) and a VAL manifest (two top-border valances), then one fault per negative
control.  geometry_verdict (the mount-aware mesh gate) is driven directly with measurements derived from each
plan's expectations (+) and single faults (-).  A FakeOps drives DRY / APPLY / VERIFY / UNDO_LIST.
What this harness CANNOT prove [inf]: Interchange behaviour on a top-border FBX, the slot_a/pilot reads in UE 5.8 on a
socket-less mesh, texture property string forms, collision counts, memory use.  The live DRY + each batch's
read-back exist for that; VERIFY on the P06 manifest (read-only) is the live positive control of the generalised gate.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RZ = "DerivedAssets/FlatV3/Realism_20261007"
P06_MANIFEST = RZ + "/P06_backrooms/P06_IMPORT_MANIFEST_v2.json"
V1_MANIFEST = RZ + "/IMPORT_MANIFEST.json"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


core = _load("rzimp_core_t", os.path.join(HERE, "rzimport_core.py"))
app = _load("rzimp_app_t", os.path.join(HERE, "rzimport.py"))
p06core = _load("p06imp_core_for_rz_t", os.path.join(HERE, "..", "p06import", "p06_import_core.py"))
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


def sha(path):
    return core.sha_file(path)


# =====================================================================================================================
# Synthetic fixtures
# =====================================================================================================================

P06_AGED = None


def _real_aged():
    global P06_AGED
    if P06_AGED is None:
        m = core.load_json(os.path.join(PROJECT, P06_MANIFEST))
        P06_AGED = [{"path": a["path"], "sha256": a["sha256"]} for a in m["meshes"][0]["aged_textures"]]
    return P06_AGED


def _wj(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    return path


def _wb(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


def make_entry(root, passage, owner, side, mount, height_cm, width_cm, variant="t5p", art_top_cm=None, mut=None):
    """One synthetic manifest entry with every file the core reads.  mut(dict of docs) may alter them first."""
    item = (root + "/%s/%s_v2" % (passage, owner)).replace("\\", "/")
    asset = "SM_FlatV3_%s_%s" % (owner, variant)
    W = width_cm / 100.0
    H = height_cm / 100.0
    top = (art_top_cm / 100.0) if art_top_cm is not None else H
    if mount == "wing":
        y0, y1 = (-W, -0.0128) if side == "L" else (0.0128, W)          # FBX frame: L extends to -Y
        bounds = {"min": [-0.1605, y0, -1.0], "max": [0.038, y1, top + 0.2]}
        pole_y = -1.0 if side == "L" else 1.0                             # FBX metres
        sockets = [{"name": "SOCKET_Hinge", "relative_location_cm": [0.0, 0.0, 0.0],
                    "relative_rotation_deg": {"roll": 0.0, "pitch": 0.0, "yaw": -90.0}},
                   {"name": "SOCKET_Pivot", "relative_location_cm": [0.0, W * 50.0 * (1 if side == "L" else -1), H * 50.0],
                    "relative_rotation_deg": {"roll": 0.0, "pitch": 90.0, "yaw": 0.0}},
                   {"name": "SOCKET_Pole_1", "relative_location_cm": [0.0, -pole_y * 100.0, 0.0],
                    "relative_rotation_deg": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}}]
        sidecar_extra = {"baked_pole_geometry": {"extension_below_panel_cm": 100.0, "bottom_z_cm": -100.0,
                                                 "top_above_panel_cm": 20.0}}
        checks_extra = {"baked_poles_lod0": {"pass": True, "details": {"SOCKET_Pole_1": {"pass": True}}},
                        "socket_contract": {"pass": True, "details": {n: {} for n in ("SOCKET_Hinge", "SOCKET_Pivot",
                                                                                      "SOCKET_Pole_1")}}}
        kind = "flat"
    else:
        bounds = {"min": [-0.1605, -W / 2.0, 0.0], "max": [0.038, W / 2.0, top]}
        sockets, sidecar_extra, kind = [], {}, "wave"
        checks_extra = {"socket_contract": {"pass": True, "details": {}}}
    docs = {
        "validation": {"pass": True, "kind": kind, "bounds_m": bounds,
                       "dimensions_m": [0.1985, W, bounds["max"][2] - bounds["min"][2]],
                       "triangle_counts": {"lod0": 12000, "lod1": 11000, "unexpected_meshes": 0},
                       "triangle_counts_by_material": {"Front": 3000, "Flap": 40, "Timber": 4000, "Edge": 5000},
                       "checks": dict({"fbx_lod_group": {"mechanism": "FBX LodGroup NodeAttribute"},
                                       "material_slots_exact": {"value": ["Front", "Flap", "Timber", "Edge"]}},
                                      **checks_extra)},
        "sidecar": dict({"schema_version": 1, "asset": asset, "sockets": sockets}, **sidecar_extra),
        "mi_params": {"parents": {"Front": core.PARENTS["Front"], "Flap": core.PARENTS["Flap"]},
                      "texture_parameters": {"SkinColor": "T_%s_SkinColor_o2.png" % owner,
                                             "SkinMask": "T_%s_SkinMask_o2.png" % owner,
                                             "SkinNormal": "T_%s_SkinNormal_o2.png" % owner},
                      "scalar_parameters": {"SheetWidthM": 1.0}},
        "report_status": "PASS", "report_owner": owner, "entry": {}, "manifest": {}}
    if mut:
        mut(docs)
    fbx = _wb(item + "/hf/builds/%s_%s/%s.fbx" % (owner, variant, asset), ("FBX " + asset).encode())
    side_car = _wj(item + "/hf/builds/%s_%s/sockets_%s.json" % (owner, variant, asset), docs["sidecar"])
    val = _wj(item + "/hf/builds/%s_%s/validation.json" % (owner, variant), docs["validation"])
    tex = {}
    for k, suf in (("SkinColor", "_SkinColor_o2p"), ("SkinMask", "_SkinMask_o2"), ("SkinNormal", "_SkinNormal_o2")):
        p = _wb(item + "/stage1/%s/skin_v3/T_%s%s.png" % (owner, owner, suf), ("PNG %s %s" % (owner, k)).encode())
        tex[k] = {"path": p, "sha256": sha(p)}
    _wj(item + "/stage1/%s/skin_v3/%s_mi_params.json" % (owner, owner), docs["mi_params"])
    probe = _wj(item + "/edge_gate/edge_probe.json", [{"fbx": fbx, "objects": {
        asset + "_LOD%d" % i: {"slots": {"Edge": {"x_min": -15.0, "x_max": -10.0},
                                         "Front": {"x_min": -15.0, "x_max": -15.0}}} for i in (0, 1)}}])
    rep = {"status": docs["report_status"], "owner": docs["report_owner"], "fbx": fbx, "fbx_sha256": sha(fbx),
           "edge_gate": {"probe": probe, "pass": True}}
    _wj(item + "/RZ_HF_REPORT.json", rep)
    _wj(item + "/RZ_BUILD_REPORT.json", rep)
    e = {"asset": asset, "intended_passage": passage, "side": side, "mount": mount, "height_cm": float(height_cm),
         "fbx": fbx, "fbx_sha256": sha(fbx), "socket_sidecar": side_car, "socket_sidecar_sha256": sha(side_car),
         "variant": "%s (synthetic)" % variant, "validation": val, "validation_pass": True,
         "build_report": item + "/RZ_BUILD_REPORT.json", "textures": tex, "aged_textures": _real_aged(),
         "slots": ["Front", "Flap", "Timber", "Edge"]}
    e.update(docs["entry"])
    return e


def make_manifest(root, name, entries, **extra):
    doc = dict({"run": "SYNTH-" + name, "unreal_imported": False, "meshes": entries}, **extra)
    return _wj(root + "/" + name, doc)


def fixture_set(root):
    p02 = [make_entry(root, "P02", "P02_real_91_synth_fern_L", "L", "wing", 1200.0, 520.0),
           make_entry(root, "P02", "P02_real_92_synth_hut_R", "R", "wing", 1200.0, 610.0, variant="t5j")]
    val = [make_entry(root, "VAL", "VAL_real_93_synth_valance_C", "L", "top-border", 300.0, 900.0),
           make_entry(root, "VAL", "VAL_real_94_synth_garland_C", "L", "top-border", 262.5, 700.0, art_top_cm=250.0)]
    return make_manifest(root, "IMPORT_MANIFEST_v2_P02.json", p02), make_manifest(root, "IMPORT_MANIFEST_v2_VAL.json", val)


def single(root, tag, **kw):
    """One-entry manifest with a fault; returns its refusals."""
    sub = os.path.join(root, tag).replace("\\", "/")
    e = make_entry(sub, kw.pop("passage", "P02"), kw.pop("owner", "P02_real_95_synth_fault_L"), kw.pop("side", "L"),
                   kw.pop("mount", "wing"), kw.pop("height", 1200.0), kw.pop("width", 500.0), **kw)
    m = make_manifest(sub, "M.json", [e])
    return core.build_plan(PROJECT, [m])["refusals"]


def synth_measure(w):
    """A measurement the Unreal side would produce for a correct import of w."""
    exp = w["expected"]
    socks = {}
    for n in exp["sockets"]:
        if n == "SOCKET_Hinge":
            socks[n] = {"location_cm": [0.0, 0.0, 0.0], "local_x_axis": [0.0, -1.0, 0.0]}
        elif n == "SOCKET_Pivot":
            socks[n] = {"location_cm": [0.0, 100.0, w["height_cm"] * 0.5], "local_x_axis": [0.0, 0.0, 1.0]}
        else:
            socks[n] = {"location_cm": [0.0, 100.0 if w["side"] == "L" else -100.0, 0.0], "local_x_axis": [1.0, 0.0, 0.0]}
    feet = ([96.0, 104.0] if w["side"] == "L" else [-104.0, -96.0]) if w["mount"] == "wing" else None
    front = {"du_dY": 0.002, "dv_dZ": -0.001, "normal": [-1.0, 0.0, 0.0]}
    return {"slots": list(core.SLOTS), "num_lods": 2, "bounds_cm": copy.deepcopy(exp["bounds_cm"]), "sockets": socks,
            "nanite": False, "edge_geometry": [{"lod": i, "front_x": [-15.0, -15.0], "edge_x": [-15.0, -10.0]} for i in (0, 1)],
            "lods": {"0": {"front": dict(front), "flap": dict(front) if exp["expect_flap"] else None,
                           "triangles": exp["triangles"]["lod0"], "foot_y": feet},
                     "1": {"front": dict(front), "flap": None, "triangles": exp["triangles"]["lod1"], "foot_y": feet}}}


# =====================================================================================================================
# Fake editor (p06 harness pattern)
# =====================================================================================================================

GOOD_REF = {"mesh_slots": [["Front", "/Game/x/MI_Front_o2p"], ["Flap", "/Game/x/MI_Flap"],
                           ["Timber", core.PARENTS["Timber"]], ["Edge", core.PARENTS["Edge"]]],
            "collision_count": 0, "num_lods": 2, "socket_names": [],
            "edge_geometry": [{"lod": 0, "front_x": [-15.0, -15.0], "edge_x": [-15.0, -10.0]},
                              {"lod": 1, "front_x": [-15.0, -15.0], "edge_x": [-15.0, -10.0]}],
            "lod0_triangles": 5000, "Front_parent": core.PARENTS["Front"], "Flap_parent": core.PARENTS["Flap"],
            "textures": {k: {p: "v" for p in core.TEXTURE_CMP} for k in core.TEXTURE_KINDS},
            "texture_kind_errors": {}, "parents_exist": {p: True for p in sorted(core.PARENTS.values())}}


class FakeOps:
    def __init__(self):
        self.logs, self.errors, self.events = [], [], []
        self.assets, self.disk = set(), set()
        self.dirty = {"content": [], "maps": []}
        self.pie = False
        self.ram = 40.0
        self.ref = copy.deepcopy(GOOD_REF)
        self.aged_fail = None
        self.fail_import_at = None
        self.measure_fault = None
        self.foreign_dirty_on_import = False
        self.fail_save = None
        self.fail_readback = None
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
        m = synth_measure(w)
        if self.measure_fault and self.measure_fault[0] == w["owner"]:
            self.measure_fault[1](m)
        bad = core.geometry_verdict(w, m)                     # the real gate, as rzimport.UnrealOps._geometry calls it
        if bad:
            raise RuntimeError("GEOMETRY_GATE|" + " ; ".join(bad[:6]))
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


def main():
    tmp = tempfile.mkdtemp(prefix="rzimp_").replace("\\", "/")
    try:
        return _main(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _main(tmp):
    # ---------------------------------------------------------------- R: real manifests
    p06 = core.build_plan(PROJECT, [P06_MANIFEST])
    kit = p06core.build_plan(PROJECT)
    check("R1 POS P06 v2 manifest: destinations == the P06 kit's (same 15 owners, same 105 /Game paths)",
          {w["owner"]: w["destinations"] for w in p06["wings"].values()} ==
          {w["owner"]: w["destinations"] for w in kit["wings"].values()} and p06["package_count"] == 105)
    check("R1 NEG ... and it REFUSES only with DESTINATION_CLASH_WITH_P06_IMPORT (already imported 7 Oct)",
          len(p06["refusals"]) == 1 and p06["refusals"][0].startswith("DESTINATION_CLASH_WITH_P06_IMPORT 105"),
          p06["refusals"][:2])
    check("R1 POS P06 auto-batches <= 3 and cover every owner once",
          all(len(b["owners"]) <= 3 for b in p06["batches"]) and
          sorted(o for b in p06["batches"] for o in b["owners"]) == sorted(p06["wings"]))
    v1 = core.build_plan(PROJECT, [V1_MANIFEST])
    check("R2 POS v1 root manifest (P02, 12 m, never imported): every file gate passes", v1["gates_ok"], v1["refusals"])
    check("R2 POS ... heights come from the manifest: 1200 cm, bounds z -100..1220, pivot 600",
          all(w["height_cm"] == 1200.0 and abs(w["expected"]["bounds_cm"]["max"][2] - 1220.0) < 1.5 and
              abs(w["expected"]["bounds_cm"]["min"][2] + 100.0) < 1.5 for w in v1["wings"].values()) and
          len(v1["wings"]) == 2, [(w["height_cm"], w["expected"]["bounds_cm"]) for w in v1["wings"].values()])
    check("R2 POS ... P02 owners only, mesh folders by variant (t5p -> T5P, t5j -> T5J)",
          all(o.startswith("P02_") for o in v1["wings"]) and
          all(("/T5P/" if w["variant"] == "t5p" else "/T5J/") in w["destinations"]["mesh"] for w in v1["wings"].values()))
    # geometry verdict on the real P06 + v1 expectations
    check("G0 POS geometry_verdict accepts the expected measurement of every real entry (P06 x15, P02 v1 x2)",
          all(not core.geometry_verdict(w, synth_measure(w)) for pl in (p06, v1) for w in pl["wings"].values()),
          [core.geometry_verdict(w, synth_measure(w))[:1] for pl in (p06, v1) for w in pl["wings"].values()][:2])
    # ---------------------------------------------------------------- F: fixtures
    m02, mval = fixture_set(tmp + "/fx")
    fx = core.build_plan(PROJECT, [m02, mval])
    W = fx["wings"]
    check("F1 POS fixtures P02 (2 x 12 m wings) + VAL (2 top borders): every file gate passes", fx["gates_ok"], fx["refusals"])
    check("F1 POS 28 packages, all under the Realism root, 7 per entry", fx["package_count"] == 28 and
          all(len(w["packages"]) == 7 and all(p.startswith(core.ROOT + "/") for p in w["packages"]) for w in W.values()))
    check("F1 POS batches never mix manifests; <= 3 each", [b["owners"] for b in fx["batches"]] ==
          [["P02_real_91_synth_fern_L", "P02_real_92_synth_hut_R"], ["VAL_real_93_synth_valance_C", "VAL_real_94_synth_garland_C"]],
          [b["owners"] for b in fx["batches"]])
    v = W["VAL_real_93_synth_valance_C"]
    check("F2 POS top border: no sockets expected, no pole, mount top-border, centred bounds, z 0..300",
          v["mount"] == "top-border" and v["expected"]["sockets"] == [] and v["expected"]["pole"] is None and
          abs(v["expected"]["bounds_cm"]["min"][1] + v["expected"]["bounds_cm"]["max"][1]) < 0.01 and
          abs(v["expected"]["bounds_cm"]["max"][2] - 300.0) < 0.01)
    check("F2 POS top border whose art stops below the image top (250 of 262.5 cm) is accepted [inf rule]",
          "VAL_real_94_synth_garland_C" in W)
    w12 = W["P02_real_91_synth_fern_L"]
    check("F3 POS 12 m wing: bounds z -100..1220, pivot expectation 600 cm",
          abs(w12["expected"]["bounds_cm"]["max"][2] - 1220.0) < 0.01 and w12["height_cm"] == 1200.0)
    both = core.build_plan(PROJECT, [V1_MANIFEST, m02, mval])
    check("F4 POS real v1 P02 + fixtures together: owners distinct, gates pass, 3 batches (one per manifest)", both["gates_ok"] and
          len(both["wings"]) == 6 and len(both["batches"]) == 3, (both["refusals"], [b["owners"] for b in both["batches"]]))
    check("F4 POS plan hash changes with the manifest set", both["inputs_hash"] != fx["inputs_hash"])
    # ---------------------------------------------------------------- N: file-gate negatives
    r = single(tmp, "n1", height=1200.0, art_top_cm=1000.0)
    check("N1 NEG manifest says 1200 but the build is 10 m (bounds top 1020) -> HEIGHT_VS_MANIFEST (not hard-coded)",
          any(x.startswith("HEIGHT_VS_MANIFEST") for x in r), r)
    r = single(tmp, "n1b", height=1000.0, art_top_cm=1200.0)
    check("N1 NEG manifest says 1000 but the build is 12 m -> HEIGHT_VS_MANIFEST", any("HEIGHT_VS_MANIFEST" in x for x in r), r)

    def m_pivot(d):
        d["sidecar"]["sockets"][1]["relative_location_cm"][2] = 500.0
    r = single(tmp, "n2", mut=m_pivot)
    check("N2 NEG 12 m wing with its pivot at 500 (a 10 m contract) -> PIVOT_Z_VS_MANIFEST_HEIGHT",
          any("PIVOT_Z_VS_MANIFEST_HEIGHT" in x for x in r), r)
    a = make_entry(tmp + "/n3", "P02", "P02_real_96_dup_L", "L", "wing", 1200.0, 500.0)
    m1 = make_manifest(tmp + "/n3a", "A.json", [a])
    m2 = make_manifest(tmp + "/n3b", "B.json", [a])
    r = core.build_plan(PROJECT, [m1, m2])["refusals"]
    check("N3 NEG same owner in two manifests -> DUPLICATE_OWNER", any("DUPLICATE_OWNER" in x for x in r), r)
    r = single(tmp, "n4", passage="P03")
    check("N4 NEG a P02 owner under intended_passage P03 -> OWNER_NOT_PASSAGE_PREFIXED",
          any("OWNER_NOT_PASSAGE_PREFIXED" in x for x in r), r)

    def t_sock(d):
        d["sidecar"]["sockets"] = [{"name": "SOCKET_Hinge", "relative_location_cm": [0, 0, 0],
                                    "relative_rotation_deg": {"roll": 0, "pitch": 0, "yaw": -90}}]
    kw = dict(passage="VAL", owner="VAL_real_97_t_C", mount="top-border", height=300.0, width=800.0)
    r = single(tmp, "n5", mut=t_sock, **kw)
    check("N5 NEG top border whose sidecar carries a socket -> TOP_BORDER_HAS_SOCKETS",
          any("TOP_BORDER_HAS_SOCKETS" in x for x in r), r)
    r = single(tmp, "n6", mut=lambda d: d["sidecar"].update({"baked_pole_geometry": {"bottom_z_cm": -100.0,
                                                                                     "top_above_panel_cm": 20.0}}), **kw)
    check("N6 NEG top border with baked poles -> TOP_BORDER_HAS_BAKED_POLES", any("TOP_BORDER_HAS_BAKED_POLES" in x for x in r), r)
    r = single(tmp, "n7", mut=lambda d: d["validation"].update({"kind": "flat"}), **kw)
    check("N7 NEG top border validated as 'flat' -> TOP_BORDER_VALIDATION_KIND", any("TOP_BORDER_VALIDATION_KIND" in x for x in r), r)

    def off_centre(d):
        d["validation"]["bounds_m"]["min"][1] += 0.5
        d["validation"]["bounds_m"]["max"][1] += 0.5
    r = single(tmp, "n8", mut=off_centre, **kw)
    check("N8 NEG top border not centred on Y (50 cm off) -> TOP_NOT_CENTRED", any("TOP_NOT_CENTRED" in x for x in r), r)
    r = single(tmp, "n9", passage="VAL", owner="VAL_real_98_t_L", mount="top-border", height=300.0, width=800.0)
    check("N9 NEG top border owner without the _C suffix -> OWNER_SIDE", any(x.startswith("OWNER_SIDE") for x in r), r)

    def wing_no_sockets(d):
        d["sidecar"]["sockets"] = []
    r = single(tmp, "n10", mut=wing_no_sockets)
    check("N10 NEG a wing whose sidecar has no sockets (top-border sidecar on a wing) -> SOCKET_SIDECAR_VS_BAKED_POLES",
          any("SOCKET_SIDECAR_VS_BAKED_POLES" in x for x in r), r)
    r = single(tmp, "n11", mut=lambda d: d.update({"report_status": "FAIL"}))
    check("N11 NEG build report FAIL -> BUILD_REPORT_DISAGREES", any("BUILD_REPORT_DISAGREES" in x for x in r), r)
    sub = tmp + "/n12"
    e = make_entry(sub, "P02", "P02_real_99_imp_L", "L", "wing", 1200.0, 500.0)
    r = core.build_plan(PROJECT, [make_manifest(sub, "M.json", [e], unreal_imported=True)])["refusals"]
    check("N12 NEG manifest unreal_imported true -> MANIFEST_ALREADY_IMPORTED_OR_UNMARKED",
          any("MANIFEST_ALREADY_IMPORTED" in x for x in r), r)
    r = single(tmp, "n13", mut=lambda d: d["entry"].update({"fbx_sha256": "0" * 64}))
    check("N13 NEG FBX sha in the manifest != file -> SOURCE_HASH_MISMATCH (+ BUILD_REPORT_DISAGREES)",
          any("SOURCE_HASH_MISMATCH" in x and "fbx" in x for x in r), r)
    owners = list(both["wings"])
    r = core.build_plan(PROJECT, [V1_MANIFEST, m02, mval], batches=(tuple(owners[:4]), tuple(owners[4:])))["refusals"]
    check("N14 NEG a 4-entry batch -> BATCH_TOO_BIG", any("BATCH_TOO_BIG" in x for x in r), r)
    r = core.build_plan(PROJECT, [V1_MANIFEST, m02, mval], batches=(tuple(owners[:3]), tuple(owners[3:5])))["refusals"]
    check("N15 NEG an entry left out of the batches -> BATCHES_DO_NOT_COVER_OWNERS_ONCE", any("COVER" in x for x in r), r)
    r = single(tmp, "n16", mount="valance-ish")
    check("N16 NEG unknown mount -> MOUNT_UNKNOWN", any("MOUNT_UNKNOWN" in x for x in r), r)

    def no_flap(d):
        d["validation"]["triangle_counts_by_material"]["Flap"] = 0
    sub = tmp + "/n17"
    e = make_entry(sub, "VAL", "VAL_real_90_noflap_C", "L", "top-border", 300.0, 800.0, mut=no_flap)
    nf = core.build_plan(PROJECT, [make_manifest(sub, "M.json", [e])])
    check("N17 POS a top border with 0 Flap triangles plans expect_flap False", nf["gates_ok"] and
          nf["wings"]["VAL_real_90_noflap_C"]["expected"]["expect_flap"] is False, nf["refusals"])
    # ---------------------------------------------------------------- G: the mount-aware mesh gate, pure
    wing, top, topnf = w12, v, nf["wings"]["VAL_real_90_noflap_C"]
    check("G1 POS wing (12 m) expected measurement passes", core.geometry_verdict(wing, synth_measure(wing)) == [],
          core.geometry_verdict(wing, synth_measure(wing)))
    check("G1 POS top border expected measurement passes", core.geometry_verdict(top, synth_measure(top)) == [],
          core.geometry_verdict(top, synth_measure(top)))
    check("G1 POS top border without flaps passes with no Flap section", core.geometry_verdict(topnf, synth_measure(topnf)) == [])

    def gneg(name, w, fault, token):
        m = synth_measure(w)
        fault(m)
        bad = core.geometry_verdict(w, m)
        check(name, any(token in b for b in bad), bad)
    gneg("G2 NEG top border that came in WITH a socket -> SOCKET_NAMES_FAIL / TOP_SOCKET_FAIL", top,
         lambda m: m["sockets"].update({"SOCKET_Hinge": {"location_cm": [0, 0, 0], "local_x_axis": [0, 1, 0]}}),
         "TOP_SOCKET_FAIL")
    gneg("G3 NEG top border shifted 30 cm on Y -> TOP_NOT_CENTRED_ON_Y", top,
         lambda m: (m["bounds_cm"]["min"].__setitem__(1, m["bounds_cm"]["min"][1] + 30.0),
                    m["bounds_cm"]["max"].__setitem__(1, m["bounds_cm"]["max"][1] + 30.0)), "TOP_NOT_CENTRED_ON_Y")
    gneg("G4 NEG flap-less top border that grew a Flap section -> UNEXPECTED_FLAP_SECTION", topnf,
         lambda m: m["lods"]["0"].update({"flap": {"du_dY": 0.002, "dv_dZ": -0.001, "normal": [-1, 0, 0]}}),
         "UNEXPECTED_FLAP_SECTION")
    gneg("G5 NEG wing with no pole-foot vertices -> BAKED_POLE_FOOT_VERTICES_MISSING", wing,
         lambda m: m["lods"]["0"].update({"foot_y": []}), "BAKED_POLE_FOOT_VERTICES_MISSING")
    gneg("G6 NEG 12 m wing with pivot at 500 -> PIVOT_SOCKET_FAIL", wing,
         lambda m: m["sockets"]["SOCKET_Pivot"].update({"location_cm": [0.0, 100.0, 500.0]}), "PIVOT_SOCKET_FAIL")
    gneg("G7 NEG LodGroup not honoured (1 LOD) -> LOD_COUNT_FAIL", wing, lambda m: m.update({"num_lods": 1}), "LOD_COUNT_FAIL")
    gneg("G8 NEG LOD1 flap survived -> LOD1_FLAP_SURVIVED", top,
         lambda m: m["lods"]["1"].update({"flap": {"du_dY": 1, "dv_dZ": -1, "normal": [-1, 0, 0]}}), "LOD1_FLAP_SURVIVED")
    gneg("G9 NEG V runs up (dv_dZ > 0) -> FRONT_UV0_SIGN_FAIL", top,
         lambda m: m["lods"]["0"]["front"].update({"dv_dZ": 0.001}), "FRONT_UV0_SIGN_FAIL")
    gneg("G10 NEG triangle count off by 5 -> TRIANGLE_COUNT_FAIL", wing,
         lambda m: m["lods"]["1"].update({"triangles": m["lods"]["1"]["triangles"] + 5}), "TRIANGLE_COUNT_FAIL")
    gneg("G11 NEG Edge section at x -15..-12.5 -> EDGE_GEOMETRY_FAIL", top,
         lambda m: m["edge_geometry"][1].update({"edge_x": [-15.0, -12.5]}), "EDGE_GEOMETRY_FAIL")
    gneg("G12 NEG import bounds 20 cm taller than the validator's -> BOUNDS_MISMATCH", top,
         lambda m: m["bounds_cm"]["max"].__setitem__(2, m["bounds_cm"]["max"][2] + 20.0), "BOUNDS_MISMATCH")
    gneg("G13 NEG nanite left on -> NANITE_ENABLED", wing, lambda m: m.update({"nanite": True}), "NANITE_ENABLED")
    wing_as_top = dict(top, mount="wing", side="L")
    bad = core.geometry_verdict(wing_as_top, synth_measure(top))
    check("G14 NEG a top-border mesh judged by the WING rule fails (the mount switch is load-bearing)",
          any("HINGE_SOCKET_FAIL" in b for b in bad), bad)
    # ---------------------------------------------------------------- A: args
    margs = [m02, mval]
    expect_stop("A1 NEG DRY confirm mismatch", lambda: core.validate_args({"mode": "DRY", "confirm": "DRY", "manifests": margs}),
                "CONFIRM_MISMATCH")
    expect_stop("A2 NEG no manifests", lambda: core.validate_args({"mode": "DRY", "confirm": "DRY RZIMPORT"}), "MANIFESTS_MISSING")
    expect_stop("A3 NEG APPLY batch 3 of 2", lambda: core.validate_args({"mode": "APPLY", "batch": 3, "confirm": "x",
                                                                       "manifests": margs}, fx), "BATCH_INVALID")
    expect_stop("A4 NEG APPLY confirm of another plan (old hash)", lambda: core.validate_args(
        {"mode": "APPLY", "batch": 1, "confirm": core.confirm_for("APPLY", both, 1), "manifests": margs}, fx), "CONFIRM_MISMATCH")
    check("A5 POS APPLY confirm carries the plan hash", core.validate_args(
        {"mode": "APPLY", "batch": 2, "confirm": "APPLY RZIMPORT BATCH 2 #" + fx["hash8"], "manifests": margs}, fx) == ("APPLY", 2))
    # ---------------------------------------------------------------- D / X / Y: orchestration
    def fresh():
        return FakeOps(), tempfile.mkdtemp(prefix="rzimp_run_", dir=tmp)

    def dry(ops, d, run="RZ-T-DRY"):
        return app.run_dry(ops, core, {"mode": "DRY", "confirm": "DRY RZIMPORT", "manifests": margs}, run, d)

    def apply_(ops, d, k, run=None, plan=None):
        plan = plan or fx
        a = {"mode": "APPLY", "batch": k, "confirm": core.confirm_for("APPLY", plan, k), "manifests": margs}
        core.validate_args(a, plan)
        return app.run_apply(ops, core, a, plan, run or "RZ-T-B%d" % k, d, k)

    ops, d = fresh()
    ops.dirty["content"] = ["/Game/Other"]
    expect_stop("D1 NEG dirty census at start", lambda: dry(ops, d), "DIRTY_CENSUS")
    ops, d = fresh()
    ops.pie = True
    expect_stop("D2 NEG PIE running", lambda: dry(ops, d), "PIE_OR_SIE_ACTIVE")
    for label, mut, token in (
            ("a target already exists", lambda o: o.assets.add(W["VAL_real_93_synth_valance_C"]["destinations"]["Flap"]),
             "CREATE_ONLY_TARGETS_EXIST"),
            ("reference Front MI moved to v4", lambda o: o.ref.update({"Front_parent": core.BB + "MI_Billboard_Front_v4"}),
             "REFERENCE_MI_PARENT"),
            ("aged Common missing", lambda o: setattr(o, "aged_fail", "LOAD_FAIL|Common"), "AGED_COMMON_NOT_READY"),
            ("low RAM", lambda o: setattr(o, "ram", 6.0), "LOW_RAM")):
        ops, d = fresh()
        mut(ops)
        expect_stop("D3 NEG DRY refuses: %s -> %s" % (label, token), lambda: dry(ops, d), token)
        lat = app._read_json(os.path.join(d, core.dry_latest_name(fx)))
        check("D3 NEG ... DRY record written REFUSED", lat and lat["status"] == "REFUSED", lat and lat["status"])
    ops, d = fresh()
    dry(ops, d)
    check("D4 POS DRY marker with run id + plan hash; 2 per-batch confirms logged", any(
        m.startswith("FLATV3_RZIMPORT_DRY_OK|run=RZ-T-DRY|plan=%s|wings=4|packages=28" % fx["hash8"]) for m in ops.logs) and
        sum("DRY_CONFIRM|run=RZ-T-DRY|plan=" in m for m in ops.logs) == 2, ops.logs[:2])
    check("D4 POS DRY created nothing", not ops.assets and ops.imports == 0 and ops.census() == {"content": [], "maps": []})
    ops, d = fresh()
    expect_stop("X1 NEG APPLY with no DRY", lambda: apply_(ops, d, 1), "NO_PASSING_DRY")
    ops, d = fresh()
    dry(ops, d)
    expect_stop("X2 NEG APPLY of ANOTHER plan (manifest set changed) finds no DRY for its hash",
                lambda: apply_(ops, d, 1, plan=both), "NO_PASSING_DRY")
    ops, d = fresh()
    dry(ops, d)
    lat = app._read_json(os.path.join(d, core.dry_latest_name(fx)))
    lat["inputs_hash"] = "deadbeef" + lat["inputs_hash"][8:]
    app._write_json(os.path.join(d, core.dry_latest_name(fx)), lat)
    expect_stop("X3 NEG DRY record hash != plan -> PLAN_STALE", lambda: apply_(ops, d, 1), "PLAN_STALE")
    ops, d = fresh()
    dry(ops, d)
    ops.ram = 8.0
    expect_stop("X4 NEG low RAM before any import", lambda: apply_(ops, d, 1), "LOW_RAM")
    check("X4 NEG ... nothing imported", ops.imports == 0)
    ops, d = fresh()
    dry(ops, d)
    ops.ref["collision_count"] = 1
    expect_stop("X5 NEG reference drift since DRY", lambda: apply_(ops, d, 1), "REFERENCE_DRIFT_SINCE_DRY")
    ops, d = fresh()
    dry(ops, d)
    ops.measure_fault = ("VAL_real_94_synth_garland_C", lambda m: m["sockets"].update(
        {"SOCKET_Pivot": {"location_cm": [0, 0, 100], "local_x_axis": [0, 0, 1]}}))
    expect_stop("X6 NEG top border imported WITH a socket (Interchange) -> IMPORT_GATE GEOMETRY_GATE, nothing saved",
                lambda: apply_(ops, d, 2), "GEOMETRY_GATE")
    fail = app._read_json(os.path.join(d, "rzimport_apply_b2_RZ-T-B2_FAILURE.json"))
    check("X6 NEG ... no save call; failure record lists the unsaved packages + Don't Save",
          not any(e[0] == "save" for e in ops.events) and fail and fail["saved"] == [] and
          len(fail["created_unsaved"]) == 14 and "Don't Save" in fail["next"], fail and fail.get("status"))
    check("X6 NEG ... STOPPED marker carries run, plan and batch", any(
        m.startswith("FLATV3_RZIMPORT_STOPPED|run=RZ-T-B2|plan=%s|batch=2|" % fx["hash8"]) for m in ops.errors), ops.errors[-1:])
    ops, d = fresh()
    dry(ops, d)
    ops.foreign_dirty_on_import = True
    expect_stop("X7 NEG foreign package dirtied during import -> DIRTY_SET_NOT_EXACT", lambda: apply_(ops, d, 1),
                "DIRTY_SET_NOT_EXACT")
    check("X7 NEG ... no save call", not any(e[0] == "save" for e in ops.events))
    ops, d = fresh()
    dry(ops, d)
    ops.fail_save = sorted(fx["batches"][0]["packages"])[2]
    expect_stop("X8 NEG save returns False on the 3rd package", lambda: apply_(ops, d, 1), "SAVE_FAIL")
    led = app._read_json(os.path.join(d, core.ledger_name(fx)))
    check("X8 NEG ... ledger (per plan hash) FAILED_AFTER_SAVE with exactly 2 saved; no OK marker",
          led["batches"]["1"]["status"] == "FAILED_AFTER_SAVE" and len(led["batches"]["1"]["saved"]) == 2 and
          not any("APPLY_OK" in m for m in ops.logs), led)
    ops, d = fresh()
    dry(ops, d)
    ops.fail_readback = "P02_real_91_synth_fern_L"
    expect_stop("X9 NEG read-back fails after save -> no success marker", lambda: apply_(ops, d, 1), "SAVE_OR_READBACK")
    check("X9 NEG ... no APPLY_OK marker", not any("APPLY_OK" in m for m in ops.logs))
    ops, d = fresh()
    dry(ops, d)
    v0 = app.run_verify(ops, core, {"manifests": margs}, "RZ-T-V0", d)
    check("Y0 POS VERIFY before APPLY -> INCOMPLETE 4 missing", v0["status"] == "INCOMPLETE" and len(v0["missing"]) == 4)
    apply_(ops, d, 1)
    saves = [e[1] for e in ops.events if e[0] == "save"]
    check("Y1 POS batch 1 saved exactly its 14 packages", sorted(saves) == sorted(fx["batches"][0]["packages"]) and
          len(saves) == 14, saves[:3])
    ok_i = max(i for i, e in enumerate(ops.events) if e[0] == "log" and "APPLY_OK" in e[1])
    last_save = max(i for i, e in enumerate(ops.events) if e[0] == "save")
    last_rb = max(i for i, e in enumerate(ops.events) if e[0] == "readback")
    gc_i = max(i for i, e in enumerate(ops.events) if e[0] == "gc")
    check("Y1 POS success marker AFTER the last save, the read-back and the GC",
          ok_i > last_save and ok_i > last_rb and ok_i > gc_i, (ok_i, last_save, last_rb, gc_i))
    check("Y1 POS marker = FLATV3_RZIMPORT_APPLY_OK|run=..|plan=..|batch=1", any(
        m.startswith("FLATV3_RZIMPORT_APPLY_OK|run=RZ-T-B1|plan=%s|batch=1|" % fx["hash8"]) for m in ops.logs))
    expect_stop("Y2 NEG same batch again -> BATCH_ALREADY_SAVED", lambda: apply_(ops, d, 1, "RZ-T-B1b"), "BATCH_ALREADY_SAVED")
    u = app.run_undo_list(core, PROJECT, d, ops.log, margs)
    check("U1 POS UNDO_LIST after batch 1: 14 packages, MIs first; auto_delete False; nothing deleted",
          not u["auto_delete"] and len(u["batches"]) == 1 and len(u["batches"][0]["delete_in_order"]) == 14 and
          all("/Materials/Instances/" in p for p in u["batches"][0]["delete_in_order"][:4]) and
          all(p in ops.assets for p in fx["batches"][0]["packages"]))
    apply_(ops, d, 2)
    v2 = app.run_verify(ops, core, {"manifests": margs}, "RZ-T-V2", d)
    check("Y3 POS both batches -> VERIFY_OK wings=4 (2 wings + 2 top borders), mesh paths listed for rzswap",
          v2["status"] == "PASS" and len(v2["mesh_paths"]) == 4 and any(
              m.startswith("FLATV3_RZIMPORT_VERIFY_OK|run=RZ-T-V2|plan=%s|wings=4" % fx["hash8"]) for m in ops.logs))
    check("Y3 POS VERIFY wrote rzimport_verify_<hash8>_LATEST.json", os.path.isfile(
        os.path.join(d, "rzimport_verify_%s_LATEST.json" % fx["hash8"])))
    check("Y3 POS 28 packages on disk, 2 GCs", len(ops.disk) == 28 and ops.gc == 2)
    # ---------------------------------------------------------------- S: static source rules
    src = open(os.path.join(HERE, "rzimport.py"), encoding="utf-8").read()
    check("S1 no delete / reload / Save All anywhere in the kit", not any(t in src for t in (
        "delete_asset", "reload_packages", "save_dirty_packages", "save_all", "SaveAll", "delete_directory")))
    tree = ast.parse(src)
    glob_unreal = [n.lineno for n in tree.body if isinstance(n, ast.Assign) and "unreal." in ast.unparse(n.value)]
    check("S2 no unreal object in a module global", not glob_unreal, glob_unreal)
    run_src = open(os.path.join(HERE, "rzimport_run.py"), encoding="utf-8").read()
    check("S3 runner purges the Saved module cache BEFORE running the kit",
          run_src.index("purge_saved_module_cache.py") < run_src.index("rzimport.py\""))
    req = json.load(open(os.path.join(HERE, "rzimport_request.json"), encoding="utf-8"))
    check("S4 request = guarded loopback route, our runner", req["arguments"]["toolset_name"] ==
          "MCPBlueprintsGenerator.MCPBlueprintsGeneratorToolset" and req["arguments"]["tool_name"] == "ExecuteProjectPythonFile"
          and req["arguments"]["arguments"]["relativeSavedPath"] == "CodexFlatV3/rzimport/rzimport_run.py")
    args = json.load(open(os.path.join(HERE, "rzimport_args.json"), encoding="utf-8"))
    check("S5 shipped args = read-only (VERIFY or DRY), never APPLY", args["mode"] in ("VERIFY", "DRY") and
          core.validate_args(args)[0] == args["mode"])
    ast.parse(src)
    check("S6 live files parse as Python 3.11 syntax (no 3.12+ constructs used: ast.parse with feature_version)",
          all(ast.parse(open(os.path.join(HERE, f), encoding="utf-8").read(), feature_version=(3, 11)) is not None
              for f in ("rzimport.py", "rzimport_core.py", "rzimport_run.py")))
    rep = {"checks": RESULTS, "passed": sum(r["pass"] for r in RESULTS), "failed": sum(not r["pass"] for r in RESULTS),
           "fixture_plan_hash": fx["inputs_hash"], "v1_plan_hash": v1["inputs_hash"]}
    with open(os.path.join(HERE, "test_rzimport_offline_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print("RESULT %d passed, %d failed" % (rep["passed"], rep["failed"]))
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
