"""S3 hand-print GREASE layer: real (saved) assets.  PREPARED, NOT RUN.  One stage per MCP call (wrappers set
HP_GREASE_STAGE; *_dry wrappers also set HP_DRY_RUN=True, which stops after the preflight and mutates nothing).

Gary 7 Oct (conductor session): "Yes, build it" -- grease sheen, NO albedo, one unified layer.

  texture         import DerivedAssets/S3Marble/Grime_20261007/T_S3MG_GreaseAtlas.png (sha pinned) ONCE as
                  /Game/Scenes/Scene3/HandPrints/Textures/T_HP_S03_GreaseAtlas (linear, TC_MASKS), save.  Create-only.
                  Marker ..._IMPORTED|NOT_YET_VERIFIED (a read in the importing call can be stale).
  texture_verify  later call: unreal.load_asset -> Texture2D, srgb False, TC_MASKS, 2048 x 2048 (the 32 x 32
                  placeholder of a still-compiling texture = PENDING, retry).            -> ..._TEXTURE_SUCCESS
  master          create-only /Game/Scenes/Scene3/HandPrints/Materials/Grease/M_HP_S03_Grease: the bench graph of
                  s3mg_bench.py:413-465 ported 1:1 (blend TRANSLUCENT set before domain DEFERRED_DECAL; Opacity =
                  saturate(GreaseMask.r x GreaseGain); Roughness = saturate(GreaseRoughMin + GreaseRoughRange x
                  GreaseMask.g); Normal = PrintNormal x NormalStrength with the U flip; NO BaseColor), save.
                  START marker first.                                                    -> ..._MASTER_BUILT
  master_verify   later call: no "Failed to compile"/"Default Material" line for it since the START marker, pixel
                  shader instructions > 0 (0 = PENDING until COMPILE_DEADLINE_S, then FAILED), domain/blend, the
                  parameter set, and MaterialEditingLibrary.get_material_property_input_node: BaseColor None,
                  Opacity/Roughness/Normal connected (MaterialEditingLibrary.h:317).   -> ..._MASTER_SUCCESS
  mi_batch        the NEXT fixed batch (<= 20) of hp_grease_mi_worklist.json (sha pinned): create the
                  MaterialInstanceConstants, parent = master, AtlasU0/V0/USize/VSize, FlipU, GreaseGain, save each.
                  Resumable (an interrupted batch is finished, never duplicated); refuses an unrecorded existing
                  asset; free RAM >= 8 GB; GC after.  Repeat until NOTHING_TO_DO.     -> ..._MI_BATCH_DONE
  mi_verify       later call: every instance via unreal.load_asset: class, parent, the 6 scalars (1e-6), master
                  defaults not overridden.                                             -> ..._MI_SUCCESS|verified=142

Every write stage: right world, no PIE, CLEAN census at start and exactly clean after its own saves; record
hp_grease_assets_record.json written BEFORE the first mutation.  Never deletes a node or an asset, never reloads
the level, never touches the level.  Markers carry run=<id>; failures log HP_GREASE_<STAGE>_STOPPED/_ERROR.
"""
import datetime
import hashlib
import json
import os
import traceback

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUT_DIR = os.path.join(PROJECT_DIR, "Saved", "CodexFlatV3", "handprints", "grease")
RECORD = os.path.join(OUT_DIR, "hp_grease_assets_record.json")
WORKLIST = os.path.join(OUT_DIR, "hp_grease_mi_worklist.json")
WORKLIST_SHA256 = "9d9c19a451f74fb9eaaae4c0a1fbf178ee0b9f72d0ca3d21bc142f1ac54ee157"
ATLAS_PNG = os.path.join(PROJECT_DIR, "DerivedAssets", "S3Marble", "Grime_20261007", "T_S3MG_GreaseAtlas.png")
ATLAS_PNG_SHA256 = "8f85307b26db11725f31c8427381af46b5b4ea5507f6f50473d052333a553599"
ROOT = "/Game/Scenes/Scene3/HandPrints"
TEX_DIR = ROOT + "/Textures"
GREASE_TEX_NAME = "T_HP_S03_GreaseAtlas"
GREASE_TEX = TEX_DIR + "/" + GREASE_TEX_NAME
PRINT_NORMAL = TEX_DIR + "/T_S03_HandPrints_Normal"          # imported 6 Oct (hp_import_stages_record.json)
MAT_DIR = ROOT + "/Materials/Grease"
MASTER_NAME = "M_HP_S03_Grease"
MASTER = MAT_DIR + "/" + MASTER_NAME
EXPECTED_TEX_SIZE = [2048, 2048]
COMPILE_DEADLINE_S = 600
LOG_FAIL_PATTERNS = ("Failed to compile", "Default Material will be used")
MI_BATCH_MAX = 20
MIN_FREE_RAM_GB = 8.0
GREASE = {"GreaseGain": 1.0, "GreaseRoughMin": 0.30, "GreaseRoughRange": 0.25, "NormalStrength": 0.25}  # s3mg_bench.py:112
ATLAS_PARAMS = ("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize", "FlipU", "GlobalFlipU", "GlobalFlipV")
MASTER_SCALARS = ATLAS_PARAMS + ("GreaseGain", "GreaseRoughMin", "GreaseRoughRange", "NormalStrength")
MI_SCALARS = ("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize", "FlipU", "GreaseGain")
CUSTOM = {   # verbatim from s3mg_bench.py CUSTOM (the graph Gary saw in the C bench)
    "AtlasUV": {"inputs": ["UV", "U0", "V0", "US", "VS", "FlipU", "GlobalFlipU", "GlobalFlipV"], "output": 2,
                "code": ("float fu = abs(saturate(FlipU) - saturate(GlobalFlipU));\n"
                         "float u = lerp(UV.x, 1.0 - UV.x, fu);\n"
                         "float v = lerp(UV.y, 1.0 - UV.y, saturate(GlobalFlipV));\n"
                         "return float2(U0, V0) + float2(u, v) * float2(US, VS);")},
    "GreaseOpacity": {"inputs": ["M", "Gain"], "output": 1, "code": "return saturate(M.r * Gain);"},
    "GreaseRough": {"inputs": ["M", "RMin", "RRange"], "output": 1, "code": "return saturate(RMin + RRange * M.g);"},
    "StainNormal": {"inputs": ["N", "Strength", "FlipU", "GlobalFlipU"], "output": 3,
                    "code": ("float fu = abs(saturate(FlipU) - saturate(GlobalFlipU));\n"
                             "float3 n = N;\n"
                             "n.x *= (fu > 0.5) ? -1.0 : 1.0;\n"
                             "n.xy *= Strength;\n"
                             "return normalize(float3(n.xy, max(n.z, 1e-3)));")},
}
STAGE = globals().get("HP_GREASE_STAGE")
DRY = bool(globals().get("HP_DRY_RUN"))


