"""Offline harness for grease_v2_ue.py (fake `unreal`, temp project).  NOTHING here touches Unreal.

  python test_grease_v2_ue.py        -> test_grease_v2_ue_report.json

The REAL tool runs via runpy against fake_unreal_gv2.py in a temp project holding copies of the two v2 PNGs, the pinned
grease worklist and grease assets record; Content is seeded with the v1 textures (non-default settings), the grease
master, the 142 MIs from the worklist (scalars from it), the tint master + MIs and the visible print decal v3 master +
MIs.  Positive tests run the whole slot order; negative controls inject one fault each and assert the refusal reason
AND that nothing was saved where nothing may be.
"""
import ast
import copy
import hashlib
import json
import os
import re
import runpy
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import fake_unreal_gv2 as fk  # noqa: E402

TOOL = HERE / "grease_v2_ue.py"
WORKLIST = PROJECT / "Saved/CodexFlatV3/handprints/grease/hp_grease_mi_worklist.json"
REF_RECORD = PROJECT / "Saved/CodexFlatV3/handprints/grease/hp_grease_assets_record.json"
PNG_DIR = PROJECT / "DerivedAssets/S3Marble/GreaseV2_20261008"
ROOT = "/Game/Scenes/Scene3/HandPrints"
TEX = ROOT + "/Textures"
ATLAS_V1, NORMAL_V1 = TEX + "/T_HP_S03_GreaseAtlas", TEX + "/T_S03_HandPrints_Normal"
ATLAS_V2, NORMAL_V2 = TEX + "/T_HP_S03_GreaseAtlas_v2", TEX + "/T_HP_S03_PrintNormal_v2"
MASTER = ROOT + "/Materials/Grease/M_HP_S03_Grease"
V3 = ROOT + "/Materials/M_HP_S03_Decal_v3"
TINT = ROOT + "/Materials/GreaseTint/M_HP_S03_GreaseTint"
SCALARS = {"AtlasU0": 0.0, "AtlasV0": 0.0, "AtlasUSize": 1.0, "AtlasVSize": 1.0, "FlipU": 0.0, "GlobalFlipU": 0.0,
           "GlobalFlipV": 0.0, "GreaseGain": 1.0, "GreaseRoughMin": 0.30, "GreaseRoughRange": 0.25, "NormalStrength": 0.25}
CONFIRM_APPLY, CONFIRM_REVERT = "APPLY GREASE V2", "REVERT GREASE V2"
RESULTS = {}


def E(enum, name):
    return {"__enum__": name}


def tex_spec(comp, lod, mip, flt, bias, never, addr, flip, size, srgb=False):
    return {"cls": "Texture2D", "size": size,
            "props": {"srgb": srgb, "compression_settings": E(0, comp), "lod_group": E(0, lod),
                      "mip_gen_settings": E(0, mip), "filter": E(0, flt), "lod_bias": bias, "never_stream": never,
                      "max_texture_size": 0, "virtual_texture_streaming": False, "address_x": E(0, addr),
                      "address_y": E(0, addr), "flip_green_channel": flip}}


