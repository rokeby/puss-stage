"""CURTAIN IMAGE (6 Oct, offline-written, NEVER RUN IN UNREAL): put Gary's picture on a back-passage curtain.

Gary 6 Oct ~00:30 (Docs/Conductor/GARY_PIE_NOTES_2026-10-05.md:267): "Back-passage curtains across P01-P05 (not P06),
easy to put images on".

Tiers: [decl] read in a file/header (cited), [prec] an in-repo precedent call (cited, whether it ran), [inf] inferred.

WHY A NEW MATERIAL (and no edit to an existing one)
  * Every curtain cache today renders MI_CurtainVelvet_DeepRed_Drop or Soft goods' backcloth MI, children of
    M_CurtainVelvet, which has no texture parameter for a picture [decl curtain_baked_import.py:172-178,
    import_passing_bake.py:247-265: only PatternWidthM/DropM/SeamWidthM scalars and the velvet vectors are set].
    The Drop MI is SHARED by the Opening, Interactions 1-5 and Rig's portal border [decl ChaosClothCurtain.md:5-12,
    :208-209], so a picture cannot go on it. Node edits on existing masters are banned here (memory
    ue58-python-material-authoring: deleting rooted nodes crashed the editor).
  * So: ONE new master M_CurtainImage (create-only) and ONE new instance per back curtain, MI_CurtainImage_P0n
    (create-only), put on that curtain ACTOR as a component material override (the shared cache asset is not touched).
    UGeometryCacheComponent is a UMeshComponent [decl UE_5.8 GeometryCacheComponent.h:36] and overrides GetMaterial
    [decl :74]; that the override wins over the cache's own material is [inf] (engine .cpp not on disk): ASSIGN reads
    get_material back and Gary's still is the proof.

THE MATERIAL (Default Lit, two-sided, used_with_geometry_cache; graph style of
  Saved/CodexFlatV3/edge/build_canvas_edge_master_v2.py [prec, ran 5 Oct])
  BaseColor = lerp(VelvetColor, Image.rgb x ImageTint, ImageAmount x mask x Image.a); Emissive = the same picture x
  ImageEmissive (0 by default: lit by the stage); Roughness, Specular params.
  Two mappings, chosen per instance by PlanarMapping (0/1):
    1 (default) PLANAR in the actor's local Y/Z (the hanging plane): u = (y - PlanarY0Cm) / PlanarWidthCm,
      v = (PlanarTopZCm - z) / PlanarHeightCm. The picture reads flat across the pleats while hanging. During the fall
      the cloth moves THROUGH the projection (the picture slides over it) [inf]; PlanarMinZCm hides it below a height
      (e.g. 120 = a plain velvet pile). Negative PlanarWidthCm mirrors (the cache's Y sign is unrecorded,
      passage_end_drape.py:744).
    0 UV: u = (UV0.x - RectU0) / RectUW, v = (UV0.y - RectV0) / RectVH on the flat fabric (UV0 spans the pattern,
      [decl velvet_v2_build.py "UV0 x (PatternWidthM, DropM) = flat-fabric metres"]). The picture rides the cloth
      through the fall, but the pleats (fullness ~2x) concertina it [inf].
  Outside the [0,1] rectangle: plain velvet.

Modes (curtain_image_run.py <- curtain_image_args.json):
  BUILD    create-only M_CurtainImage + MI_CurtainImage_P01..P05 (per-curtain planar defaults); saves those 6 only
  SET      {"passage": n, "png": "<path>"} or {"passage": n, "texture": "/Game/..."}: imports the PNG create-only as
           T_CurtainImage_P0n_<stem>_<stamp>, sets the MI's Image (+ ImageAmount, and any "mi_scalars" given),
           saves the texture + that MI only. No level write. Logged to curtain_image_log.json with the previous
           texture, so "SET texture=<previous>" is the undo.
  ASSIGN   {"passage": n}: the curtain actor's component overrides -> MI_CurtainImage_P0n. Level write: umap backup,
           exclusive record (previous overrides), read-back, census == {level}, save the level only.
  UNASSIGN {"passage": n}: restores the recorded overrides, saves the level only.
  VERIFY   read-only: master flags/params, every MI's parent and Image, every assigned curtain's material.
Confirm: "<MODE> P0n" (BUILD/VERIFY: "<MODE> ALL"). Markers CURTAIN_IMAGE_<MODE>_OK|run=.. / CURTAIN_IMAGE_STOPPED|run=..
Never Save All, never end PIE, never reload the level, no unreal objects in module globals, no expression deletion.
Compile is async: grep Saved/Logs/PussStage.log for M_CurtainImage ~20 s after BUILD ("Failed to compile" must be absent).
"""
import datetime
import json
import os
import re
import shutil
import struct