class StageError(RuntimeError):
    pass


def require(cond, msg):
    if not cond:
        raise StageError(msg)


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def census():
    def names(pkgs):
        return sorted(str(p.get_path_name()).split(".", 1)[0] for p in pkgs)
    return {"maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def path_of(obj):
    return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]


def read_record():
    if not os.path.isfile(RECORD):
        return {"worklist_sha256": WORKLIST_SHA256, "stages": {}}
    with open(RECORD, encoding="utf-8") as fh:
        rec = json.load(fh)
    require(rec.get("worklist_sha256") == WORKLIST_SHA256, "RECORD_FOR_OTHER_WORKLIST")
    return rec


def write_record(rec):
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = RECORD + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, RECORD)


def preflight(clean=True):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    if clean:
        before = census()
        require(not before["maps"] and not before["content"], "DIRTY_AT_START|" + json.dumps(before))


def end_clean():
    after = census()
    require(after == {"maps": [], "content": []}, "DIRTY_AFTER|" + json.dumps(after))


def log_path():
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_log_dir()), "PussStage.log")


def log_failures_since(marker, names):
    with open(log_path(), encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    start = None
    for i, line in enumerate(lines):
        if marker in line:
            start = i
    require(start is not None, "START_MARKER_NOT_IN_LOG|" + marker)
    return [ln.strip()[:300] for ln in lines[start:]
            if any(p in ln for p in LOG_FAIL_PATTERNS) and any(n in ln for n in names)]


# ----------------------------------------------------------------------------------------------- texture
def stage_texture(run):
    preflight()
    rec = read_record()
    require("texture" not in rec["stages"], "TEXTURE_STAGE_ALREADY_RECORDED")
    require(os.path.isfile(ATLAS_PNG) and sha256(ATLAS_PNG) == ATLAS_PNG_SHA256, "SOURCE_HASH_MISMATCH")
    require(not unreal.EditorAssetLibrary.does_asset_exist(GREASE_TEX), "TEXTURE_EXISTS|" + GREASE_TEX)
    require(unreal.EditorAssetLibrary.does_asset_exist(PRINT_NORMAL), "PRINT_NORMAL_MISSING")
    if DRY:
        end_clean()
        unreal.log("HP_GREASE_TEXTURE_DRY_RUN_OK|run=%s|mutated=0" % run)
        return
    rec["stages"]["texture"] = {"run": run, "started_utc": utc(), "saved": False, "verified": False,
                                "asset": GREASE_TEX, "source_sha256": ATLAS_PNG_SHA256}
    write_record(rec)
    task = unreal.AssetImportTask()
    for k, v in (("filename", ATLAS_PNG), ("destination_path", TEX_DIR), ("destination_name", GREASE_TEX_NAME),
                 ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    task = None
    tex = unreal.EditorAssetLibrary.load_asset(GREASE_TEX)
    require(isinstance(tex, unreal.Texture2D), "TEXTURE_IMPORT_FAILED")
    tex.modify()
    tex.set_editor_property("srgb", False)
    tex.modify()
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
    tex = None
    require(unreal.EditorAssetLibrary.save_asset(GREASE_TEX, only_if_is_dirty=False), "SAVE_FAILED|" + GREASE_TEX)
    end_clean()
    rec["stages"]["texture"]["saved"] = True
    write_record(rec)
    unreal.SystemLibrary.collect_garbage()
    unreal.log("HP_GREASE_TEXTURE_IMPORTED|run=%s|NOT_YET_VERIFIED: send the texture_verify call" % run)


def stage_texture_verify(run):
    preflight(clean=False)
    rec = read_record()
    st = rec["stages"].get("texture") or {}
    require(st.get("saved") is True, "TEXTURE_NOT_IMPORTED")
    require(st.get("verified") is not True, "TEXTURE_ALREADY_VERIFIED")
    tex = unreal.load_asset(GREASE_TEX)
    require(isinstance(tex, unreal.Texture2D), "TEXTURE_CLASS")
    size = [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]
    srgb = bool(tex.get_editor_property("srgb"))
    comp = tex.get_editor_property("compression_settings")
    tex = None
    if DRY:
        unreal.log("HP_GREASE_TEXTURE_VERIFY_DRY_RUN_OK|run=%s|size=%s|mutated=0" % (run, size))
        return
    require(srgb is False, "TEXTURE_SRGB")
    require(comp == unreal.TextureCompressionSettings.TC_MASKS, "TEXTURE_COMPRESSION|%s" % comp)
    if size != EXPECTED_TEX_SIZE:
        require(max(size) <= 32, "TEXTURE_SIZE|%s" % size)
        unreal.log_warning("HP_GREASE_TEXTURE_PENDING|run=%s|size=%s|placeholder: retry texture_verify" % (run, size))
        return
    st.update({"verified": True, "verify_run": run, "size": size})
    write_record(rec)
    unreal.log("HP_GREASE_TEXTURE_SUCCESS|run=%s|size=%s|srgb=0|TC_MASKS" % (run, size))


# ----------------------------------------------------------------------------------------------- master
class Graph:
    def __init__(self, mat):
        self.mat = mat
        self.mel = unreal.MaterialEditingLibrary

    def node(self, cls, x, y, **props):
        n = self.mel.create_material_expression(self.mat, cls, x, y)
        require(n is not None, "CREATE_NODE|" + cls.__name__)
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    def link(self, a, a_out, b, b_in):
        ok = self.mel.connect_material_expressions(a, a_out, b, b_in)
        if not ok and len(self.mel.get_material_expression_input_names(b)) == 1:
            ok = self.mel.connect_material_expressions(a, a_out, b, "")
        require(ok, "CONNECT|%s.%s->%s.%s" % (a.get_name(), a_out, b.get_name(), b_in))

    def prop(self, a, a_out, prop):
        require(self.mel.connect_material_property(a, a_out, prop), "CONNECT_PROP|%s" % prop)

    def custom(self, x, y, name):
        spec = CUSTOM[name]
        out_type = {1: "CMOT_FLOAT1", 2: "CMOT_FLOAT2", 3: "CMOT_FLOAT3"}[spec["output"]]
        n = self.node(unreal.MaterialExpressionCustom, x, y, description=name, code=spec["code"],
                      output_type=getattr(unreal.CustomMaterialOutputType, out_type))
        ins = []
        for in_name in spec["inputs"]:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", in_name)
            ins.append(ci)
        n.set_editor_property("inputs", ins)
        return n

    def scalar(self, name, value, x, y):
        return self.node(unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name,
                         default_value=float(value), group="HPGrease")


def build_master(grease_tex, norm_tex):
    """Port of s3mg_bench.py build_grease_master (413-465); create-only."""
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(MASTER_NAME, MAT_DIR, unreal.Material,
                                                                  unreal.MaterialFactoryNew())
    require(mat is not None, "MASTER_CREATE")
    mat.modify()
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)          # blend BEFORE domain
    require(mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_TRANSLUCENT, "BLEND")
    mat.modify()
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
    require(mat.get_editor_property("material_domain") == unreal.MaterialDomain.MD_DEFERRED_DECAL, "DOMAIN")
    require(mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_TRANSLUCENT, "BLEND_2")
    g = Graph(mat)
    ST = unreal.MaterialSamplerType
    uv = g.node(unreal.MaterialExpressionTextureCoordinate, -1800, 0, coordinate_index=0)
    defaults = dict(zip(ATLAS_PARAMS, (0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0)), **GREASE)
    p = {n: g.scalar(n, defaults[n], -1800, 120 + 90 * i) for i, n in enumerate(MASTER_SCALARS)}
    auv = g.custom(-1400, 200, "AtlasUV")
    g.link(uv, "", auv, "UV")
    for pin, name in (("U0", "AtlasU0"), ("V0", "AtlasV0"), ("US", "AtlasUSize"), ("VS", "AtlasVSize"),
                      ("FlipU", "FlipU"), ("GlobalFlipU", "GlobalFlipU"), ("GlobalFlipV", "GlobalFlipV")):
        g.link(p[name], "", auv, pin)
    mask = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1000, 0, parameter_name="GreaseMask",
                  texture=grease_tex, sampler_type=ST.SAMPLERTYPE_MASKS, group="HPGrease")
    g.link(auv, "", mask, "UVs")
    nrm = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1000, 400, parameter_name="PrintNormal",
                 texture=norm_tex, sampler_type=ST.SAMPLERTYPE_NORMAL, group="HPGrease")
    g.link(auv, "", nrm, "UVs")
    op = g.custom(-600, 0, "GreaseOpacity")
    g.link(mask, "RGB", op, "M")
    g.link(p["GreaseGain"], "", op, "Gain")
    rg = g.custom(-600, 200, "GreaseRough")
    g.link(mask, "RGB", rg, "M")
    g.link(p["GreaseRoughMin"], "", rg, "RMin")
    g.link(p["GreaseRoughRange"], "", rg, "RRange")
    nn = g.custom(-600, 400, "StainNormal")
    g.link(nrm, "RGB", nn, "N")
    g.link(p["NormalStrength"], "", nn, "Strength")
    g.link(p["FlipU"], "", nn, "FlipU")
    g.link(p["GlobalFlipU"], "", nn, "GlobalFlipU")
    MP = unreal.MaterialProperty
    g.prop(op, "", MP.MP_OPACITY)
    g.prop(rg, "", MP.MP_ROUGHNESS)
    g.prop(nn, "", MP.MP_NORMAL)              # deliberately NO MP_BASE_COLOR (Gary: no albedo)
    unreal.MaterialEditingLibrary.layout_material_expressions(mat)
    errs = [str(e) for e in (unreal.MaterialEditingLibrary.recompile_material(mat) or [])]
    require(not errs, "MASTER_COMPILE|" + json.dumps(errs[:6]))
    return mat


