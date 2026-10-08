"""S3 hand-print GREASE TINT layer (Gary 8 Oct: "faintly red, only in their darkest/thickest parts, so they don't get
totally lost").  PREPARED, NOT RUN.  One stage per MCP call: wrappers set HP_TINT_STAGE; *_dry wrappers also set
HP_DRY_RUN=True (every gate, nothing mutated); place / revert also need HP_TINT_CONFIRM.

WHY A SECOND (TWIN) DECAL LAYER AND NOT A NEW MASTER + REPARENT:
  A deferred decal has ONE opacity for every attribute it writes.  UE 5.8 DecalCommon.ush:110-112 (non-Substrate
  DBuffer path) encodes MultiOpacity = Opacity into DBufferA (colour), B (normal) and C (roughness) alike;
  DecalCommon.ush:148-150 (GBuffer path) and :65-67 (Substrate) do the same.  The grease sheen needs roughness at
  opacity = GreaseMask.r x GreaseGain over the whole print; connecting BaseColor to that master would repaint the
  marble colour wherever the sheen is (the decal cannot read the marble colour underneath to preserve it).  The
  colour must therefore come from a separate decal whose Opacity is the tint gate and which writes ONLY BaseColor
  (no Roughness/Normal pin -> the existing sheen stays exactly as it is).  The old master and its 142 MIs are not
  touched at all.

Stages (HP_TINT_STAGE):
  master          create-only <TINT_DIR>/M_HP_S03_GreaseTint: blend TRANSLUCENT then domain DEFERRED_DECAL;
                  BaseColor = TintColor; Opacity = TintStrength x smoothstep(TintLo, TintHi, GreaseMask.r) through
                  the SAME AtlasUV custom node as the grease master; nothing else connected.  Backs up the grease
                  material folder first.                                         -> HP_TINT_MASTER_BUILT (not verified)
  master_verify   LATER call: no compile failure in the log since the START marker, ps instructions > 0, domain,
                  blend, parameter sets, defaults read back, BaseColor+Opacity connected, Roughness/Normal/Metallic/
                  Specular/Emissive NOT connected.                               -> HP_TINT_MASTER_SUCCESS
  mi_batch        next fixed batch (<= 20, the grease worklist's batch numbers) of PARALLEL instances
                  MI_HP_S03_t1_<same suffix as the grease MI>, parent = tint master, AtlasU0/V0/USize/VSize/FlipU;
                  resumable; refuses an unrecorded existing asset.  Repeat until NOTHING_TO_DO.   -> HP_TINT_MI_BATCH_DONE
  mi_verify       LATER call: 142 x class/parent/5 scalars/tint defaults not overridden.  -> HP_TINT_MI_SUCCESS
  place           (DRY / APPLY, confirm "APPLY HPS03T") one twin DecalActor per live HP_S03G grease decal (live grease
                  digest must equal hp_place_grease_record.json grease_digest_after): same transform/scale/size/
                  parent, sort order +2, tint MI for the grease MI, label "HP_S03T ...", tags HP_S03T(+run).
                  umap backup + record BEFORE any change; every twin read back; census exactly the level; save.
                                                                                  -> HP_TINT_PLACE_SUCCESS
  place_verify    LATER call, read-only: every twin paired with its grease decal.  -> HP_TINT_PLACE_VERIFY_SUCCESS
  revert          (REVERT_DRY / REVERT, confirm "REVERT HPS03T") umap backup -> destroy the twins (asserted) -> grease
                  digest unchanged -> census exactly the level -> save -> clean -> record archived.
                  Assets are left in place (unused; no asset is ever deleted).      -> HP_TINT_REVERT_SUCCESS
Never deletes a node or an asset, never reloads the level, refuses PIE.  Markers carry run=<id>; failures log
HP_TINT_<STAGE>_STOPPED / _ERROR with the census.
"""
import datetime
import hashlib
import json
import os
import shutil
import traceback

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
OUT_DIR = os.path.join(PROJECT_DIR, "Saved", "CodexFlatV3", "handprints", "grease")
RECORD = os.path.join(OUT_DIR, "hp_grease_tint_record.json")                 # asset stages
PLACE_RECORD = os.path.join(OUT_DIR, "hp_grease_tint_place_record.json")     # level stages
GREASE_ASSETS_RECORD = os.path.join(OUT_DIR, "hp_grease_assets_record.json")
GREASE_PLACE_RECORD = os.path.join(OUT_DIR, "hp_place_grease_record.json")
WORKLIST = os.path.join(OUT_DIR, "hp_grease_mi_worklist.json")
WORKLIST_SHA256 = "9d9c19a451f74fb9eaaae4c0a1fbf178ee0b9f72d0ca3d21bc142f1ac54ee157"
ROOT = "/Game/Scenes/Scene3/HandPrints"
GREASE_TEX = ROOT + "/Textures/T_HP_S03_GreaseAtlas"
GREASE_MASTER = ROOT + "/Materials/Grease/M_HP_S03_Grease"
GREASE_DIR = ROOT + "/Materials/Grease"
TINT_DIR = ROOT + "/Materials/GreaseTint"
MASTER_NAME = "M_HP_S03_GreaseTint"
MASTER = TINT_DIR + "/" + MASTER_NAME
GREASE_MI_PREFIX, TINT_MI_PREFIX = "MI_HP_S03_g1_", "MI_HP_S03_t1_"
COMPILE_DEADLINE_S = 600
LOG_FAIL_PATTERNS = ("Failed to compile", "Default Material will be used")
MI_BATCH_MAX = 20
MIN_FREE_RAM_GB = 8.0
# Defaults: gate on the RAW print thickness (GreaseMask.r, atlas R = feathered grease opacity), so faint (gain 0.6)
# prints keep a red core too.  Measured on T_S3MG_GreaseAtlas.png (texels with R > 0.02): 0.40/0.70 touches 21 %,
# > half strength on 5.7 %; the brief's 0.65/0.95 touches 1.7 % (atlas R max 0.949, p99 0.671) = effectively nothing.
TINT_SCALARS = {"TintStrength": 0.55, "TintLo": 0.45, "TintHi": 0.75}   # swatch E (previews/tint_swatch_EFG.png)
TINT_COLOR = (0.155, 0.007, 0.005, 1.0)              # linear, dried blood (sRGB ~110,20,15); Gary picked swatch E 8 Oct
ATLAS_PARAMS = ("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize", "FlipU", "GlobalFlipU", "GlobalFlipV")
MASTER_SCALARS = ATLAS_PARAMS + tuple(TINT_SCALARS)
MI_SCALARS = ("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize", "FlipU")
ATLAS_UV_CODE = ("float fu = abs(saturate(FlipU) - saturate(GlobalFlipU));\n"     # == hp_grease_assets.py CUSTOM
                 "float u = lerp(UV.x, 1.0 - UV.x, fu);\n"
                 "float v = lerp(UV.y, 1.0 - UV.y, saturate(GlobalFlipV));\n"
                 "return float2(U0, V0) + float2(u, v) * float2(US, VS);")