class Sim:
    def __init__(self, drop_mi=0, pre_override=0, faults=None):
        self.tmp = Path(tempfile.mkdtemp(prefix="gv2_"))
        p = self.tmp
        for src, rel in ((WORKLIST, "Saved/CodexFlatV3/handprints/grease/hp_grease_mi_worklist.json"),
                         (REF_RECORD, "Saved/CodexFlatV3/handprints/grease/hp_grease_assets_record.json"),
                         (PNG_DIR / "T_HP_S03_GreaseAtlas_v2.png", "DerivedAssets/S3Marble/GreaseV2_20261008/T_HP_S03_GreaseAtlas_v2.png"),
                         (PNG_DIR / "T_HP_S03_PrintNormal_v2.png", "DerivedAssets/S3Marble/GreaseV2_20261008/T_HP_S03_PrintNormal_v2.png")):
            (p / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, p / rel)
        (p / "Saved/CodexConductor/GreaseV2_20261008").mkdir(parents=True, exist_ok=True)
        self.work = json.loads(WORKLIST.read_text(encoding="utf-8"))
        objs = {
            ATLAS_V1: tex_spec("TC_MASKS", "TEXTUREGROUP_WORLD", "TMGS_SIMPLE_AVERAGE", "TF_TRILINEAR", 0, False,
                               "TA_CLAMP", False, [2048, 2048]),
            NORMAL_V1: tex_spec("TC_NORMALMAP", "TEXTUREGROUP_WORLD_NORMAL_MAP", "TMGS_FROM_TEXTURE_GROUP",
                                "TF_TRILINEAR", 1, True, "TA_WRAP", False, [1024, 1024]),
            TEX + "/T_S03_HandPrints_BaseColor": tex_spec("TC_DEFAULT", "TEXTUREGROUP_WORLD", "TMGS_FROM_TEXTURE_GROUP",
                                                          "TF_DEFAULT", 0, False, "TA_WRAP", False, [4096, 4096], True),
            TEX + "/T_S03_HandPrints_Roughness": tex_spec("TC_MASKS", "TEXTUREGROUP_WORLD", "TMGS_FROM_TEXTURE_GROUP",
                                                          "TF_DEFAULT", 0, False, "TA_WRAP", False, [1024, 1024]),
            MASTER: {"cls": "Material", "scalars": SCALARS, "textures": {"GreaseMask": ATLAS_V1, "PrintNormal": NORMAL_V1}},
            TINT: {"cls": "Material", "scalars": {"TintStrength": 0.5}, "textures": {"GreaseMask": ATLAS_V1}},
            V3: {"cls": "Material", "scalars": {"Gain": 1.0},
                 "textures": {"NormalAtlas": NORMAL_V1, "BaseColorAtlas": TEX + "/T_S03_HandPrints_BaseColor"}},
        }
        for i in range(4):
            objs[ROOT + "/Materials/GreaseTint/MI_HP_S03_t1_%d" % i] = {"cls": "MaterialInstanceConstant", "parent": TINT,
                                                                       "scalars": {"TintStrength": 0.1 * i}, "textures": {}}
        for i in range(6):
            objs[ROOT + "/Materials/V3/MI_HP_S03_v3_P%03d_F0" % i] = {
                "cls": "MaterialInstanceConstant", "parent": V3, "scalars": {"Gain": 0.5},
                "textures": {"NormalAtlas": NORMAL_V1} if i == 0 else {}}
        insts = self.work["instances"][drop_mi:]
        self.mi_paths = [i["path"] for i in insts]
        for k, i in enumerate(insts):
            objs[i["path"]] = {"cls": "MaterialInstanceConstant", "parent": MASTER,
                               "scalars": dict(i["scalars"]),
                               "textures": {"GreaseMask": ATLAS_V1} if k < pre_override else {}}
        self.state = {"project": str(p).replace("\\", "/"), "objects": objs, "faults": dict(faults or {})}
        self.u = fk.make(self.state)
        self.original_disk = {mp: self.disk(mp) for mp in self.mi_paths}

    def cfile(self, path):
        return self.tmp / "Content" / (path[len("/Game/"):] + ".uasset")

    def disk(self, path):
        return json.loads(self.cfile(path).read_text(encoding="utf-8"))

    def protected_hashes(self):
        out = {}
        for f in sorted((self.tmp / "Content").rglob("*.uasset")):
            rel = f.relative_to(self.tmp).as_posix()
            if "/Grease/MI_HP_S03_g1_" in rel or "_v2.uasset" in rel:
                continue
            out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
        return out

    def run(self, mode, confirm=None, args=None, tool=TOOL):
        argf = self.tmp / "Saved/CodexConductor/GreaseV2_20261008/grease_v2_ue_args.json"
        if args is None:
            if argf.exists():
                argf.unlink()
        else:
            argf.write_text(json.dumps(args), encoding="utf-8")
        sys.modules["unreal"] = self.u
        n0 = len(self.u.logs)
        g = {"GV2_MODE": mode, "GV2_FREE_RAM_PROBE": self.state["faults"].get("ram", lambda: 32.0)}
        if confirm:
            g["GV2_CONFIRM"] = confirm
        runpy.run_path(str(tool), init_globals=g)
        return self.u.logs[n0:]

    def record(self):
        return json.loads((self.tmp / "Saved/CodexConductor/GreaseV2_20261008/grease_v2_ue_record.json").read_text(encoding="utf-8"))

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def text(logs):
    return "\n".join(m for _, m in logs)


def ok(logs, marker):
    t = text(logs)
    return marker in t and "_STOPPED" not in t and "_ERROR" not in t


def stopped(logs, reason):
    t = text(logs)
    return "_STOPPED" in t and reason in t


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def to_textures(sim):
    check(ok(sim.run("IMPORT"), "GV2_IMPORT_IMPORTED"), "import")
    check(ok(sim.run("VERIFY_TEX"), "GV2_VERIFY_TEX_SUCCESS"), "verify_tex")


def to_snapshot(sim, args=None):
    to_textures(sim)
    lg = sim.run("SNAPSHOT", args=args)
    check(ok(lg, "GV2_SNAPSHOT_SUCCESS"), "snapshot: " + text(lg)[-400:])