def stage_master(run):
    preflight()
    rec = read_record()
    require((rec["stages"].get("texture") or {}).get("verified") is True, "TEXTURE_NOT_VERIFIED")
    require("master" not in rec["stages"], "MASTER_STAGE_ALREADY_RECORDED")
    require(not unreal.EditorAssetLibrary.does_asset_exist(MASTER), "MASTER_EXISTS|" + MASTER)
    if DRY:
        end_clean()
        unreal.log("HP_GREASE_MASTER_DRY_RUN_OK|run=%s|mutated=0" % run)
        return
    marker = "HP_GREASE_MASTER_START|run=%s" % run
    unreal.log(marker)
    rec["stages"]["master"] = {"run": run, "start_marker": marker, "built_utc": utc(), "saved": False,
                               "verified": False, "asset": MASTER, "verify_attempts": 0}
    write_record(rec)
    grease_tex = unreal.load_asset(GREASE_TEX)
    norm_tex = unreal.load_asset(PRINT_NORMAL)
    require(grease_tex is not None and norm_tex is not None, "MASTER_TEXTURES")
    mat = build_master(grease_tex, norm_tex)
    mat = grease_tex = norm_tex = None
    require(unreal.EditorAssetLibrary.save_asset(MASTER, only_if_is_dirty=False), "SAVE_FAILED|" + MASTER)
    end_clean()
    rec["stages"]["master"]["saved"] = True
    write_record(rec)
    unreal.SystemLibrary.collect_garbage()
    unreal.log("HP_GREASE_MASTER_BUILT|run=%s|recompile_errors=0|NOT_YET_VERIFIED: send master_verify after ~30 s" % run)