TINT_ALPHA_CODE = ("float t = saturate((M.r - Lo) / max(Hi - Lo, 1e-4));\n"
                   "return saturate(Strength) * t * t * (3.0 - 2.0 * t);")
CUSTOM = {
    "AtlasUV": {"inputs": ["UV", "U0", "V0", "US", "VS", "FlipU", "GlobalFlipU", "GlobalFlipV"], "output": 2,
                "code": ATLAS_UV_CODE},
    "TintAlpha": {"inputs": ["M", "Strength", "Lo", "Hi"], "output": 1, "code": TINT_ALPHA_CODE},
}
TAG, LABEL_PREFIX, FOLDER = "HP_S03T", "HP_S03T ", "HandPrints/S03_GreaseTint"
GREASE_TAG, GREASE_PREFIX = "HP_S03G", "HP_S03G "
SORT_OFFSET = 2                                       # grease uses 0/1
POS_TOL_CM, AXIS_DOT_MIN = 0.05, 0.99999
STAGE = globals().get("HP_TINT_STAGE")
DRY = bool(globals().get("HP_DRY_RUN"))
CONFIRM = globals().get("HP_TINT_CONFIRM")


class StageError(RuntimeError):
    pass


def require(cond, msg):
    if not cond:
        raise StageError(msg)


# ------------------------------------------------------------------------------------------------ pure helpers
def tint_alpha(m, strength, lo, hi):
    """Python twin of TINT_ALPHA_CODE (the harness tests this; the HLSL string is pinned to it)."""
    t = min(1.0, max(0.0, (m - lo) / max(hi - lo, 1e-4)))
    return min(1.0, max(0.0, strength)) * t * t * (3.0 - 2.0 * t)


def tint_name(grease_mi_name):
    require(grease_mi_name.startswith(GREASE_MI_PREFIX), "GREASE_MI_PREFIX|" + grease_mi_name)
    return TINT_MI_PREFIX + grease_mi_name[len(GREASE_MI_PREFIX):]


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hp_digest(rows):
    """IDENTICAL to hp_place_grease.py / s3_marble_tiling_apply.py hp_digest."""
    keyed = sorted("%s|%s|%s|%s|%s" % (h["object_path"], h["parent_label"],
                                       ",".join("%.2f" % v for v in h["location"]),
                                       ",".join("%.3f" % v for v in h["rotation"]),
                                       ",".join("%.4f" % v for v in h["scale"])) for h in rows)
    return hashlib.sha256("\n".join(keyed).encode("utf-8")).hexdigest()