try:
    import unreal
except ModuleNotFoundError:  # Offline harness.
    unreal = None


MARK = "CURTAIN_IMAGE"
EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
FOLDER = "/Game/InfinityStage/Curtains/Image"
MASTER = FOLDER + "/M_CurtainImage"
MI_PATTERN = FOLDER + "/MI_CurtainImage_P%02d"
TEX_FOLDER = FOLDER + "/Textures"
DEFAULT_TEX = "/Engine/EngineResources/WhiteSquareTexture"
PASSAGES = (1, 2, 3, 4, 5)                      # Gary: P01-P05, P06 excluded
ARGS_NAME = "curtain_image_args.json"
LOG_NAME = "curtain_image_log.json"
RECORD_PATTERN = "curtain_image_assign_record_P%02d.json"
# The back curtain of each Passage, by label, in preference order (exactly one must exist).
CURTAIN_LABELS = {
    1: ["P01 End Drape (stand-in)"], 2: ["P02 End Drape (stand-in)"], 3: ["P03 End Drape (stand-in)"],
    4: ["P04 Backcloth (baked)", "P04 End Drape (stand-in)"],   # p04_backcloth_section_record.json; passage_end_drape
    5: ["P05 End Drape (stand-in)"],
}
# Hang extents (actor-local cm) per cache, for the planar defaults. final13 hang y +-940, z 20..1020
# [meas curtain_sleight_I1_dry.json inputs.cache via test_passage_end_drape.py:8]; final11 hold sample y +-500 m,
# z 20..1220 [meas DropBake/final11_backcloth_p04_a06.json checkpoint 479: x +-5.0 m, z 0.2..12.2 m].
HANG = {"final13": {"y": 940.0, "z0": 20.0, "z1": 1020.0}, "final11": {"y": 500.0, "z0": 20.0, "z1": 1220.0}}
CACHE_OF = {1: "final13", 2: "final13", 3: "final13", 4: "final11", 5: "final13"}

SCALARS = {   # name: (default, group)
    "ImageAmount": (0.0, "01 Image"), "ImageEmissive": (0.0, "01 Image"),
    "PlanarMapping": (1.0, "02 Mapping"),
    "PlanarY0Cm": (-940.0, "02 Mapping"), "PlanarWidthCm": (1880.0, "02 Mapping"),
    "PlanarTopZCm": (1020.0, "02 Mapping"), "PlanarHeightCm": (1000.0, "02 Mapping"),
    "PlanarMinZCm": (-100000.0, "02 Mapping"),
    "RectU0": (0.0, "03 UV"), "RectUW": (1.0, "03 UV"), "RectV0": (0.0, "03 UV"), "RectVH": (1.0, "03 UV"),
    "Roughness": (0.85, "04 Surface"), "Specular": (0.3, "04 Surface"),
}
VECTORS = {"VelvetColor": ((0.07, 0.004, 0.012), "04 Surface"),     # plain oxblood B (ChaosClothCurtain.md "Velvet")
           "ImageTint": ((1.0, 1.0, 1.0), "01 Image")}
TEXTURES = {"Image": (DEFAULT_TEX, "01 Image")}