def stage_master_verify(run):
    preflight(clean=False)
    rec = read_record()
    st = rec["stages"].get("master") or {}
    require(st.get("saved") is True, "MASTER_NOT_BUILT")
    require(st.get("verified") is not True, "MASTER_ALREADY_VERIFIED")
    require(st.get("failed") is not True, "MASTER_ALREADY_FAILED|" + str(st.get("failure")))
    if DRY:
        unreal.log("HP_GREASE_MASTER_VERIFY_DRY_RUN_OK|run=%s|mutated=0" % run)
        return
    bad = log_failures_since(st["start_marker"], (MASTER_NAME,))
    st["verify_attempts"] = int(st.get("verify_attempts", 0)) + 1
    if bad:
        st.update({"failed": True, "failure": bad[:5]})
        write_record(rec)
        raise StageError("COMPILE_FAILED_IN_LOG|" + json.dumps(bad[:3]))
    m = unreal.load_asset(MASTER)
    require(isinstance(m, unreal.Material), "MASTER_CLASS")
    require(m.get_editor_property("material_domain") == unreal.MaterialDomain.MD_DEFERRED_DECAL, "MASTER_DOMAIN")
    require(m.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_TRANSLUCENT, "MASTER_BLEND")
    mel = unreal.MaterialEditingLibrary
    scalars = sorted(str(n) for n in mel.get_scalar_parameter_names(m))
    textures = sorted(str(n) for n in mel.get_texture_parameter_names(m))
    require(scalars == sorted(MASTER_SCALARS), "MASTER_SCALARS|%s" % scalars)
    require(textures == ["GreaseMask", "PrintNormal"], "MASTER_TEXTURES|%s" % textures)
    MP = unreal.MaterialProperty
    require(mel.get_material_property_input_node(m, MP.MP_BASE_COLOR) is None, "BASE_COLOR_CONNECTED")
    for prop in (MP.MP_OPACITY, MP.MP_ROUGHNESS, MP.MP_NORMAL):
        require(mel.get_material_property_input_node(m, prop) is not None, "NOT_CONNECTED|%s" % prop)
    ps = int(mel.get_statistics(m).get_editor_property("num_pixel_shader_instructions"))
    m = None
    age = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.datetime.fromisoformat(st["built_utc"])).total_seconds()
    if ps <= 0:
        if age > COMPILE_DEADLINE_S:
            st.update({"failed": True, "failure": "COMPILE_TIMEOUT age=%.0fs" % age})
            write_record(rec)
            raise StageError("COMPILE_TIMEOUT|age=%.0f" % age)
        write_record(rec)
        unreal.log_warning("HP_GREASE_MASTER_PENDING|run=%s|age=%.0fs|ps=0|retry master_verify" % (run, age))
        return
    st.update({"verified": True, "verified_ps": ps, "verify_run": run})
    write_record(rec)
    unreal.log("HP_GREASE_MASTER_SUCCESS|run=%s|ps_instructions=%d|base_color=none|log_failures=0" % (run, ps))