def check_confirm(stage, confirm):
    if stage == "place" and not DRY:
        require(confirm == "APPLY HPS03T", "CONFIRM_MISSING|APPLY HPS03T")
    if stage == "revert" and not DRY:
        require(confirm == "REVERT HPS03T", "CONFIRM_MISSING|REVERT HPS03T")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, rec, exclusive=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if exclusive:
        with open(path, "x", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def read_record():
    if not os.path.isfile(RECORD):
        return {"worklist_sha256": WORKLIST_SHA256, "stages": {}}
    rec = load_json(RECORD)
    require(rec.get("worklist_sha256") == WORKLIST_SHA256, "RECORD_FOR_OTHER_WORKLIST")
    return rec


def write_record(rec):
    write_json(RECORD, rec)


def content_file(asset_path, ext):
    require(asset_path.startswith("/Game/"), "NOT_GAME_PATH|" + asset_path)
    return os.path.join(PROJECT_DIR, "Content", *asset_path[len("/Game/"):].split("/")) + ext


def backup_files(prefix, run, files):
    """Copy files (absolute, under PROJECT_DIR) to Backups/<prefix><run>/<same relative path>, hash-checked."""
    root = os.path.join(PROJECT_DIR, "Backups", prefix + run)
    require(not os.path.exists(root), "BACKUP_EXISTS|" + root)
    os.makedirs(root)
    for src in files:
        require(os.path.isfile(src), "BACKUP_SOURCE_MISSING|" + src)
        rel = os.path.relpath(src, PROJECT_DIR)
        dest = os.path.join(root, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        require(sha256(src) == sha256(dest), "BACKUP_HASH_MISMATCH|" + rel)
    return root


# ------------------------------------------------------------------------------------------------ unreal glue
def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def rpy(r):
    return [float(r.roll), float(r.pitch), float(r.yaw)]


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def path_of(obj):
    return None if obj is None else str(obj.get_path_name()).split(".", 1)[0]


def census():
    def names(pkgs):
        return sorted(str(p.get_path_name()).split(".", 1)[0] for p in pkgs)
    return {"maps": names(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def editor_world():
    return unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()


def preflight(clean=True):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    require(world is not None and str(world.get_outermost().get_name()) == EXPECTED_WORLD, "WRONG_WORLD")
    require(editor.get_game_world() is None, "PIE_OR_SIE_ACTIVE")
    if clean:
        before = census()
        require(not before["maps"] and not before["content"], "DIRTY_AT_START|" + json.dumps(before))
    return world


def end_clean():
    after = census()
    require(after == {"maps": [], "content": []}, "DIRTY_AFTER|" + json.dumps(after))


def exists(path):
    return bool(unreal.EditorAssetLibrary.does_asset_exist(path))


def save_asset(path):
    require(unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False), "SAVE_FAILED|" + path)


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


def grease_prereqs():
    require(os.path.isfile(GREASE_ASSETS_RECORD), "GREASE_ASSETS_RECORD_MISSING")
    st = load_json(GREASE_ASSETS_RECORD)["stages"]
    require((st.get("master") or {}).get("verified") is True, "GREASE_MASTER_NOT_VERIFIED")
    require((st.get("mi") or {}).get("verified") is True, "GREASE_MIS_NOT_VERIFIED")


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


# ------------------------------------------------------------------------------------------------ master
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
                         default_value=float(value), group="HPGreaseTint")


def build_master(grease_tex):
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(MASTER_NAME, TINT_DIR, unreal.Material,
                                                                  unreal.MaterialFactoryNew())
    require(mat is not None, "MASTER_CREATE")
    mat.modify()
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)          # blend BEFORE domain
    mat.modify()
    mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_DEFERRED_DECAL)
    require(mat.get_editor_property("material_domain") == unreal.MaterialDomain.MD_DEFERRED_DECAL, "DOMAIN")
    require(mat.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_TRANSLUCENT, "BLEND")
    g = Graph(mat)
    uv = g.node(unreal.MaterialExpressionTextureCoordinate, -1800, 0, coordinate_index=0)
    defaults = dict(zip(ATLAS_PARAMS, (0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0)), **TINT_SCALARS)
    p = {n: g.scalar(n, defaults[n], -1800, 120 + 90 * i) for i, n in enumerate(MASTER_SCALARS)}
    auv = g.custom(-1400, 200, "AtlasUV")
    g.link(uv, "", auv, "UV")
    for pin, name in (("U0", "AtlasU0"), ("V0", "AtlasV0"), ("US", "AtlasUSize"), ("VS", "AtlasVSize"),
                      ("FlipU", "FlipU"), ("GlobalFlipU", "GlobalFlipU"), ("GlobalFlipV", "GlobalFlipV")):
        g.link(p[name], "", auv, pin)
    mask = g.node(unreal.MaterialExpressionTextureSampleParameter2D, -1000, 0, parameter_name="GreaseMask",
                  texture=grease_tex, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS, group="HPGreaseTint")
    g.link(auv, "", mask, "UVs")
    ta = g.custom(-600, 0, "TintAlpha")
    g.link(mask, "RGB", ta, "M")
    g.link(p["TintStrength"], "", ta, "Strength")
    g.link(p["TintLo"], "", ta, "Lo")
    g.link(p["TintHi"], "", ta, "Hi")
    col = g.node(unreal.MaterialExpressionVectorParameter, -600, 300, parameter_name="TintColor",
                 default_value=unreal.LinearColor(*TINT_COLOR), group="HPGreaseTint")
    MP = unreal.MaterialProperty
    g.prop(ta, "", MP.MP_OPACITY)
    g.prop(col, "", MP.MP_BASE_COLOR)       # deliberately NO roughness / normal: the grease decal owns those
    unreal.MaterialEditingLibrary.layout_material_expressions(mat)
    errs = [str(e) for e in (unreal.MaterialEditingLibrary.recompile_material(mat) or [])]
    require(not errs, "MASTER_COMPILE|" + json.dumps(errs[:6]))
    return mat