def apply_all(sim, limit=20):
    n = 0
    while n < limit:
        lg = sim.run("APPLY", CONFIRM_APPLY)
        if "GV2_APPLY_NOTHING_TO_DO" in text(lg):
            return n
        check(ok(lg, "GV2_APPLY_BATCH_DONE"), "apply batch: " + text(lg)[-500:])
        n += 1
    raise AssertionError("apply did not finish")


def revert_all(sim, args=None, limit=20):
    n = 0
    while n < limit:
        lg = sim.run("REVERT", CONFIRM_REVERT, args=args)
        if "GV2_REVERT_NOTHING_TO_DO" in text(lg):
            return n
        check(ok(lg, "GV2_REVERT_BATCH_DONE"), "revert batch: " + text(lg)[-500:])
        n += 1
    raise AssertionError("revert did not finish")


def test(fn):
    name = fn.__name__
    try:
        RESULTS[name] = {"pass": True, **(fn() or {})}
    except Exception as exc:  # noqa: BLE001
        RESULTS[name] = {"pass": False, "error": "%s: %s" % (type(exc).__name__, exc),
                         "trace": traceback.format_exc()[-1500:]}
    return fn


# ============================================================================================ static
def module_level_ue(src):
    """Names of module-level statements that import or reference unreal / call U()."""
    hits = []
    for node in ast.parse(src).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Import, ast.ImportFrom)) and any(
                    a.name == "unreal" for a in getattr(sub, "names", [])):
                hits.append("import unreal@%d" % sub.lineno)
            if isinstance(sub, ast.Name) and sub.id in ("unreal", "U"):
                hits.append("%s@%d" % (sub.id, sub.lineno))
    return hits


FORBIDDEN = ("delete_asset", "delete_loaded_asset", "delete_material_expression", "save_dirty_packages", "save_packages",
             "save_current_level", "reload_packages", "load_level", "load_map", "EditorLevelLibrary",
             "request_end_play_map", "end_play_map", "quit_editor", "clear_all_material_instance_parameters",
             "recompile_material", "set_material_instance_parent", "replace_existing_settings")


def forbidden(src):
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return sorted(n for n in FORBIDDEN if n in names)


@test
def static_no_ue_at_module_level():
    src = TOOL.read_text(encoding="utf-8")
    hits = module_level_ue(src)
    check(hits == [], "module-level UE: %s" % hits)
    bad = src + "\nimport unreal\nX = unreal.load_asset('/Game/x')\n"
    neg = module_level_ue(bad)
    check(len(neg) >= 2, "negative control not detected")
    return {"hits": hits, "negative_control_hits": neg}


@test
def static_forbidden_apis():
    src = TOOL.read_text(encoding="utf-8")
    f = forbidden(src)
    check(f == [], "forbidden: %s" % f)
    neg = forbidden(src + "\nunreal.EditorAssetLibrary.delete_asset('x')\n")
    check(neg == ["delete_asset"], "negative control")
    # replace_existing must be False in the import task
    check(re.search(r'\("replace_existing", False\)', src), "replace_existing False")
    return {"forbidden": f, "negative_control": neg}