CODE_UV = """// Picture coordinates: planar in the actor's hanging plane (Planar=1) or the fabric's UV0 (Planar=0).
float2 a = float2((UV.x - U0) / (abs(UW) > 1e-4 ? UW : 1e-4), (UV.y - V0) / (abs(VH) > 1e-4 ? VH : 1e-4));
float2 b = float2((LP.y - PY0) / (abs(PW) > 1e-3 ? PW : 1e-3), (PTop - LP.z) / (abs(PH) > 1e-3 ? PH : 1e-3));
return lerp(a, b, saturate(Planar));
"""
CODE_MASK = """// 1 inside the picture rectangle (and, planar, above PMinZ), else 0.
float inside = step(0.0, P.x) * step(P.x, 1.0) * step(0.0, P.y) * step(P.y, 1.0);
float above = lerp(1.0, step(PMinZ, LP.z), saturate(Planar));
return inside * above;
"""
CODE_BASE = """// Velvet where there is no picture; the tinted picture where there is.
return lerp(Velvet, Img * Tint, saturate(Amount * Mask * ImgA));
"""
CODE_EMIS = """// Optional self-light for the picture only (0 = lit by the stage).
return Img * Tint * Emis * saturate(Amount * Mask * ImgA);
"""
CUSTOM = {   # key: (code, inputs, output)
    "CI_UV": (CODE_UV, ["UV", "LP", "Planar", "U0", "UW", "V0", "VH", "PY0", "PW", "PTop", "PH"], "F2"),
    "CI_Mask": (CODE_MASK, ["P", "LP", "PMinZ", "Planar"], "F1"),
    "CI_Base": (CODE_BASE, ["Velvet", "Img", "ImgA", "Tint", "Amount", "Mask"], "F3"),
    "CI_Emis": (CODE_EMIS, ["Img", "ImgA", "Tint", "Amount", "Mask", "Emis"], "F3"),
}
# (source key, source output, target key, target pin). Custom inputs are wired by name.
EDGES = [
    ("WPos", "", "LPos", ""),
    ("UV0", "", "CI_UV", "UV"), ("LPos", "", "CI_UV", "LP"), ("PlanarMapping", "", "CI_UV", "Planar"),
    ("RectU0", "", "CI_UV", "U0"), ("RectUW", "", "CI_UV", "UW"), ("RectV0", "", "CI_UV", "V0"), ("RectVH", "", "CI_UV", "VH"),
    ("PlanarY0Cm", "", "CI_UV", "PY0"), ("PlanarWidthCm", "", "CI_UV", "PW"), ("PlanarTopZCm", "", "CI_UV", "PTop"),
    ("PlanarHeightCm", "", "CI_UV", "PH"),
    ("CI_UV", "", "Image", "UVs"),
    ("CI_UV", "", "CI_Mask", "P"), ("LPos", "", "CI_Mask", "LP"), ("PlanarMinZCm", "", "CI_Mask", "PMinZ"),
    ("PlanarMapping", "", "CI_Mask", "Planar"),
    ("VelvetColor", "", "CI_Base", "Velvet"), ("Image", "RGB", "CI_Base", "Img"), ("Image", "A", "CI_Base", "ImgA"),
    ("ImageTint", "", "CI_Base", "Tint"), ("ImageAmount", "", "CI_Base", "Amount"), ("CI_Mask", "", "CI_Base", "Mask"),
    ("Image", "RGB", "CI_Emis", "Img"), ("Image", "A", "CI_Emis", "ImgA"), ("ImageTint", "", "CI_Emis", "Tint"),
    ("ImageAmount", "", "CI_Emis", "Amount"), ("CI_Mask", "", "CI_Emis", "Mask"), ("ImageEmissive", "", "CI_Emis", "Emis"),
]
PROPS = [("CI_Base", "MP_BASE_COLOR"), ("CI_Emis", "MP_EMISSIVE_COLOR"), ("Roughness", "MP_ROUGHNESS"),
         ("Specular", "MP_SPECULAR")]
# 3 plain nodes (UV0, WPos, LPos) + 4 custom + 14 scalar + 2 vector + 1 texture parameter
EXPECTED_EXPRESSIONS = 3 + len(CUSTOM) + len(SCALARS) + len(VECTORS) + len(TEXTURES)


class PlanError(ValueError):
    pass


# =====================================================================================================================
# Pure helpers (offline harness: test_curtain_image.py)
# =====================================================================================================================