def stage_master(run):
    preflight()
    grease_prereqs()
    rec = read_record()
    require("master" not in rec["stages"], "MASTER_STAGE_ALREADY_RECORDED")
    require(not exists(MASTER), "MASTER_EXISTS|" + MASTER)
    require(exists(GREASE_TEX), "GREASE_TEXTURE_MISSING")
    grease_files = sorted(content_file(GREASE_DIR + "/" + f[:-len(".uasset")], ".uasset")
                          for f in os.listdir(os.path.dirname(content_file(GREASE_MASTER, ".uasset")))
                          if f.endswith(".uasset"))
    require(len(grease_files) >= 143, "GREASE_FOLDER_COUNT|%d" % len(grease_files))
    if DRY:
        end_clean()
        unreal.log("HP_TINT_MASTER_DRY_RUN_OK|run=%s|grease_files=%d|mutated=0" % (run, len(grease_files)))
        return
    backup = backup_files("PreHPS03Tint-", run, grease_files + [content_file(GREASE_TEX, ".uasset")])
    marker = "HP_TINT_MASTER_START|run=%s" % run
    unreal.log(marker)
    rec["stages"]["master"] = {"run": run, "start_marker": marker, "built_utc": utc(), "saved": False,
                               "verified": False, "asset": MASTER, "verify_attempts": 0, "backup": backup}
    write_record(rec)
    grease_tex = unreal.load_asset(GREASE_TEX)
    require(grease_tex is not None, "MASTER_TEXTURE")
    mat = build_master(grease_tex)
    mat = grease_tex = None
    save_asset(MASTER)
    end_clean()
    rec["stages"]["master"]["saved"] = True
    write_record(rec)
    unreal.SystemLibrary.collect_garbage()
    unreal.log("HP_TINT_MASTER_BUILT|run=%s|recompile_errors=0|NOT_YET_VERIFIED: send master_verify after ~30 s" % run)


def stage_master_verify(run):
    preflight(clean=False)
    rec = read_record()
    st = rec["stages"].get("master") or {}
    require(st.get("saved") is True, "MASTER_NOT_BUILT")
    require(st.get("verified") is not True, "MASTER_ALREADY_VERIFIED")
    require(st.get("failed") is not True, "MASTER_ALREADY_FAILED|" + str(st.get("failure")))
    require(st.get("run") != run, "SAME_CALL_AS_BUILD")
    if DRY:
        unreal.log("HP_TINT_MASTER_VERIFY_DRY_RUN_OK|run=%s|mutated=0" % run)
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
    require(scalars == sorted(MASTER_SCALARS), "MASTER_SCALARS|%s" % scalars)
    require(sorted(str(n) for n in mel.get_vector_parameter_names(m)) == ["TintColor"], "MASTER_VECTORS")
    require(sorted(str(n) for n in mel.get_texture_parameter_names(m)) == ["GreaseMask"], "MASTER_TEXTURES")
    for k, v in TINT_SCALARS.items():
        got = float(mel.get_material_default_scalar_parameter_value(m, k))
        require(abs(got - v) < 1e-6, "DEFAULT|%s|%s" % (k, got))
    c = mel.get_material_default_vector_parameter_value(m, "TintColor")
    got = [float(c.r), float(c.g), float(c.b)]
    require(max(abs(a - b) for a, b in zip(got, TINT_COLOR)) < 1e-6, "DEFAULT|TintColor|%s" % got)
    MP = unreal.MaterialProperty
    for prop in (MP.MP_BASE_COLOR, MP.MP_OPACITY):
        require(mel.get_material_property_input_node(m, prop) is not None, "NOT_CONNECTED|%s" % prop)
    for prop in (MP.MP_ROUGHNESS, MP.MP_NORMAL, MP.MP_METALLIC, MP.MP_SPECULAR, MP.MP_EMISSIVE_COLOR):
        require(mel.get_material_property_input_node(m, prop) is None, "UNEXPECTED_CONNECTION|%s" % prop)
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
        unreal.log_warning("HP_TINT_MASTER_PENDING|run=%s|age=%.0fs|ps=0|retry master_verify" % (run, age))
        return
    st.update({"verified": True, "verified_ps": ps, "verify_run": run})
    write_record(rec)
    unreal.log("HP_TINT_MASTER_SUCCESS|run=%s|ps_instructions=%d|outputs=base_color+opacity|log_failures=0"
               % (run, ps))