# ============================================================================================ positive
@test
def full_flow_apply_revert():
    s = Sim()
    try:
        prot0 = s.protected_hashes()
        check(ok(s.run("IMPORT_DRY"), "GV2_IMPORT_DRY_RUN_OK"), "import dry")
        check(not s.state["saves"] and s.state["calls"].get("import", 0) == 0, "dry mutated")
        check(ok(s.run("IMPORT"), "GV2_IMPORT_IMPORTED"), "import")
        check(sorted(s.state["saves"]) == sorted([ATLAS_V2, NORMAL_V2]), "import saves %s" % s.state["saves"])
        check(ok(s.run("VERIFY_TEX"), "GV2_VERIFY_TEX_SUCCESS"), "verify")
        a, n = s.disk(ATLAS_V2)["props"], s.disk(NORMAL_V2)["props"]
        check(a["filter"] == {"__enum__": "TF_TRILINEAR"} and a["mip_gen_settings"] == {"__enum__": "TMGS_SIMPLE_AVERAGE"}
              and a["address_x"] == {"__enum__": "TA_CLAMP"} and a["srgb"] is False
              and a["compression_settings"] == {"__enum__": "TC_MASKS"}, "atlas settings %s" % a)
        check(n["flip_green_channel"] is False and n["lod_group"] == {"__enum__": "TEXTUREGROUP_WORLD_NORMAL_MAP"}
              and n["filter"] == {"__enum__": "TF_TRILINEAR"} and n["lod_bias"] == 1 and n["never_stream"] is True
              and n["compression_settings"] == {"__enum__": "TC_NORMALMAP"}, "normal settings %s" % n)
        check(ok(s.run("SNAPSHOT_DRY"), "GV2_SNAPSHOT_DRY_RUN_OK"), "snap dry")
        lg = s.run("SNAPSHOT")
        check(ok(lg, "GV2_SNAPSHOT_SUCCESS|") and "mis=142|batches=8" in text(lg), text(lg))
        rec = s.record()
        bk = Path(rec["stages"]["snapshot"]["backup"])
        nbk = len(list(bk.rglob("*.uasset")))
        check(nbk == 142, "backup files %d" % nbk)
        check(ok(s.run("APPLY_DRY"), "GV2_APPLY_DRY_RUN_OK"), "apply dry")
        saves0 = len(s.state["saves"])
        nb = apply_all(s)
        apply_saves = s.state["saves"][saves0:]
        check(nb == 8 and sorted(apply_saves) == sorted(s.mi_paths), "apply saves %d" % len(apply_saves))
        check(ok(s.run("APPLY_VERIFY"), "GV2_APPLY_SUCCESS|"), "apply verify")
        d = s.disk(s.mi_paths[0])
        check(d["textures"] == {"GreaseMask": ATLAS_V2, "PrintNormal": NORMAL_V2}, "v2 override %s" % d)
        check(all(s.disk(p)["scalars"] == s.original_disk[p]["scalars"] for p in s.mi_paths), "scalars")
        prot_after_apply = s.protected_hashes()
        check(ok(s.run("REVERT_DRY"), "GV2_REVERT_DRY_RUN_OK"), "revert dry")
        check(stopped(s.run("REVERT"), "CONFIRM_MISSING"), "revert w/o confirm")
        nr = revert_all(s)
        check(nr == 8, "revert batches %d" % nr)
        check(ok(s.run("REVERT_VERIFY"), "GV2_REVERT_SUCCESS|run=") and "verified=142" in text(s.u.logs[-1:]), "revert verify")
        check(all(s.disk(p) == s.original_disk[p] for p in s.mi_paths), "MI disk state not exactly original")
        check(s.state["calls"].get("set_override", 0) == 284, "override clears %s" % s.state["calls"].get("set_override"))
        check(s.cfile(ATLAS_V2).exists() and s.cfile(NORMAL_V2).exists(), "v2 kept")
        # protected: everything except g1 MIs and v2 textures is byte-identical through import/apply/revert
        check(prot_after_apply == s.protected_hashes() == {k: v for k, v in prot0.items()}, "protected files changed")
        non_target = [p for p in s.state["saves"] if p not in s.mi_paths and p not in (ATLAS_V2, NORMAL_V2)]
        check(non_target == [], "non-target saves %s" % non_target)
        return {"apply_batches": nb, "revert_batches": nr, "backup_files": nbk, "saves": len(s.state["saves"]),
                "protected_files": len(prot0), "non_target_saves": 0}
    finally:
        s.close()


@test
def revert_restores_preexisting_override():
    s = Sim(pre_override=3)
    try:
        to_snapshot(s)
        apply_all(s)
        check(ok(s.run("APPLY_VERIFY"), "GV2_APPLY_SUCCESS"), "apply verify")
        revert_all(s)
        check(ok(s.run("REVERT_VERIFY"), "GV2_REVERT_SUCCESS"), "revert verify")
        d0, d9 = s.disk(s.mi_paths[0]), s.disk(s.mi_paths[9])
        check(d0["textures"] == {"GreaseMask": ATLAS_V1}, "override must be restored, not cleared: %s" % d0)
        check(d9["textures"] == {}, "inherited must be cleared: %s" % d9)
        check(all(s.disk(p) == s.original_disk[p] for p in s.mi_paths), "exact restore")
        return {"restored_overrides": 3, "cleared": 142 * 2 - 3}
    finally:
        s.close()


@test
def verify_tex_pending_placeholder():
    s = Sim(faults={"placeholder": {ATLAS_V2: 1}})
    try:
        check(ok(s.run("IMPORT"), "GV2_IMPORT_IMPORTED"), "import")
        lg = s.run("VERIFY_TEX")
        check("GV2_VERIFY_TEX_PENDING" in text(lg) and "SUCCESS" not in text(lg), text(lg))
        check(s.record()["stages"]["import"]["verified"] is False, "must not verify")
        check(ok(s.run("VERIFY_TEX"), "GV2_VERIFY_TEX_SUCCESS"), "retry")
        return {"pending_then_success": True}
    finally:
        s.close()