# ----------------------------------------------------------------------------------------------- instances
def free_ram_gb():
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    require(ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)), "RAM_QUERY_FAILED")
    return status.ullAvailPhys / float(1 << 30)


def load_worklist():
    require(os.path.isfile(WORKLIST) and sha256(WORKLIST) == WORKLIST_SHA256, "WORKLIST_SHA256_MISMATCH")
    with open(WORKLIST, encoding="utf-8") as fh:
        work = json.load(fh)
    require(work.get("master") == MASTER, "WORKLIST_MASTER")
    items = work["instances"]
    require(len({i["name"] for i in items}) == len(items), "WORKLIST_DUPLICATE_NAMES")
    require(all(len([j for j in items if j["batch"] == i["batch"]]) <= MI_BATCH_MAX for i in items), "BATCH_TOO_BIG")
    return work, items


def next_batch(items, st):
    """The lowest batch number with an unfinished item; an interrupted batch (in_progress) first."""
    done = set(st["done"])
    if st.get("in_progress"):
        return sorted({i["batch"] for i in items if i["name"] in set(st["in_progress"])})[0]
    pending = sorted({i["batch"] for i in items if i["name"] not in done})
    return pending[0] if pending else None


def stage_mi_batch(run):
    preflight()
    rec = read_record()
    require((rec["stages"].get("master") or {}).get("verified") is True, "MASTER_NOT_VERIFIED")
    work, items = load_worklist()
    st = rec["stages"].setdefault("mi", {"done": [], "in_progress": [], "batches": [], "verified": False})
    b = next_batch(items, st)
    if b is None:
        unreal.log("HP_GREASE_MI_BATCH_NOTHING_TO_DO|run=%s|done=%d" % (run, len(st["done"])))
        return
    batch = [i for i in items if i["batch"] == b and i["name"] not in set(st["done"])]
    for i in batch:
        exists = unreal.EditorAssetLibrary.does_asset_exist(i["path"])
        require(not exists or i["name"] in set(st.get("in_progress") or []), "MI_EXISTS_UNRECORDED|" + i["name"])
    ram = free_ram_gb()
    require(ram >= MIN_FREE_RAM_GB, "FREE_RAM_LOW|%.1f" % ram)
    if DRY:
        end_clean()
        unreal.log("HP_GREASE_MI_BATCH_DRY_RUN_OK|run=%s|batch=%d|size=%d|done=%d|total=%d|free_ram_gb=%.1f|mutated=0"
                   % (run, b, len(batch), len(st["done"]), len(items), ram))
        return
    st["in_progress"] = [i["name"] for i in batch]
    write_record(rec)
    master = unreal.load_asset(MASTER)
    require(master is not None, "MASTER_MISSING")
    mel = unreal.MaterialEditingLibrary
    for i in batch:
        if unreal.EditorAssetLibrary.does_asset_exist(i["path"]):
            mi = unreal.load_asset(i["path"])                         # resume: re-set and re-save
        else:
            mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                i["name"], work["mi_dir"], unreal.MaterialInstanceConstant,
                unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "MI_CREATE_FAILED|" + i["name"])
        mel.set_material_instance_parent(mi, master)
        for k in MI_SCALARS:
            mel.set_material_instance_scalar_parameter_value(mi, k, float(i["scalars"][k]))
        mel.update_material_instance(mi)
        require(unreal.EditorAssetLibrary.save_asset(i["path"], only_if_is_dirty=False), "SAVE_FAILED|" + i["path"])
        mi = None
    master = None
    end_clean()
    st["done"] = sorted(set(st["done"]) | {i["name"] for i in batch})
    st["in_progress"] = []
    st["batches"].append({"run": run, "batch": b, "names": [i["name"] for i in batch], "free_ram_gb": round(ram, 2)})
    write_record(rec)
    unreal.SystemLibrary.collect_garbage()
    unreal.log("HP_GREASE_MI_BATCH_DONE|run=%s|batch=%d|created=%d|done=%d|remaining=%d|NOT_YET_VERIFIED"
               % (run, b, len(batch), len(st["done"]), len(items) - len(st["done"])))