# ------------------------------------------------------------------------------------------------ instances
def load_worklist():
    require(os.path.isfile(WORKLIST) and sha256(WORKLIST) == WORKLIST_SHA256, "WORKLIST_SHA256_MISMATCH")
    work = load_json(WORKLIST)
    items = []
    for i in work["instances"]:
        n = tint_name(i["name"])
        items.append({"name": n, "path": TINT_DIR + "/" + n, "grease": i["name"], "batch": i["batch"],
                      "scalars": {k: float(i["scalars"][k]) for k in MI_SCALARS}})
    require(len({i["name"] for i in items}) == len(items), "WORKLIST_DUPLICATE_NAMES")
    require(all(len([j for j in items if j["batch"] == i["batch"]]) <= MI_BATCH_MAX for i in items), "BATCH_TOO_BIG")
    return items


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
    items = load_worklist()
    st = rec["stages"].setdefault("mi", {"done": [], "in_progress": [], "batches": [], "verified": False})
    b = next_batch(items, st)
    if b is None:
        unreal.log("HP_TINT_MI_BATCH_NOTHING_TO_DO|run=%s|done=%d" % (run, len(st["done"])))
        return
    batch = [i for i in items if i["batch"] == b and i["name"] not in set(st["done"])]
    for i in batch:
        require(not exists(i["path"]) or i["name"] in set(st.get("in_progress") or []),
                "MI_EXISTS_UNRECORDED|" + i["name"])
    ram = free_ram_gb()
    require(ram >= MIN_FREE_RAM_GB, "FREE_RAM_LOW|%.1f" % ram)
    if DRY:
        end_clean()
        unreal.log("HP_TINT_MI_BATCH_DRY_RUN_OK|run=%s|batch=%d|size=%d|done=%d|total=%d|free_ram_gb=%.1f|mutated=0"
                   % (run, b, len(batch), len(st["done"]), len(items), ram))
        return
    st["in_progress"] = sorted(set(st.get("in_progress") or []) | {i["name"] for i in batch})
    write_record(rec)                                            # BEFORE the first create
    master = unreal.load_asset(MASTER)
    require(master is not None, "MASTER_MISSING")
    mel = unreal.MaterialEditingLibrary
    for i in batch:
        if exists(i["path"]):
            mi = unreal.load_asset(i["path"])                         # resume: re-set and re-save
        else:
            mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                i["name"], TINT_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        require(mi is not None, "MI_CREATE_FAILED|" + i["name"])
        mel.set_material_instance_parent(mi, master)
        for k in MI_SCALARS:
            mel.set_material_instance_scalar_parameter_value(mi, k, i["scalars"][k])
        mel.update_material_instance(mi)
        save_asset(i["path"])
        mi = None
    master = None
    end_clean()
    st["done"] = sorted(set(st["done"]) | {i["name"] for i in batch})
    st["in_progress"] = []
    st["batches"].append({"run": run, "batch": b, "names": [i["name"] for i in batch], "free_ram_gb": round(ram, 2)})
    write_record(rec)
    unreal.SystemLibrary.collect_garbage()
    unreal.log("HP_TINT_MI_BATCH_DONE|run=%s|batch=%d|created=%d|done=%d|remaining=%d|NOT_YET_VERIFIED"
               % (run, b, len(batch), len(st["done"]), len(items) - len(st["done"])))


def stage_mi_verify(run):
    preflight(clean=False)
    rec = read_record()
    st = rec["stages"].get("mi") or {}
    items = load_worklist()
    require(set(st.get("done") or []) == {i["name"] for i in items} and not st.get("in_progress"), "MI_NOT_ALL_CREATED")
    require(all(b["run"] != run for b in st.get("batches") or []), "SAME_CALL_AS_BATCH")
    if DRY:
        unreal.log("HP_TINT_MI_VERIFY_DRY_RUN_OK|run=%s|n=%d|mutated=0" % (run, len(items)))
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
            if abs(got - i["scalars"][k]) > 1e-6:
                bad.append("SCALAR|%s|%s|%s" % (i["name"], k, got))
        for k, v in TINT_SCALARS.items():
            got = float(mel.get_material_instance_scalar_parameter_value(mi, k))
            if abs(got - v) > 1e-6:
                bad.append("DEFAULT|%s|%s|%s" % (i["name"], k, got))
        c = mel.get_material_instance_vector_parameter_value(mi, "TintColor")
        if max(abs(a - b) for a, b in zip((float(c.r), float(c.g), float(c.b)), TINT_COLOR)) > 1e-6:
            bad.append("DEFAULT|%s|TintColor" % i["name"])
        mi = None
    if bad:
        st["verify_failures"] = bad[:20]
        write_record(rec)
        raise StageError("MI_VERIFY|%d|%s" % (len(bad), json.dumps(bad[:5])))
    end_clean()
    st.update({"verified": True, "verify_run": run, "verified_count": len(items)})
    write_record(rec)
    unreal.SystemLibrary.collect_garbage()
    unreal.log("HP_TINT_MI_SUCCESS|run=%s|verified=%d" % (run, len(items)))