# ============================================================================================ negative controls
@test
def neg_sha_mismatch():
    s = Sim()
    try:
        f = s.tmp / "DerivedAssets/S3Marble/GreaseV2_20261008/T_HP_S03_PrintNormal_v2.png"
        b = bytearray(f.read_bytes())
        b[-20] ^= 1
        f.write_bytes(bytes(b))
        lg = s.run("IMPORT")
        check(stopped(lg, "SOURCE_HASH_MISMATCH|T_HP_S03_PrintNormal_v2.png"), text(lg))
        check(s.state["calls"].get("import", 0) == 0 and not s.state["saves"], "imported anyway")
        check(not (s.tmp / "Saved/CodexConductor/GreaseV2_20261008/grease_v2_ue_record.json").exists(), "record written")
        return {"refused": "SOURCE_HASH_MISMATCH"}
    finally:
        s.close()


@test
def neg_asset_exists():
    s = Sim()
    try:
        s.state["objects"] = {}
        spec = tex_spec("TC_NORMALMAP", "TEXTUREGROUP_WORLD", "TMGS_FROM_TEXTURE_GROUP", "TF_DEFAULT", 0, False,
                        "TA_WRAP", False, [1024, 1024])
        f = s.cfile(NORMAL_V2)
        f.write_text(json.dumps(spec), encoding="utf-8")
        h0 = hashlib.sha256(f.read_bytes()).hexdigest()
        lg = s.run("IMPORT")
        check(stopped(lg, "TEXTURE_EXISTS|" + NORMAL_V2), text(lg))
        check(s.state["calls"].get("import", 0) == 0 and not s.state["saves"], "mutated")
        check(hashlib.sha256(f.read_bytes()).hexdigest() == h0, "existing asset touched")
        return {"refused": "TEXTURE_EXISTS"}
    finally:
        s.close()


@test
def neg_mi_count_differs():
    s = Sim(drop_mi=1)
    try:
        to_textures(s)
        lg = s.run("SNAPSHOT")
        check(stopped(lg, "MI_SET_DIFFERS|live=141|worklist=142"), text(lg))
        check(stopped(s.run("SNAPSHOT", args={"ack_mi_count": 142}), "MI_SET_DIFFERS"), "wrong ack accepted")
        check("snapshot" not in s.record()["stages"], "snapshot recorded")
        lg = s.run("SNAPSHOT", args={"ack_mi_count": 141})
        check(ok(lg, "GV2_SNAPSHOT_SUCCESS|") and "mis=141" in text(lg), text(lg))
        n = apply_all(s)
        check(ok(s.run("APPLY_VERIFY"), "GV2_APPLY_SUCCESS|run="), "verify")
        # extra unrecorded MI -> refused as well
        s2 = Sim()
        try:
            s2.cfile(ROOT + "/Materials/Grease/MI_HP_S03_g1_ZZZ_extra").write_text(json.dumps(
                {"cls": "MaterialInstanceConstant", "parent": MASTER, "scalars": {}, "textures": {}}), encoding="utf-8")
            to_textures(s2)
            check(stopped(s2.run("SNAPSHOT"), "MI_SET_DIFFERS|live=143"), "extra MI not refused")
        finally:
            s2.close()
        return {"refused_141": True, "wrong_ack_refused": True, "ack_141_batches": n, "extra_143_refused": True}
    finally:
        s.close()


@test
def neg_scalar_changed():
    s = Sim()
    try:
        to_snapshot(s)
        victim = s.mi_paths[3].rsplit("/", 1)[1]
        s.state["faults"]["scalar_side_effect"] = (victim, "GreaseGain", 0.123)
        lg = s.run("APPLY", CONFIRM_APPLY)
        check(stopped(lg, "READBACK_BEFORE_SAVE") and "SCALAR:GreaseGain" in text(lg), text(lg))
        check(not [p for p in s.state["saves"] if p in s.mi_paths], "MI saved after a scalar change")
        check(s.record()["stages"]["apply"]["in_progress"], "in_progress kept")
        # recovery: Don't-Save restart + fault gone -> the same batch resumes and completes
        s.state["faults"].pop("scalar_side_effect")
        s.u._restart()
        apply_all(s)
        check(ok(s.run("APPLY_VERIFY"), "GV2_APPLY_SUCCESS"), "verify after recovery")
        # scalar drift on disk before REVERT -> refused
        mi = s.u._load(s.mi_paths[2])
        mi.scalars["AtlasU0"] = 0.5
        s.u.EditorAssetLibrary.save_asset(s.mi_paths[2])
        n0 = len(s.state["saves"])
        lg = s.run("REVERT", CONFIRM_REVERT)
        check(stopped(lg, "REVERT_DRIFT|1|") and "SCALAR:AtlasU0" in text(lg), text(lg))
        check(len(s.state["saves"]) == n0, "revert saved despite scalar drift")
        return {"refused": "READBACK_BEFORE_SAVE SCALAR", "recovered": True, "revert_scalar_drift": "REVERT_DRIFT"}
    finally:
        s.close()