def mi_defaults(n):
    """Per-curtain planar defaults: the picture fills the hanging cloth's front."""
    if n not in PASSAGES:
        raise PlanError("OUT_OF_SCOPE: P%02d (Gary: P01-P05, P06 excluded)" % n)
    h = HANG[CACHE_OF[n]]
    return {"PlanarY0Cm": -h["y"], "PlanarWidthCm": 2.0 * h["y"], "PlanarTopZCm": h["z1"],
            "PlanarHeightCm": h["z1"] - h["z0"]}


def png_size(path):
    """(width, height) from the PNG IHDR, or raise. Reads 24 bytes; no imaging library."""
    with open(path, "rb") as handle:
        head = handle.read(24)
    if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise PlanError("NOT_A_PNG: %s" % path)
    return struct.unpack(">II", head[16:24])


def texture_name(n, png, stamp):
    stem = re.sub(r"[^A-Za-z0-9]+", "_", os.path.splitext(os.path.basename(png))[0]).strip("_")[:40] or "image"
    return "T_CurtainImage_P%02d_%s_%s" % (n, stem, stamp)


def png_warnings(size, n, mi_scalars=None):
    w, h = size
    out = []
    if w & (w - 1) or h & (h - 1):
        out.append("NOT_POWER_OF_TWO: %dx%d (UE builds no mips for it: shimmer at distance; 4096x2048 or 2048x2048 "
                   "are safe)" % (w, h))
    if max(w, h) > 8192:
        out.append("LARGER_THAN_8192: %dx%d" % (w, h))
    d = dict(mi_defaults(n))
    d.update({k: v for k, v in (mi_scalars or {}).items() if k in d})
    want = abs(d["PlanarWidthCm"]) / abs(d["PlanarHeightCm"])
    got = w / float(h)
    if abs(got / want - 1.0) > 0.1:
        out.append("ASPECT: picture %.2f:1 vs the curtain front %.2f:1, it will be stretched (or set the Planar*Cm "
                   "rectangle)" % (got, want))
    return out


def validate_args(args):
    mode = str(args.get("mode") or "").upper()
    if mode not in ("BUILD", "SET", "ASSIGN", "UNASSIGN", "VERIFY"):
        raise PlanError("MODE_INVALID: %r" % mode)
    if mode in ("BUILD", "VERIFY"):
        want = "%s ALL" % mode
        n = None
    else:
        n = args.get("passage")
        if n not in PASSAGES:
            raise PlanError("PASSAGE_OUT_OF_SCOPE: %r (P01-P05)" % (n,))
        want = "%s P%02d" % (mode, n)
    if args.get("confirm") != want:
        raise PlanError("CONFIRM_MISMATCH: %r, want %r" % (args.get("confirm"), want))
    if mode == "SET":
        if bool(args.get("png")) == bool(args.get("texture")):
            raise PlanError("SET_NEEDS_ONE_OF: png | texture")
        bad = sorted(set(args.get("mi_scalars") or {}) - set(SCALARS))
        if bad:
            raise PlanError("UNKNOWN_MI_SCALARS: %r" % bad)
        if args.get("texture") and not str(args["texture"]).startswith("/Game/"):
            raise PlanError("TEXTURE_NOT_GAME_PATH: %r" % args["texture"])
    if mode in ("ASSIGN", "UNASSIGN") and not str(args.get("decided_by") or "").strip():
        raise PlanError("NOT_DECIDED: decided_by is empty (a level write)")
    return mode, n


def set_values(args):
    """What SET writes on the MI besides the texture: ImageAmount 1 unless given, plus any mi_scalars."""
    out = {"ImageAmount": 1.0}
    out.update({k: float(v) for k, v in (args.get("mi_scalars") or {}).items()})
    return out


# =====================================================================================================================
# Unreal side
# =====================================================================================================================

def _here():
    if unreal is not None:
        return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    return os.path.dirname(os.path.abspath(__file__))


def _stop(run, reason):
    unreal.log_error("%s_STOPPED|run=%s|reason=%s" % (MARK, run, reason))
    raise RuntimeError(reason)