# ------------------------------------------------------------------------------------------------ level
def all_actors(world):
    return list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))


def tagged(world, tag):
    return [a for a in all_actors(world) if tag in [str(t) for t in a.get_editor_property("tags")]]


def temp_actors(world):
    return [str(a.get_actor_label()) for a in all_actors(world)
            if str(a.get_actor_label()).startswith("ZZ_") or "TEMP" in str(a.get_actor_label()).upper()]


def digest_row(a):
    p = a.get_attach_parent_actor()
    return {"object_path": a.get_path_name(), "parent_label": str(p.get_actor_label()) if p else None,
            "location": vec(a.get_actor_location()), "rotation": rpy(a.get_actor_rotation()),
            "scale": vec(a.get_actor_scale3d())}


def twin_label(grease_label):
    require(grease_label.startswith(GREASE_PREFIX), "GREASE_LABEL|" + grease_label)
    return LABEL_PREFIX + grease_label[len(GREASE_PREFIX):]


def backup_level(prefix, run):
    return backup_files(prefix, run, [content_file(EXPECTED_WORLD, ".umap")])


def grease_layer(world):
    """The live grease decals, proven unchanged since hp_place_grease APPLY (count + digest)."""
    require(os.path.isfile(GREASE_PLACE_RECORD), "GREASE_PLACE_RECORD_MISSING")
    grec = load_json(GREASE_PLACE_RECORD)
    require(grec.get("saved") is True and grec.get("mode") == "APPLY", "GREASE_PLACE_NOT_SAVED")
    grease = sorted(tagged(world, GREASE_TAG), key=lambda a: str(a.get_actor_label()))
    require(len(grease) == grec["count_after_save"], "GREASE_COUNT|%d" % len(grease))
    for a in grease:
        require(isinstance(a, unreal.DecalActor) and str(a.get_actor_label()).startswith(GREASE_PREFIX),
                "GREASE_NOT_OWNED|" + str(a.get_actor_label()))
    digest = hp_digest([digest_row(a) for a in grease])
    require(digest == grec["grease_digest_after"], "GREASE_LAYER_CHANGED_SINCE_APPLY|" + digest)
    return grease, digest


def place_gates(world):
    preflight()
    require(not tagged(world, TAG), "HP_S03T_ALREADY_EXIST")
    require(not any(str(a.get_actor_label()).startswith(LABEL_PREFIX) for a in all_actors(world)), "HP_S03T_LABELS_EXIST")
    require(not os.path.exists(PLACE_RECORD), "PLACE_RECORD_EXISTS|" + PLACE_RECORD)
    rec = read_record()
    require((rec["stages"].get("master") or {}).get("verified") is True, "MASTER_NOT_VERIFIED")
    mi = rec["stages"].get("mi") or {}
    require(mi.get("verified") is True, "MIS_NOT_VERIFIED")
    grease, digest = grease_layer(world)
    plan, need = [], set()
    for a in grease:
        c = a.get_editor_property("decal")
        gmi = path_of(c.get_decal_material())
        require(gmi is not None and gmi.startswith(GREASE_DIR + "/"), "GREASE_MATERIAL|" + str(a.get_actor_label()))
        tmi = tint_name(gmi.rsplit("/", 1)[1])
        require(tmi in set(mi["done"]), "TINT_MI_NOT_VERIFIED|" + tmi)
        need.add(tmi)
        plan.append((a, TINT_DIR + "/" + tmi))
    for n in sorted(need):
        require(exists(TINT_DIR + "/" + n), "TINT_MI_MISSING|" + n)
    return grease, digest, plan


def spawn_twin(g, mi, run):
    c0 = g.get_editor_property("decal")
    actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.DecalActor, g.get_actor_location(), g.get_actor_rotation())
    require(actor is not None, "SPAWN_FAILED|" + str(g.get_actor_label()))
    actor.modify(); actor.set_actor_label(twin_label(str(g.get_actor_label())))
    actor.modify(); actor.set_folder_path(FOLDER)
    actor.modify(); actor.set_editor_property("tags", [unreal.Name(TAG), unreal.Name(TAG + ".run." + run)])
    actor.modify(); actor.set_actor_scale3d(g.get_actor_scale3d())
    c = actor.get_editor_property("decal")
    c.modify(); c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.modify(); c.set_decal_material(mi)
    c.modify(); c.set_editor_property("decal_size", c0.get_editor_property("decal_size"))
    c.modify(); c.set_sort_order(int(c0.get_editor_property("sort_order")) + SORT_OFFSET)
    c.modify(); c.set_fade_screen_size(float(c0.get_editor_property("fade_screen_size")))
    parent = g.get_attach_parent_actor()
    if parent is not None:
        actor.modify()
        actor.attach_to_actor(parent, unreal.Name(""), unreal.AttachmentRule.KEEP_WORLD,
                              unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD, False)
    return actor