@test
def neg_non_target_dirtied():
    s = Sim()
    try:
        to_snapshot(s)
        s.state["faults"]["dirty_other_on_set"] = MASTER
        lg = s.run("APPLY", CONFIRM_APPLY)
        check(stopped(lg, "CENSUS_BEFORE_SAVE") and MASTER in text(lg), text(lg))
        check(not [p for p in s.state["saves"] if p in s.mi_paths or p == MASTER], "saved")
        s2 = Sim(faults={"import_dirties": V3})
        try:
            lg = s2.run("IMPORT")
            check(stopped(lg, "CENSUS_BEFORE_SAVE") and V3 in text(lg), text(lg))
            check(not s2.state["saves"], "import saved with a foreign dirty package")
        finally:
            s2.close()
        return {"apply_refused": "CENSUS_BEFORE_SAVE", "import_refused": "CENSUS_BEFORE_SAVE"}
    finally:
        s.close()


@test
def neg_lying_setters():
    out = {}
    s = Sim()
    try:
        to_snapshot(s)
        s.state["faults"]["tex_param_setter_lies"] = s.mi_paths[5].rsplit("/", 1)[1]
        lg = s.run("APPLY", CONFIRM_APPLY)
        check(stopped(lg, "READBACK_BEFORE_SAVE") and s.mi_paths[5].rsplit("/", 1)[1] in text(lg), text(lg))
        check(not [p for p in s.state["saves"] if p in s.mi_paths], "saved after a lying setter")
        out["mi_texture_setter"] = "READBACK_BEFORE_SAVE"
    finally:
        s.close()
    s = Sim(faults={"tex_setter_lies": ("T_HP_S03_GreaseAtlas_v2", "srgb")})
    try:
        lg = s.run("IMPORT")
        check(stopped(lg, "TEXTURE_SETTING_READBACK") and "srgb" in text(lg), text(lg))
        check(not s.state["saves"], "import saved with a lying setter")
        out["texture_setting_setter"] = "TEXTURE_SETTING_READBACK"
    finally:
        s.close()
    s = Sim()
    try:
        to_snapshot(s)
        apply_all(s)
        s.state["faults"]["override_clear_lies"] = True
        n0 = len(s.state["saves"])
        lg = s.run("REVERT", CONFIRM_REVERT)
        check(stopped(lg, "READBACK_BEFORE_SAVE"), text(lg))
        check(len(s.state["saves"]) == n0, "saved after a lying override clear")
        # escape hatch: Don't-Save restart, then pin the recorded inherited texture as an override
        s.u._restart()
        revert_all(s, args={"revert_pin_fallback": True})
        lg = s.run("REVERT_VERIFY")
        check(ok(lg, "GV2_REVERT_SUCCESS|") and "pinned=142" in text(lg), text(lg))
        d = s.disk(s.mi_paths[0])
        check(d["textures"] == {"GreaseMask": ATLAS_V1, "PrintNormal": NORMAL_V1}, "pinned values %s" % d)
        out["override_clear"] = "READBACK_BEFORE_SAVE, then pin fallback verified"
    finally:
        s.close()
    s = Sim(faults={"probe_lies": True})
    try:
        to_textures(s)
        lg = s.run("SNAPSHOT")
        # inherited params: probe False == entry False, so the probe lie only shows where an entry exists
        check(ok(lg, "GV2_SNAPSHOT_SUCCESS"), text(lg))
        s2 = Sim(pre_override=2, faults={"probe_lies": True})
        try:
            to_textures(s2)
            check(stopped(s2.run("SNAPSHOT"), "OVERRIDE_PROBES_DISAGREE"), "probe disagreement not refused")
        finally:
            s2.close()
        out["override_probe_disagreement"] = "SNAPSHOT_REFUSED"
    finally:
        s.close()
    return out