def _pk(path_name):
    return str(path_name).split(".")[0]


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(_pk(p.get_path_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(_pk(p.get_path_name()) for p in lib.get_dirty_map_packages())}


def _content_file(path, ext=".uasset"):
    project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    return os.path.join(project, "Content", *path[len("/Game/"):].split("/")) + ext


def _mel():
    return unreal.MaterialEditingLibrary


def _build(run):
    eal, mel = unreal.EditorAssetLibrary, _mel()
    targets = [MASTER] + [MI_PATTERN % n for n in PASSAGES]
    taken = [p for p in targets if eal.does_asset_exist(p)]
    if taken:
        _stop(run, "TARGETS_EXIST (create-only; never edits an existing material)|%s" % taken)
    if unreal.load_asset(DEFAULT_TEX) is None:
        _stop(run, "DEFAULT_TEXTURE_MISSING|" + DEFAULT_TEX)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    folder, name = MASTER.rsplit("/", 1)
    mat = tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
    if mat is None or int(mel.get_num_material_expressions(mat)) != 0:
        _stop(run, "CREATE_MASTER")
    for key, value in (("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT), ("two_sided", True),
                       ("blend_mode", unreal.BlendMode.BLEND_OPAQUE), ("used_with_geometry_cache", True)):
        mat.set_editor_property(key, value)
    nodes = {}

    def node(key, cls, x, y, **props):
        n = mel.create_material_expression(mat, cls, x, y)
        if n is None:
            _stop(run, "CREATE_EXPRESSION|" + key)
        for k, v in props.items():
            n.set_editor_property(k, v)
        nodes[key] = n
        return n

    out_types = {"F1": unreal.CustomMaterialOutputType.CMOT_FLOAT1, "F2": unreal.CustomMaterialOutputType.CMOT_FLOAT2,
                 "F3": unreal.CustomMaterialOutputType.CMOT_FLOAT3}
    node("UV0", unreal.MaterialExpressionTextureCoordinate, -1800, -200, coordinate_index=0)
    node("WPos", unreal.MaterialExpressionWorldPosition, -1800, 0,
         world_position_shader_offset=unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    node("LPos", unreal.MaterialExpressionTransformPosition, -1600, 0,       # build_canvas_edge_master_v2.py:148-150
         transform_source_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
         transform_type=unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    for i, (pname, (value, group)) in enumerate(SCALARS.items()):
        node(pname, unreal.MaterialExpressionScalarParameter, -1400, 200 + 70 * i, parameter_name=pname,
             default_value=float(value), group=group, sort_priority=i)
    for i, (pname, (rgb, group)) in enumerate(VECTORS.items()):
        node(pname, unreal.MaterialExpressionVectorParameter, -1400, -500 - 160 * i, parameter_name=pname,
             default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0), group=group)
    for pname, (path, group) in TEXTURES.items():
        node(pname, unreal.MaterialExpressionTextureSampleParameter2D, -600, -300, parameter_name=pname,
             texture=unreal.load_asset(path), sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_COLOR, group=group)
    for i, (key, (code, inputs, out)) in enumerate(CUSTOM.items()):
        n = node(key, unreal.MaterialExpressionCustom, -1000 + 300 * (i // 2), -200 + 300 * (i % 2), description=key,
                 code=code, output_type=out_types[out])
        pins = []
        for pin in inputs:
            ci = unreal.CustomInput()
            ci.set_editor_property("input_name", pin)
            pins.append(ci)
        n.set_editor_property("inputs", pins)
    for src, so, dst, di in EDGES:
        ok = mel.connect_material_expressions(nodes[src], so, nodes[dst], di)
        if not ok and len(mel.get_material_expression_input_names(nodes[dst])) == 1:
            ok = mel.connect_material_expressions(nodes[src], so, nodes[dst], "")   # single-input nodes report 'None'
        if not ok:
            _stop(run, "CONNECT|%s.%s->%s.%s" % (src, so, dst, di))
    for src, prop in PROPS:
        if not mel.connect_material_property(nodes[src], "", getattr(unreal.MaterialProperty, prop)):
            _stop(run, "CONNECT_PROPERTY|%s->%s" % (src, prop))
    mel.recompile_material(mat)
    _verify_master(run, mat)
    for n in PASSAGES:
        folder, name = (MI_PATTERN % n).rsplit("/", 1)
        mi = tools.create_asset(name, folder, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        if mi is None:
            _stop(run, "CREATE_MI|P%02d" % n)
        mel.set_material_instance_parent(mi, mat)
        for pname, value in mi_defaults(n).items():
            mel.set_material_instance_scalar_parameter_value(mi, pname, float(value))   # the bool may lie: read back
        mel.update_material_instance(mi)
        _verify_mi(run, mi, n, mi_defaults(n))
    want = sorted([MASTER] + [MI_PATTERN % n for n in PASSAGES])
    census = _census()
    if census["maps"] or census["content"] != want:
        _stop(run, "DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))
    saved = {p: bool(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False)) for p in want}
    if not all(saved.values()) or _census() != {"content": [], "maps": []}:
        _stop(run, "SAVE|%r|%s" % (saved, json.dumps(_census())))
    unreal.log("%s_BUILD_OK|run=%s|master=%s|mis=%d|expressions=%d|check the log for 'Failed to compile' in ~20 s"
               % (MARK, run, MASTER, len(PASSAGES), int(mel.get_num_material_expressions(mat))))


def _verify_master(run, mat):
    mel = _mel()
    got = (sorted(str(n) for n in mel.get_scalar_parameter_names(mat)), sorted(str(n) for n in mel.get_vector_parameter_names(mat)),
           sorted(str(n) for n in mel.get_texture_parameter_names(mat)))
    if got != (sorted(SCALARS), sorted(VECTORS), sorted(TEXTURES)):
        _stop(run, "MASTER_PARAM_NAMES|%r" % (got,))
    for pname, (value, _) in SCALARS.items():
        if abs(float(mel.get_material_default_scalar_parameter_value(mat, pname)) - float(value)) > 1e-4:
            _stop(run, "MASTER_DEFAULT|" + pname)
    if int(mel.get_num_material_expressions(mat)) != EXPECTED_EXPRESSIONS:
        _stop(run, "EXPRESSION_COUNT|%d|want %d" % (int(mel.get_num_material_expressions(mat)), EXPECTED_EXPRESSIONS))
    for key in ("two_sided", "used_with_geometry_cache"):
        if not bool(mat.get_editor_property(key)):
            _stop(run, "MASTER_FLAG|" + key)
    for src, prop in PROPS:
        n = mel.get_material_property_input_node(mat, getattr(unreal.MaterialProperty, prop))
        if n is None:
            _stop(run, "PROPERTY_UNWIRED|" + prop)


def _verify_mi(run, mi, n, scalars, texture=None):
    mel = _mel()
    par = mi.get_editor_property("parent")
    if par is None or _pk(par.get_path_name()) != MASTER:
        _stop(run, "MI_PARENT|P%02d|%s" % (n, par))
    for pname, value in scalars.items():
        got = float(mel.get_material_instance_scalar_parameter_value(mi, pname))
        if abs(got - float(value)) > 1e-4:
            _stop(run, "MI_SCALAR|P%02d|%s|%r want %r" % (n, pname, got, value))
    if texture is not None:
        got = mel.get_material_instance_texture_parameter_value(mi, "Image")
        if got is None or _pk(got.get_path_name()) != texture:
            _stop(run, "MI_TEXTURE|P%02d|%s want %s" % (n, got, texture))


def _import_png(run, png, dest):
    folder, name = dest.rsplit("/", 1)
    if unreal.EditorAssetLibrary.does_asset_exist(dest):
        _stop(run, "TEXTURE_EXISTS|" + dest)
    task = unreal.AssetImportTask()                                 # s3_flats / hangar_exit_doors precedent
    for key, value in (("filename", png), ("destination_path", folder), ("destination_name", name),
                       ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(key, value)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = unreal.EditorAssetLibrary.load_asset(dest)
    if not isinstance(tex, unreal.Texture2D):
        _stop(run, "IMPORT_FAILED|%s|NOTHING SAVED" % dest)
    if not bool(tex.get_editor_property("srgb")):
        tex.set_editor_property("srgb", True)                       # a colour picture
    return tex


def _set(run, args, n):
    mel = _mel()
    mi_path = MI_PATTERN % n
    mi = unreal.EditorAssetLibrary.load_asset(mi_path)
    if mi is None:
        _stop(run, "MI_MISSING|%s (run BUILD first)" % mi_path)
    prev = mel.get_material_instance_texture_parameter_value(mi, "Image")
    warnings = []
    if args.get("png"):
        png = str(args["png"])
        if not os.path.isfile(png):
            _stop(run, "PNG_MISSING|" + png)
        try:
            size = png_size(png)
        except PlanError as exc:
            _stop(run, str(exc))
        warnings = png_warnings(size, n, args.get("mi_scalars"))
        dest = TEX_FOLDER + "/" + texture_name(n, png, datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
        tex = _import_png(run, png, dest)
    else:
        dest = str(args["texture"]).split(".")[0]
        tex = unreal.EditorAssetLibrary.load_asset(dest)
        if not isinstance(tex, unreal.Texture2D):
            _stop(run, "TEXTURE_NOT_FOUND|" + dest)
    values = set_values(args)
    mel.set_material_instance_texture_parameter_value(mi, "Image", tex)   # the bool may lie: read back below
    for pname, value in values.items():
        mel.set_material_instance_scalar_parameter_value(mi, pname, value)
    mel.update_material_instance(mi)
    _verify_mi(run, mi, n, values, dest)
    want = sorted([mi_path] + ([dest] if args.get("png") else []))
    census = _census()
    if census["maps"] or census["content"] != want:
        _stop(run, "DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))
    saved = {p: bool(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False)) for p in want}
    if not all(saved.values()) or _census() != {"content": [], "maps": []}:
        _stop(run, "SAVE|%r|%s" % (saved, json.dumps(_census())))
    _verify_mi(run, unreal.EditorAssetLibrary.load_asset(mi_path), n, values, dest)
    log_path = os.path.join(_here(), LOG_NAME)
    log = json.load(open(log_path, encoding="utf-8")) if os.path.exists(log_path) else []
    log.append({"run": run, "passage": n, "texture": dest, "previous": _pk(prev.get_path_name()) if prev else None,
                "values": values, "png": args.get("png"), "warnings": warnings})
    with open(log_path, "w", encoding="utf-8") as handle:
        json.dump(log, handle, indent=1)
    for w in warnings:
        unreal.log_warning("%s_WARNING|run=%s|%s" % (MARK, run, w))
    unreal.log("%s_SET_OK|run=%s|passage=P%02d|texture=%s|previous=%s|undo=SET texture=<previous>"
               % (MARK, run, n, dest, log[-1]["previous"]))


def _curtain(run, n):
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    for label in CURTAIN_LABELS[n]:
        rows = [a for a in actors if str(a.get_actor_label()) == label]
        if len(rows) == 1:
            comp = rows[0].get_component_by_class(unreal.GeometryCacheComponent)
            if comp is None:
                _stop(run, "NOT_A_GEOMETRY_CACHE_ACTOR|" + label)
            return rows[0], comp
        if len(rows) > 1:
            _stop(run, "LABEL_COUNT|%s|%d" % (label, len(rows)))
    _stop(run, "NO_BACK_CURTAIN|P%02d|%s (place it first: passage_end_drape.py)" % (n, CURTAIN_LABELS[n]))


def _assign(run, args, n, undo):
    rec_path = os.path.join(_here(), RECORD_PATTERN % n)
    actor, comp = _curtain(run, n)
    slots = int(comp.get_num_materials())
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not undo:
        if os.path.exists(rec_path):
            _stop(run, "RECORD_EXISTS|%s (UNASSIGN first)" % rec_path)
        mi = unreal.EditorAssetLibrary.load_asset(MI_PATTERN % n)
        if mi is None:
            _stop(run, "MI_MISSING|run BUILD first")
        overrides = list(comp.get_editor_property("override_materials") or [])
        prev = [_pk(m.get_path_name()) if m else None for m in overrides]
        project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        backup = os.path.join(project, "Backups", "PreCurtainImageAssign-P%02d-%s" % (n, run))
        os.makedirs(backup, exist_ok=False)
        shutil.copy2(_content_file(EXPECTED_WORLD, ".umap"), backup)
        fd = os.open(rec_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"run": run, "passage": n, "actor": str(actor.get_actor_label()), "slots": slots,
                       "previous_overrides": prev, "backup": backup, "decided_by": args.get("decided_by")}, handle, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        actor.modify()
        for i in range(slots):
            comp.set_material(i, mi)
        want = [MI_PATTERN % n] * slots
    else:
        rec = json.load(open(rec_path, encoding="utf-8"))
        if str(actor.get_actor_label()) != rec["actor"]:
            _stop(run, "ACTOR_CHANGED|%s vs %s" % (actor.get_actor_label(), rec["actor"]))
        actor.modify()
        prev = rec["previous_overrides"]
        for i in range(slots):
            path = prev[i] if i < len(prev) else None
            comp.set_material(i, unreal.load_asset(path) if path else None)
        want = None
    got = [_pk(comp.get_material(i).get_path_name()) if comp.get_material(i) else None for i in range(slots)]
    if want is not None and got != want:
        _stop(run, "MATERIAL_READBACK|%r want %r|NOTHING SAVED; Don't-Save restart (the override may not win on a "
                   "GeometryCacheComponent)" % (got, want))
    census = _census()
    if census["content"] or census["maps"] != [EXPECTED_WORLD]:
        _stop(run, "DIRTY_SCOPE|%s|NOTHING SAVED; Don't-Save restart" % json.dumps(census))
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, EXPECTED_WORLD) or _census() != {"content": [], "maps": []}:
        _stop(run, "SAVE|%s" % json.dumps(_census()))
    if undo:
        os.rename(rec_path, rec_path + ".reverted-" + run)
    unreal.log("%s_%s_OK|run=%s|passage=P%02d|actor=%s|materials=%s" % (MARK, "UNASSIGN" if undo else "ASSIGN", run, n,
                                                                       actor.get_actor_label(), got))


def _verify(run):
    mel = _mel()
    mat = unreal.EditorAssetLibrary.load_asset(MASTER)
    if mat is None:
        _stop(run, "MASTER_MISSING")
    _verify_master(run, mat)
    rows = []
    for n in PASSAGES:
        mi = unreal.EditorAssetLibrary.load_asset(MI_PATTERN % n)
        tex = mel.get_material_instance_texture_parameter_value(mi, "Image") if mi else None
        rows.append("P%02d:%s" % (n, _pk(tex.get_path_name()) if tex else None))
    unreal.log("%s_VERIFY_OK|run=%s|mutated=0|%s" % (MARK, run, "|".join(rows)))


def main():
    run = datetime.datetime.now().strftime("CI-%Y%m%d-%H%M%S")
    with open(os.path.join(_here(), ARGS_NAME), "r", encoding="utf-8") as handle:
        args = json.load(handle)
    run = str(args.get("run_id") or run)
    try:
        mode, n = validate_args(args)
    except PlanError as exc:
        _stop(run, "ARGS|" + str(exc))
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if editor.get_game_world() is not None:
        _stop(run, "PIE_OR_SIE_ACTIVE (refused; never ends PIE)")
    if world is None or str(world.get_outermost().get_name()) != EXPECTED_WORLD:
        _stop(run, "WRONG_WORLD")
    if mode != "VERIFY" and _census() != {"content": [], "maps": []}:
        _stop(run, "DIRTY_CENSUS|%s" % json.dumps(_census()))
    if mode == "BUILD":
        _build(run)
    elif mode == "SET":
        _set(run, args, n)
    elif mode in ("ASSIGN", "UNASSIGN"):
        _assign(run, args, n, undo=(mode == "UNASSIGN"))
    else:
        _verify(run)


if unreal is not None:
    main()