def twin_diffs(t, g, mi_path):
    """Fields of twin t that do not match grease decal g (empty = exact)."""
    out = []
    ct, cg = t.get_editor_property("decal"), g.get_editor_property("decal")
    if str(t.get_actor_label()) != twin_label(str(g.get_actor_label())):
        out.append("label")
    if max(abs(a - b) for a, b in zip(vec(t.get_actor_location()), vec(g.get_actor_location()))) > POS_TOL_CM:
        out.append("location")
    for fn in ("get_actor_forward_vector", "get_actor_right_vector", "get_actor_up_vector"):
        if dot(vec(getattr(t, fn)()), vec(getattr(g, fn)())) < AXIS_DOT_MIN:
            out.append("axis:" + fn)
    if max(abs(a - b) for a, b in zip(vec(t.get_actor_scale3d()), vec(g.get_actor_scale3d()))) > 1e-4:
        out.append("scale")
    if max(abs(a - b) for a, b in zip(vec(ct.get_editor_property("decal_size")),
                                      vec(cg.get_editor_property("decal_size")))) > 1e-3:
        out.append("decal_size")
    if path_of(ct.get_decal_material()) != mi_path:
        out.append("material")
    if int(ct.get_editor_property("sort_order")) != int(cg.get_editor_property("sort_order")) + SORT_OFFSET:
        out.append("sort_order")
    if abs(float(ct.get_editor_property("fade_screen_size")) - float(cg.get_editor_property("fade_screen_size"))) > 1e-9:
        out.append("fade_screen_size")
    if t.get_attach_parent_actor() != g.get_attach_parent_actor():
        out.append("parent")
    if ct.get_editor_property("mobility") != unreal.ComponentMobility.MOVABLE:
        out.append("mobility")
    if str(t.get_folder_path()) != FOLDER or TAG not in [str(x) for x in t.get_editor_property("tags")]:
        out.append("folder_or_tag")
    return out


def save_level_gated(world, expect_twins):
    require(len(tagged(world, TAG)) == expect_twins, "COUNT_BEFORE_SAVE|%d" % len(tagged(world, TAG)))
    temps = temp_actors(world)
    require(not temps, "TEMP_ACTORS_PRESENT_REFUSING_SAVE|" + json.dumps(temps[:10]))
    pre = census()
    require(pre["content"] == [] and pre["maps"] == [EXPECTED_WORLD], "CENSUS_NOT_EXACT_LEVEL|" + json.dumps(pre))
    require(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(), "LEVEL_SAVE_FAILED")


def stage_place(run):
    world = editor_world()
    grease, digest, plan = place_gates(world)
    if DRY:
        end_clean()
        unreal.log("HP_TINT_PLACE_DRY_OK|run=%s|grease=%d|twins_planned=%d|mis=%d|mutated=0"
                   % (run, len(grease), len(plan), len({p[1] for p in plan})))
        return
    backup = backup_level("PreHPS03Tint-", run)
    rec = {"run": run, "mode": "APPLY", "world": EXPECTED_WORLD, "backup": backup, "grease_digest": digest,
           "count_planned": len(plan), "spawned": 0, "saved": False, "sort_offset": SORT_OFFSET}
    write_json(PLACE_RECORD, rec, exclusive=True)                    # BEFORE the first spawn
    mats = {p: unreal.load_asset(p) for p in sorted({p[1] for p in plan})}
    require(all(m is not None for m in mats.values()), "MI_LOAD")
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned, saved = [], [False]
    try:
        with unreal.ScopedEditorTransaction("HP_S03T grease tint twins run=" + run):
            for g, mi_path in plan:
                t = spawn_twin(g, mats[mi_path], run)
                spawned.append(t)
                d = twin_diffs(t, g, mi_path)
                require(not d, "TWIN_READBACK|%s|%s" % (str(g.get_actor_label()), d))
        rec["spawned"] = len(spawned)
        write_json(PLACE_RECORD, rec)
        save_level_gated(world, len(plan))
        saved[0] = True
        end_clean()
        twins = tagged(world, TAG)
        require(len(twins) == len(plan), "COUNT_AFTER_SAVE|%d" % len(twins))
        g2, digest2 = grease_layer(world)
        require(digest2 == digest, "GREASE_CHANGED_BY_PLACE")
        rec.update({"saved": True, "count_after_save": len(twins),
                    "tint_digest_after": hp_digest([digest_row(a) for a in twins])})
        write_json(PLACE_RECORD, rec)
        unreal.log("HP_TINT_PLACE_SUCCESS|run=%s|spawned=%d|grease_unchanged=1|saved=1|backup=%s"
                   % (run, len(twins), backup))
    except Exception:
        if not saved[0]:
            for a in spawned:
                try:
                    sub.destroy_actor(a)
                except Exception:
                    pass
            rec.update({"failed": True, "needs": "DONT_SAVE_RESTART if the map is still dirty"})
            write_json(PLACE_RECORD, rec)
            os.replace(PLACE_RECORD, PLACE_RECORD + ".failed-" + run)
        raise