@test
def neg_revert_drift():
    s = Sim()
    try:
        to_snapshot(s)
        apply_all(s)
        mi = s.u._load(s.mi_paths[0])
        mi.textures["PrintNormal"] = TEX + "/T_S03_HandPrints_Roughness"          # someone repointed it after APPLY
        s.u.EditorAssetLibrary.save_asset(s.mi_paths[0])
        n0 = len(s.state["saves"])
        c0 = dict(s.state["calls"])
        lg = s.run("REVERT", CONFIRM_REVERT)
        check(stopped(lg, "REVERT_DRIFT|1|") and "MI_HP_S03_g1_P001" in text(lg), text(lg))
        check(len(s.state["saves"]) == n0 and s.state["calls"].get("set_override", 0) == c0.get("set_override", 0),
              "revert wrote despite drift")
        # APPLY_VERIFY also catches it
        check(stopped(s.run("APPLY_VERIFY"), "APPLY_VERIFY|1|"), "apply verify missed drift")
        return {"refused": "REVERT_DRIFT", "writes": 0}
    finally:
        s.close()


@test
def neg_batch_interrupted_resumes():
    s = Sim()
    try:
        to_snapshot(s)
        check(ok(s.run("APPLY", CONFIRM_APPLY), "GV2_APPLY_BATCH_DONE|"), "batch 0")
        check(ok(s.run("APPLY", CONFIRM_APPLY), "GV2_APPLY_BATCH_DONE|"), "batch 1")
        s.state["faults"]["raise_on_save"] = 5            # the 6th save of batch 2 raises
        lg = s.run("APPLY", CONFIRM_APPLY)
        check("GV2_APPLY_ERROR" in text(lg), text(lg))
        rec = s.record()["stages"]["apply"]
        check(rec["in_progress_batch"] == 2 and len(rec["done"]) == 40, "record %s" % rec["in_progress_batch"])
        batch2 = s.record()["stages"]["snapshot"]["batches"][2]
        on_disk_v2 = sum(1 for p in batch2 if s.disk(p)["textures"].get("GreaseMask") == ATLAS_V2)
        check(on_disk_v2 == 5, "saved before the interrupt: %d" % on_disk_v2)
        # dirty leftovers refuse the next call until a Don't-Save restart
        check(stopped(s.run("APPLY", CONFIRM_APPLY), "DIRTY_AT_START"), "dirty start accepted")
        s.u._restart()
        lg = s.run("APPLY", CONFIRM_APPLY)
        check(ok(lg, "GV2_APPLY_BATCH_DONE|") and "batch=2|written=15" in text(lg), text(lg))
        apply_all(s)
        check(ok(s.run("APPLY_VERIFY"), "GV2_APPLY_SUCCESS|"), "verify")
        rec = s.record()["stages"]["apply"]
        nums = [b["batch"] for b in rec["batches"]]
        check(nums == list(range(8)) and rec["batches"][2]["resumed"] is True, "batches %s" % nums)
        check(len(rec["done"]) == 142 and len(set(rec["done"])) == 142, "duplicates")
        # an interrupted REVERT resumes too
        s.state["faults"]["raise_on_save"] = 3
        check("GV2_REVERT_ERROR" in text(s.run("REVERT", CONFIRM_REVERT)), "revert interrupt")
        s.u._restart()
        revert_all(s)
        check(ok(s.run("REVERT_VERIFY"), "GV2_REVERT_SUCCESS|run=") and "verified=142" in text(s.u.logs[-1:]), "revert verify")
        check(all(s.disk(p) == s.original_disk[p] for p in s.mi_paths), "exact restore after interrupts")
        return {"resumed_batch": 2, "written_on_resume": 15, "batches": nums, "revert_resumed": True}
    finally:
        s.close()


@test
def neg_preflight_gates():
    out = {}
    for name, faults, mode, reason in (("pie", {"pie": True}, "IMPORT", "PIE_OR_SIE_ACTIVE"),
                                       ("world", {"world": "/Game/Other"}, "IMPORT", "WRONG_WORLD"),
                                       ("map_dirty", {"map_dirty": True}, "IMPORT", "DIRTY_AT_START")):
        s = Sim(faults=faults)
        try:
            lg = s.run(mode)
            check(stopped(lg, reason) and not s.state["saves"], "%s: %s" % (name, text(lg)))
            out[name] = reason
        finally:
            s.close()
    s = Sim()
    try:
        check(stopped(s.run("SNAPSHOT"), "TEXTURES_NOT_VERIFIED"), "snapshot before verify")
        to_snapshot(s)
        check(stopped(s.run("APPLY", "apply please"), "CONFIRM_MISSING"), "bad confirm")
        check(stopped(s.run("REVERT", CONFIRM_REVERT), "NOTHING_APPLIED"), "revert before apply")
        s.state["faults"]["ram"] = lambda: 3.0
        check(stopped(s.run("APPLY", CONFIRM_APPLY), "FREE_RAM_LOW"), "low ram")
        check(not [p for p in s.state["saves"] if p in s.mi_paths], "saved")
        check(stopped(s.run("NONSENSE"), "GV2_MODE_NOT_SET"), "mode")
        out.update({"order": "TEXTURES_NOT_VERIFIED", "confirm": "CONFIRM_MISSING", "ram": "FREE_RAM_LOW"})
    finally:
        s.close()
    return out