def stage_mi_verify(run):
    preflight(clean=False)
    rec = read_record()
    st = rec["stages"].get("mi") or {}
    work, items = load_worklist()
    require(set(st.get("done") or []) == {i["name"] for i in items} and not st.get("in_progress"), "MI_NOT_ALL_CREATED")
    if DRY:
        unreal.log("HP_GREASE_MI_VERIFY_DRY_RUN_OK|run=%s|n=%d|mutated=0" % (run, len(items)))
        return
    mel = unreal.MaterialEditingLibrary
    bad = []
    for i in items:
        mi = unreal.load_asset(i["path"])
        if not isinstance(mi, unreal.MaterialInstanceConstant):
            bad.append("CLASS|" + i["name"])
            continue
        if path_of(mi.get_editor_property("parent")) != MASTER:
            bad.append("PARENT|" + i["name"])
        for k in MI_SCALARS:
            got = float(mel.get_material_instance_scalar_parameter_value(mi, k))
            if abs(got - float(i["scalars"][k])) > 1e-6:
                bad.append("SCALAR|%s|%s|%s" % (i["name"], k, got))
        for k, v in work["master_scalar_defaults"].items():
            got = float(mel.get_material_instance_scalar_parameter_value(mi, k))
            if abs(got - float(v)) > 1e-6:
                bad.append("DEFAULT|%s|%s|%s" % (i["name"], k, got))
        mi = None
    if bad:
        st["verify_failures"] = bad[:20]
        write_record(rec)
        raise StageError("MI_VERIFY|%d|%s" % (len(bad), json.dumps(bad[:5])))
    end_clean()
    st.update({"verified": True, "verify_run": run, "verified_count": len(items)})
    write_record(rec)
    unreal.SystemLibrary.collect_garbage()
    unreal.log("HP_GREASE_MI_SUCCESS|run=%s|verified=%d" % (run, len(items)))


def main():
    run = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    stages = {"texture": stage_texture, "texture_verify": stage_texture_verify, "master": stage_master,
              "master_verify": stage_master_verify, "mi_batch": stage_mi_batch, "mi_verify": stage_mi_verify}
    try:
        require(STAGE in stages, "HP_GREASE_STAGE_NOT_SET|%s" % STAGE)
        stages[STAGE](run)
    except StageError as exc:
        unreal.log_error("HP_GREASE_%s_STOPPED|run=%s|reason=%s|census=%s"
                         % (str(STAGE).upper(), run, exc, json.dumps(census())))
    except Exception:
        unreal.log_error("HP_GREASE_%s_ERROR|run=%s|traceback=%s|census=%s"
                         % (str(STAGE).upper(), run, traceback.format_exc().replace("\n", "\\n"),
                            json.dumps(census())))


main()