def stage_place_verify(run):
    world = preflight(clean=False)
    require(os.path.isfile(PLACE_RECORD), "NO_PLACE_RECORD")
    rec = load_json(PLACE_RECORD)
    require(rec.get("saved") is True, "PLACE_NOT_SAVED")
    require(rec["run"] != run, "SAME_CALL_AS_PLACE")
    grease, _ = grease_layer(world)
    twins = {str(a.get_actor_label()): a for a in tagged(world, TAG)}
    require(len(twins) == rec["count_after_save"] == len(grease), "TWIN_COUNT|%d" % len(twins))
    bad = []
    for g in grease:
        t = twins.get(twin_label(str(g.get_actor_label())))
        if t is None:
            bad.append("MISSING|" + str(g.get_actor_label()))
            continue
        gmi = path_of(g.get_editor_property("decal").get_decal_material())
        d = twin_diffs(t, g, TINT_DIR + "/" + tint_name(gmi.rsplit("/", 1)[1]))
        if d:
            bad.append("%s|%s" % (str(t.get_actor_label()), d))
    require(not bad, "PLACE_VERIFY|%d|%s" % (len(bad), json.dumps(bad[:5])))
    digest = hp_digest([digest_row(a) for a in twins.values()])
    require(digest == rec["tint_digest_after"], "TINT_LAYER_CHANGED_SINCE_PLACE")
    unreal.log("HP_TINT_PLACE_VERIFY_SUCCESS|run=%s|paired=%d" % (run, len(twins)))


def stage_revert(run):
    world = preflight()
    require(os.path.isfile(PLACE_RECORD), "NO_PLACE_RECORD")
    rec = load_json(PLACE_RECORD)
    require(rec.get("saved") is True and rec.get("mode") == "APPLY", "PLACE_RECORD_NOT_SAVED_APPLY")
    twins = tagged(world, TAG)
    require(len(twins) == rec["count_after_save"], "TWIN_COUNT|%d" % len(twins))
    for a in twins:
        require(isinstance(a, unreal.DecalActor) and str(a.get_actor_label()).startswith(LABEL_PREFIX),
                "TWIN_NOT_OWNED|" + str(a.get_actor_label()))
    _, gdigest = grease_layer(world)
    if DRY:
        end_clean()
        unreal.log("HP_TINT_REVERT_DRY_OK|run=%s|twins=%d|mutated=0" % (run, len(twins)))
        return
    backup = backup_level("PreHPS03TintRevert-", run)
    rec.update({"revert_run": run, "revert_backup": backup, "revert_started": True})
    write_json(PLACE_RECORD, rec)
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    n = len(twins)
    with unreal.ScopedEditorTransaction("HP_S03T revert tint twins run=" + run):
        for a in twins:
            lab = str(a.get_actor_label())
            a.modify()
            require(sub.destroy_actor(a), "DESTROY_FAILED|" + lab)
    twins = None
    _, g2 = grease_layer(world)
    require(g2 == gdigest, "GREASE_CHANGED_BY_REVERT")
    save_level_gated(world, 0)
    end_clean()
    require(not tagged(world, TAG), "TWINS_AFTER_SAVE")
    rec.update({"reverted": True, "revert_saved": True, "removed": n})
    write_json(PLACE_RECORD, rec)
    archived = PLACE_RECORD + ".reverted-" + run
    os.replace(PLACE_RECORD, archived)
    unreal.log("HP_TINT_REVERT_SUCCESS|run=%s|removed=%d|grease_unchanged=1|saved=1|backup=%s" % (run, n, backup))


def main():
    run = globals().get("HP_TINT_RUN_ID") or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    stages = {"master": stage_master, "master_verify": stage_master_verify, "mi_batch": stage_mi_batch,
              "mi_verify": stage_mi_verify, "place": stage_place, "place_verify": stage_place_verify,
              "revert": stage_revert}
    try:
        require(STAGE in stages, "HP_TINT_STAGE_NOT_SET|%s" % STAGE)
        check_confirm(STAGE, CONFIRM)
        stages[STAGE](run)
    except StageError as exc:
        unreal.log_error("HP_TINT_%s_STOPPED|run=%s|reason=%s|census=%s|NEEDS_DONT_SAVE_RESTART_IF_MAP_DIRTY"
                         % (str(STAGE).upper(), run, exc, json.dumps(census())))
    except Exception:
        unreal.log_error("HP_TINT_%s_ERROR|run=%s|traceback=%s|census=%s|NEEDS_DONT_SAVE_RESTART_IF_MAP_DIRTY"
                         % (str(STAGE).upper(), run, traceback.format_exc().replace("\n", "\\n"),
                            json.dumps(census())))


main()