@test
def neg_protected_file_changed():
    s = Sim()
    try:
        to_snapshot(s)
        check(ok(s.run("APPLY", CONFIRM_APPLY), "GV2_APPLY_BATCH_DONE"), "batch 0")
        f = s.cfile(ROOT + "/Materials/V3/MI_HP_S03_v3_P002_F0")
        f.write_text(f.read_text(encoding="utf-8").replace('"Gain": 0.5', '"Gain": 0.6'), encoding="utf-8")
        lg = s.run("APPLY", CONFIRM_APPLY)
        check(stopped(lg, "PROTECTED_FILES_CHANGED_AFTER_SAVE|1|") and "MI_HP_S03_v3_P002_F0" in text(lg), text(lg))
        # a protected READ-BACK change (print v3 MI repointed in memory, file untouched) is caught by VERIFY
        s2 = Sim()
        try:
            to_snapshot(s2)
            apply_all(s2)
            s2.u._load(ROOT + "/Materials/V3/MI_HP_S03_v3_P003_F0").textures["NormalAtlas"] = NORMAL_V2
            lg = s2.run("APPLY_VERIFY")
            check(stopped(lg, "PROTECTED_READBACK_CHANGED_VERIFY") and "print_v3_mi" in text(lg), text(lg))
        finally:
            s2.close()
        return {"file_change": "PROTECTED_FILES_CHANGED", "readback_change": "PROTECTED_READBACK_CHANGED"}
    finally:
        s.close()


@test
def control_guard_removed_lets_lie_through():
    """Verifier-can-fail control: with both read-back calls stubbed out, a lying setter is SAVED and logged as done.
    Proves the read-back is the guard that catches it in neg_lying_setters (not some incidental refusal)."""
    src = TOOL.read_text(encoding="utf-8")
    mutated = src.replace('    check("BEFORE_SAVE")\n', '    pass\n').replace('    check("AFTER_SAVE")\n', '    pass\n')
    check(mutated != src and mutated.count("    pass\n") >= 2, "mutation failed")
    tmp_tool = Path(tempfile.mkdtemp(prefix="gv2tool_")) / "grease_v2_ue.py"
    tmp_tool.write_text(mutated, encoding="utf-8")
    s = Sim()
    try:
        to_snapshot(s)
        victim = s.mi_paths[5]
        s.state["faults"]["tex_param_setter_lies"] = victim.rsplit("/", 1)[1]
        lg = s.run("APPLY", CONFIRM_APPLY, tool=tmp_tool)
        check(ok(lg, "GV2_APPLY_BATCH_DONE"), "mutated tool should wrongly succeed: " + text(lg)[-300:])
        check(victim in s.state["saves"] and s.disk(victim)["textures"] == {}, "lie saved")
        # ...and the real APPLY_VERIFY then catches it
        s.state["faults"].pop("tex_param_setter_lies")
        apply_all(s)
        lg = s.run("APPLY_VERIFY")
        check(stopped(lg, "APPLY_VERIFY|1|") and victim.rsplit("/", 1)[1] in text(lg), "verify missed: " + text(lg)[-300:])
        return {"guard_removed_saved_lie": True, "apply_verify_caught_it": True}
    finally:
        s.close()
        shutil.rmtree(tmp_tool.parent, ignore_errors=True)


def main():
    passed = sum(1 for r in RESULTS.values() if r["pass"])
    report = {"tool": "grease_v2_ue.py", "tool_sha256": hashlib.sha256(TOOL.read_bytes()).hexdigest(),
              "fake_sha256": hashlib.sha256((HERE / "fake_unreal_gv2.py").read_bytes()).hexdigest(),
              "ran": len(RESULTS), "passed": passed, "failed": len(RESULTS) - passed, "results": RESULTS}
    (HERE / "test_grease_v2_ue_report.json").write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    for k, r in RESULTS.items():
        print("%-45s %s%s" % (k, "PASS" if r["pass"] else "FAIL", "" if r["pass"] else "  " + r["error"]))
    print("ran=%d passed=%d failed=%d" % (len(RESULTS), passed, len(RESULTS) - passed))
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
