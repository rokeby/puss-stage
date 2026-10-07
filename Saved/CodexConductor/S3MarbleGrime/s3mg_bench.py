"""S3 MARBLE GRIME BENCH -- DRAFT, NOT RUN (written offline 7 Oct while the editor was closed).

Reversible, NON-SAVING A/B/C of the S3 right marble liner + its hand prints, seen from the S3 main camera
(PassageStills S3 still 0, master frame 20756545). Look choices are Gary's; this only makes stills to choose from.

STAGES (each its own MCP call through ExecuteProjectPythonFile; runpy init_globals S3MG_STAGE / S3MG_VARIANT / S3MG_RUN):
  plan      OFFLINE-capable (no unreal needed): writes S3MarbleGrime/s3mg_bench_plan.json from geometry.json.
  assets    EDITOR (PIE may or may not run): import the six textures (2048 or smaller, LINEAR except the colour)
            into /Game/ZZ_Bench/S3MarbleGrime/Textures and build ONE create-only decal master
            /Game/ZZ_Bench/S3MarbleGrime/M_ZZ_S3MG_GreaseDecal (Deferred Decal, Translucent; Opacity/Roughness/Normal
            only, NO BaseColor). NEVER saves, never deletes a node, never edits a pre-existing asset.
            Refuses if any target asset exists. Collects garbage after. Logs S3MG_ASSETS_BUILT (no success marker:
            compile is async -- run stage "verify_assets" ~30 s later).
  verify_assets  reads the log since the run's START marker; FAILS on "Failed to compile" for the master;
            logs S3MG_ASSETS_OK|run=.. only after the read-back of every texture setting.
  apply     PIE ONLY (refuses without a PIE world). Writes the originals JSON FIRST and logs its path, then changes
            ONLY PIE-world copies: the liner StaticMeshActor_350 gets a MaterialInstanceDynamic of its own MI (R0)
            with new textures/scalars; each in-frame print decal gets a MID of its own v3 MI with OpacityGain lowered,
            plus a spawned ZZ_ grease decal (MID of the new master, atlas rect copied from the original MI);
            variant B adds the low-wall band decal; variant C adds three ZZ_ RectLights at the mirror angle.
            Read-back asserted per change; logs S3MG_BENCH_APPLIED|run=..|variant=..
  stills    NOT in this file: the conductor runs the existing scene_stills_run.py with
            scene_stills_args.json = {"passage": "S3", "fractions": [0.3], "label": "s3mg_<variant>"}.
  restore   PIE ONLY: restores every PIE-copy material from the originals file, destroys every PIE actor tagged
            ZZ_S3MG (found with GameplayStatics on the PIE world -- they are NOT transient, so they are listed;
            PIE end destroys them regardless), verifies against the file; logs S3MG_BENCH_RESTORED|run=..
  census    EDITOR world check: StaticMeshActor_350 slot 0 is still MI_S3_Marble_Tiling_Daylight_R0, no ZZ_S3MG actor in
            the editor level, dirty maps unchanged from the originals file's census.

WHY PIE COPIES: nothing in the editor level or any saved asset is touched, so a crash mid-bench loses nothing
(memory: puss-bench-originals-to-file, puss-mcp-python-crashes-the-editor). The new bench assets stay UNSAVED in
/Game/ZZ_Bench/S3MarbleGrime; the conductor discards them (Don't Save) or the APPLY stage re-creates them for real.
DEVIATION from "destroy what you spawn in the same call": stills need ticks across calls, so spawned PIE actors live
from apply to restore. Mitigations: they exist only in the PIE world, carry tag ZZ_S3MG, are listed by
GameplayStatics (non-transient), capture_every_frame is irrelevant (no SceneCapture is spawned), and PIE end kills them.

UNVERIFIED (each must be checked by the live reads first -- see the report's LIVE READS list):
  - a decal material with BaseColor UNCONNECTED writes no DBuffer colour (DecalCommon.ush:108-113 shares one opacity
    across colour/normal/roughness when written; whether colour is skipped depends on private C++) [inferred]
  - PIE copies keep object names (StaticMeshActor_350) and labels [inferred]
  - create_dynamic_material_instance on a DecalComponent in PIE renders like the MI [inferred]
"""
import json
import math
import os
import time
import traceback

ROOT = "E:/PussStage"
HERE = ROOT + "/Saved/CodexConductor/S3MarbleGrime"
SRC = ROOT + "/DerivedAssets/S3Marble/Grime_20261007"
GEOMETRY = SRC + "/geometry.json"
PLAN = HERE + "/s3mg_bench_plan.json"
ORIGINALS = HERE + "/s3mg_bench_originals.json"       # written BEFORE any change (apply)
APPLIED = HERE + "/s3mg_bench_applied.json"
STAGES_RECORD = HERE + "/s3mg_bench_stages.json"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LINER_NAME = "StaticMeshActor_350"                   # "S3 Marble Inner Wall Right" (s3_marble_tiling_record.json)
LINER_LABEL = "S3 Marble Inner Wall Right"
LINER_MI = "/Game/InfinityStage/Dev/Materials/MI_S3_Marble_Tiling_Daylight_R0"
ASSET_DIR = "/Game/ZZ_Bench/S3MarbleGrime"
TEX_DIR = ASSET_DIR + "/Textures"
GREASE_MASTER = ASSET_DIR + "/M_ZZ_S3MG_GreaseDecal"
PRINT_NORMAL = "/Game/Scenes/Scene3/HandPrints/Textures/T_S03_HandPrints_Normal"
TAG = "ZZ_S3MG"
PREFIX = "ZZ_S3MG_"

# file -> (asset name, srgb, compression enum name, LOD group / notes)
TEXTURES = {
    "T_S3MG_Marble021_RoughGrime.png": ("T_S3MG_Marble021_RoughGrime", False, "TC_GRAYSCALE"),
    "T_S3MG_Marble021_NormalDX_Scratch.png": ("T_S3MG_Marble021_NormalDX_Scratch", False, "TC_NORMALMAP"),
    "T_S3MG_Marble021_Color_Grime_sRGB.png": ("T_S3MG_Marble021_Color_Grime", True, "TC_DEFAULT"),
    "T_S3MG_GreaseAtlas.png": ("T_S3MG_GreaseAtlas", False, "TC_MASKS"),
    "T_S3MG_GrimeBand.png": ("T_S3MG_GrimeBand", False, "TC_MASKS"),
    "T_S3MG_SeamStrip.png": ("T_S3MG_SeamStrip", False, "TC_MASKS"),
}

# variant knobs (proposals; Gary picks) -- the marble MID params are the master's own names (spaces included)
MARBLE_MID = {
    "textures": {"RoughnessTexture": "T_S3MG_Marble021_RoughGrime",
                 "NormalTexture": "T_S3MG_Marble021_NormalDX_Scratch",
                 "BaseColorTexture": "T_S3MG_Marble021_Color_Grime"},
    "scalars": {"Min Roughness": 0.04, "Max Roughness": 0.60, "RoughnessTextureWeight": 1.0},
}
PRINT_COLOUR_GAIN = 0.22          # v3 OpacityGain on the PIE copies (live 1.0 per hp_import_atlas.py:91 default; READ)
GREASE = {"GreaseGain": 1.0, "GreaseRoughMin": 0.30, "GreaseRoughRange": 0.25, "NormalStrength": 0.25}
BAND = {"GreaseGain": 0.85, "GreaseRoughMin": 0.20, "GreaseRoughRange": 0.50, "NormalStrength": 0.0}
VARIANTS = {
    "A": {"marble": True, "prints": True, "band": False, "lights": None},
    "B": {"marble": True, "prints": True, "band": True, "lights": None},
    "C": {"marble": True, "prints": True, "band": False, "lights": {"intensity_cd": 4000.0, "diffuse_scale": 0.10}},
    "C_phys": {"marble": True, "prints": True, "band": False, "lights": {"intensity_cd": 1500.0, "diffuse_scale": 1.0}},
    "base_C": {"marble": False, "prints": False, "band": False, "lights": {"intensity_cd": 4000.0, "diffuse_scale": 0.10}},
}

# Custom HLSL (pure literals; same AtlasUV / StainNormal code as hp_import_atlas.py CUSTOM_NODES_V3, which compiled 6 Oct)
CUSTOM = {
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
ATLAS_PARAMS = ("AtlasU0", "AtlasV0", "AtlasUSize", "AtlasVSize", "FlipU", "GlobalFlipU", "GlobalFlipV")


class BenchError(RuntimeError):
    pass


def require(cond, msg):
    if not cond:
        raise BenchError("S3MG_BENCH_FAILED|" + msg)


def utc():
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def write_verified(path, data):
    text = json.dumps(data, indent=1, sort_keys=True, default=str)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    with open(path, encoding="utf-8") as f:
        require(f.read() == text, "READBACK|" + path)
    return path


# ------------------------------------------------------------------------------------------- plan (offline)
def _decal_rotator_R(roll_deg=0.0):
    """Same convention as Tools/FlatV3/handprints/build_handprint_placement.py:137-158 for the R wall."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "bhp", ROOT + "/Tools/FlatV3/handprints/build_handprint_placement.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    x, y, z = m.decal_axes([0.0, -1.0, 0.0], roll_deg)
    return m.rotator_from_axes(x, y, z), {"x": x, "y": y, "z": z}


def make_plan():
    geo = json.load(open(GEOMETRY))
    wall_y = geo["wall"]["plane_y_cm"]
    frame_x = sorted([geo["frame_on_wall"]["tl"]["wall_xz"][0], geo["frame_on_wall"]["tr"]["wall_xz"][0]])
    rot, axes = _decal_rotator_R(0.0)
    band_len = (frame_x[1] - frame_x[0]) + 300.0
    band = {"name": PREFIX + "Band", "location": [round((frame_x[0] + frame_x[1]) / 2, 1), wall_y, 95.0],
            "rotation": rot, "axes": axes,
            # DecalSize = half extents (X depth, Y image-down = height, Z image-right = along wall)
            "decal_size": [8.0, 100.0, round(band_len / 2, 1)],
            "atlas": {"AtlasU0": 0.0, "AtlasV0": 0.0, "AtlasUSize": round(band_len / 800.0, 4), "AtlasVSize": 1.0,
                      "FlipU": 0.0, "GlobalFlipU": 0.0, "GlobalFlipV": 0.0},
            "texture": "T_S3MG_GrimeBand", "params": BAND}
    lights = []
    for st in geo["mirror_light"]["strips_proposal"]:
        lights.append({"name": st["name"], "location": st["location_cm"], "rotation": st["rotation"],
                       "source_width": st["source_width_cm"], "source_height": st["source_height_cm"],
                       "barn_door_angle": 20.0, "barn_door_length": 40.0, "attenuation_radius": 3500.0,
                       "reflects_at_wall_cm": st["reflects_at_wall_cm"]})
    plan = {"tool": "s3mg_bench.py plan", "world": WORLD, "camera": geo["main_pose"],
            "liner": {"name": LINER_NAME, "label": LINER_LABEL, "mi": LINER_MI, "mid": MARBLE_MID},
            "prints": {"labels": [d["label"] for d in geo["decals"]], "count": len(geo["decals"]),
                       "colour_gain": PRINT_COLOUR_GAIN, "grease": GREASE},
            "band": band, "lights": lights, "variants": VARIANTS,
            "stills_args": {"passage": "S3", "fractions": [0.3], "label": "s3mg_<variant>"}}
    write_verified(PLAN, plan)
    return plan


# ------------------------------------------------------------------------------------------- unreal helpers
def _u():
    import unreal
    return unreal


def census():
    u = _u()
    def names(pkgs):
        return sorted(str(p.get_path_name()).split(".", 1)[0] for p in pkgs)
    return {"maps": names(u.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
            "content": names(u.EditorLoadingAndSavingUtils.get_dirty_content_packages())}


def editor_world():
    u = _u()
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    require(w is not None and WORLD in w.get_path_name(), "EDITOR_WORLD|%s" % (w and w.get_path_name()))
    return w


def pie_world():
    u = _u()
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_game_world()
    require(w is not None, "NO_PIE_WORLD")
    return w


def actors(world, cls=None):
    u = _u()
    return list(u.GameplayStatics.get_all_actors_of_class(world, cls or u.Actor))


def find_by_name(world, name):
    hits = [a for a in actors(world) if a.get_name() == name]
    require(len(hits) == 1, "FIND|%s|n=%d" % (name, len(hits)))
    return hits[0]


def find_by_label(world, label):
    hits = [a for a in actors(world) if a.get_actor_label() == label]
    require(len(hits) == 1, "FIND_LABEL|%s|n=%d" % (label, len(hits)))
    return hits[0]


def path(o):
    return o.get_path_name() if o is not None else None


# ------------------------------------------------------------------------------------------- stage: assets
class Graph:
    def __init__(self, mat):
        self.u = _u()
        self.mel = self.u.MaterialEditingLibrary
        self.mat = mat

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
        n = self.node(self.u.MaterialExpressionCustom, x, y, description=name, code=spec["code"],
                      output_type=getattr(self.u.CustomMaterialOutputType, out_type))
        ins = []
        for in_name in spec["inputs"]:
            ci = self.u.CustomInput()
            ci.set_editor_property("input_name", in_name)
            ins.append(ci)
        n.set_editor_property("inputs", ins)
        return n

    def scalar(self, name, value, x, y):
        return self.node(self.u.MaterialExpressionScalarParameter, x, y, parameter_name=name,
                         default_value=float(value), group="S3MG")


def import_textures(run):
    u = _u()
    eal = u.EditorAssetLibrary
    for fname, (asset, _s, _c) in TEXTURES.items():
        require(not eal.does_asset_exist(TEX_DIR + "/" + asset), "TEXTURE_EXISTS|" + asset)
        require(os.path.isfile(SRC + "/" + fname), "SOURCE_MISSING|" + fname)
    tasks = []
    for fname, (asset, _s, _c) in TEXTURES.items():
        t = u.AssetImportTask()
        t.set_editor_property("filename", (SRC + "/" + fname).replace("/", "\\"))
        t.set_editor_property("destination_path", TEX_DIR)
        t.set_editor_property("destination_name", asset)
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", False)
        t.set_editor_property("save", False)
        tasks.append(t)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    out = {}
    for fname, (asset, srgb, comp) in TEXTURES.items():
        tex = eal.load_asset(TEX_DIR + "/" + asset)
        require(tex is not None, "IMPORT_FAILED|" + asset)
        tex.modify()
        tex.set_editor_property("srgb", srgb)
        tex.set_editor_property("compression_settings", getattr(u.TextureCompressionSettings, comp))
        if comp == "TC_NORMALMAP":
            tex.set_editor_property("flip_green_channel", False)
        tex.post_edit_change()
        got = {"srgb": bool(tex.get_editor_property("srgb")),
               "compression": str(tex.get_editor_property("compression_settings")),
               "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]}
        require(got["srgb"] == srgb and comp in got["compression"], "TEX_SETTINGS|%s|%s" % (asset, got))
        require(max(got["size"]) <= 2048 or got["size"] == [32, 32], "TEX_SIZE|%s|%s" % (asset, got["size"]))
        out[asset] = got
    return out


def build_grease_master():
    u = _u()
    require(not u.EditorAssetLibrary.does_asset_exist(GREASE_MASTER), "MASTER_EXISTS")
    mat = u.AssetToolsHelpers.get_asset_tools().create_asset(
        GREASE_MASTER.rsplit("/", 1)[1], ASSET_DIR, u.Material, u.MaterialFactoryNew())
    require(mat is not None, "MASTER_CREATE")
    mat.modify()
    mat.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)          # blend BEFORE domain (v1 lesson)
    require(mat.get_editor_property("blend_mode") == u.BlendMode.BLEND_TRANSLUCENT, "BLEND")
    mat.modify()
    mat.set_editor_property("material_domain", u.MaterialDomain.MD_DEFERRED_DECAL)
    require(mat.get_editor_property("material_domain") == u.MaterialDomain.MD_DEFERRED_DECAL, "DOMAIN")
    g = Graph(mat)
    ST = u.MaterialSamplerType
    uv = g.node(u.MaterialExpressionTextureCoordinate, -1800, 0, coordinate_index=0)
    p = {n: g.scalar(n, v, -1800, 120 + 90 * i) for i, (n, v) in enumerate((
        ("AtlasU0", 0.0), ("AtlasV0", 0.0), ("AtlasUSize", 1.0), ("AtlasVSize", 1.0), ("FlipU", 0.0),
        ("GlobalFlipU", 0.0), ("GlobalFlipV", 0.0), ("GreaseGain", GREASE["GreaseGain"]),
        ("GreaseRoughMin", GREASE["GreaseRoughMin"]), ("GreaseRoughRange", GREASE["GreaseRoughRange"]),
        ("NormalStrength", GREASE["NormalStrength"])))}
    auv = g.custom(-1400, 200, "AtlasUV")
    g.link(uv, "", auv, "UV")
    for pin, name in (("U0", "AtlasU0"), ("V0", "AtlasV0"), ("US", "AtlasUSize"), ("VS", "AtlasVSize"),
                      ("FlipU", "FlipU"), ("GlobalFlipU", "GlobalFlipU"), ("GlobalFlipV", "GlobalFlipV")):
        g.link(p[name], "", auv, pin)
    grease_tex = u.EditorAssetLibrary.load_asset(TEX_DIR + "/T_S3MG_GreaseAtlas")
    norm_tex = u.EditorAssetLibrary.load_asset(PRINT_NORMAL)
    require(grease_tex is not None and norm_tex is not None, "MASTER_TEXTURES")
    mask = g.node(u.MaterialExpressionTextureSampleParameter2D, -1000, 0, parameter_name="GreaseMask",
                  texture=grease_tex, sampler_type=ST.SAMPLERTYPE_MASKS, group="S3MG")
    g.link(auv, "", mask, "UVs")
    nrm = g.node(u.MaterialExpressionTextureSampleParameter2D, -1000, 400, parameter_name="PrintNormal",
                 texture=norm_tex, sampler_type=ST.SAMPLERTYPE_NORMAL, group="S3MG")
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
    MP = u.MaterialProperty
    g.prop(op, "", MP.MP_OPACITY)
    g.prop(rg, "", MP.MP_ROUGHNESS)
    g.prop(nn, "", MP.MP_NORMAL)
    # deliberately NO MP_BASE_COLOR: grease = roughness + normal only (colour stays the marble's)
    u.MaterialEditingLibrary.layout_material_expressions(mat)
    errs = [str(e) for e in (u.MaterialEditingLibrary.recompile_material(mat) or [])]
    require(not errs, "MASTER_COMPILE|" + json.dumps(errs[:6]))
    return {"master": path(mat), "domain": str(mat.get_editor_property("material_domain")),
            "blend": str(mat.get_editor_property("blend_mode")),
            "scalars": sorted(str(n) for n in u.MaterialEditingLibrary.get_scalar_parameter_names(mat))}


def stage_assets(run):
    u = _u()
    marker = "S3MG_ASSETS_START|run=%s" % run
    u.log(marker)
    before = census()
    rec = {"run": run, "start_marker": marker, "census_before": before}
    write_verified(STAGES_RECORD, rec)
    rec["textures"] = import_textures(run)
    u.SystemLibrary.collect_garbage()
    rec["master"] = build_grease_master()
    u.SystemLibrary.collect_garbage()
    rec["saved"] = False
    rec["census_after"] = census()
    require(rec["census_after"]["maps"] == before["maps"], "MAPS_DIRTIED|%s" % rec["census_after"]["maps"])
    write_verified(STAGES_RECORD, rec)
    u.log("S3MG_ASSETS_BUILT|run=%s|textures=%d|unsaved=1" % (run, len(rec["textures"])))


def stage_verify_assets(run):
    u = _u()
    rec = json.load(open(STAGES_RECORD))
    require(rec["run"] == run, "RUN_MISMATCH")
    log = open(ROOT + "/Saved/Logs/PussStage.log", encoding="utf-8", errors="replace").read()
    i = log.rfind(rec["start_marker"])
    require(i >= 0, "START_MARKER_NOT_IN_LOG")
    tail = log[i:]
    bad = [ln for ln in tail.splitlines() if "M_ZZ_S3MG_GreaseDecal" in ln and
           ("Failed to compile" in ln or "Default Material will be used" in ln)]
    require(not bad, "MASTER_COMPILE_LOG|" + json.dumps(bad[:4]))
    m = u.EditorAssetLibrary.load_asset(GREASE_MASTER)
    stats = u.MaterialEditingLibrary.get_statistics(m)
    require(stats.num_pixel_shader_instructions > 0, "PENDING_COMPILE|retry in 30 s")
    for asset, got in rec["textures"].items():
        tex = u.EditorAssetLibrary.load_asset(TEX_DIR + "/" + asset)
        require(bool(tex.get_editor_property("srgb")) == got["srgb"], "TEX_RECHECK|" + asset)
    u.log("S3MG_ASSETS_OK|run=%s|ps=%d" % (run, stats.num_pixel_shader_instructions))


# ------------------------------------------------------------------------------------------- stage: apply (PIE)
def stage_apply(run, variant):
    u = _u()
    require(variant in VARIANTS, "VARIANT|" + str(variant))
    v = VARIANTS[variant]
    plan = json.load(open(PLAN))
    world = pie_world()
    mel = u.MaterialEditingLibrary
    liner = find_by_name(world, LINER_NAME)
    smc = liner.static_mesh_component
    decals = {}
    for a in actors(world, u.DecalActor):
        lab = a.get_actor_label()
        if lab in plan["prints"]["labels"]:
            decals[lab] = a
    require(len(decals) == plan["prints"]["count"], "PRINTS_FOUND|%d/%d" % (len(decals), plan["prints"]["count"]))
    stale = [a.get_name() for a in actors(world) if TAG in [str(t) for t in a.tags]]
    require(not stale, "STALE_BENCH_ACTORS|%s" % stale)
    # ---- ORIGINALS FIRST
    orig = {"run": run, "variant": variant, "world": world.get_path_name(), "utc": utc(),
            "census": census(),
            "liner": {"name": liner.get_name(), "slot0": path(smc.get_material(0)),
                      "n_slots": smc.get_num_materials()},
            "decals": {lab: {"material": path(a.decal.get_decal_material()), "sort_order": a.decal.sort_order}
                       for lab, a in sorted(decals.items())}}
    require(orig["liner"]["slot0"] and orig["liner"]["slot0"].split(".")[0] == LINER_MI,
            "LINER_NOT_R0|%s" % orig["liner"]["slot0"])
    write_verified(ORIGINALS, orig)
    u.log("S3MG_BENCH_ORIGINALS|run=%s|path=%s" % (run, ORIGINALS))
    applied = {"run": run, "variant": variant, "spawned": [], "mids": []}
    try:
        if v["marble"]:
            mid = smc.create_dynamic_material_instance(0, smc.get_material(0))
            for pname, asset in MARBLE_MID["textures"].items():
                tex = u.EditorAssetLibrary.load_asset(TEX_DIR + "/" + asset)
                require(tex is not None, "BENCH_TEXTURE_MISSING|" + asset)
                mid.set_texture_parameter_value(pname, tex)
                require(path(mid.k2_get_texture_parameter_value(pname)) == path(tex), "MID_TEX|" + pname)
            for k, val in MARBLE_MID["scalars"].items():
                mid.set_scalar_parameter_value(k, val)
                require(abs(mid.k2_get_scalar_parameter_value(k) - val) < 1e-5, "MID_SCALAR|" + k)
            require(smc.get_material(0) == mid, "LINER_MID_NOT_APPLIED")
            applied["mids"].append({"on": LINER_NAME, "scalars": MARBLE_MID["scalars"]})
        if v["prints"]:
            gm = u.EditorAssetLibrary.load_asset(GREASE_MASTER)
            require(gm is not None, "GREASE_MASTER_MISSING")
            for lab, a in sorted(decals.items()):
                dc = a.decal
                src_mi = dc.get_decal_material()
                cmid = dc.create_dynamic_material_instance()
                cmid.set_scalar_parameter_value("OpacityGain", PRINT_COLOUR_GAIN)
                require(abs(cmid.k2_get_scalar_parameter_value("OpacityGain") - PRINT_COLOUR_GAIN) < 1e-5,
                        "PRINT_GAIN|" + lab)
                atlas = {k: float(mel.get_material_instance_scalar_parameter_value(src_mi, k)) for k in ATLAS_PARAMS}
                # spawn into the PIE world (never EditorLevelLibrary: that targets the editor level)
                t = a.get_actor_transform()
                g = u.GameplayStatics.finish_spawning_actor(
                    u.GameplayStatics.begin_deferred_actor_spawn_from_class(world, u.DecalActor, t), t)
                require(g is not None and g.get_world() == world, "SPAWNED_IN_WRONG_WORLD")
                g.tags = [TAG]
                applied["spawned"].append(g.get_name())        # recorded before anything else can fail
                g.decal.decal_size = dc.decal_size
                g.decal.sort_order = dc.sort_order + 1
                gmid = u.KismetMaterialLibrary.create_dynamic_material_instance(world, gm)
                for k, val in list(atlas.items()) + list(GREASE.items()):
                    gmid.set_scalar_parameter_value(k, val)
                g.decal.set_decal_material(gmid)
                require(g.decal.get_decal_material() == gmid, "GREASE_MID|" + lab)
        if v["band"]:
            b = plan["band"]
            gm = u.EditorAssetLibrary.load_asset(GREASE_MASTER)
            loc = u.Vector(*b["location"])
            rot = u.Rotator(roll=b["rotation"]["roll"], pitch=b["rotation"]["pitch"], yaw=b["rotation"]["yaw"])
            g = u.GameplayStatics.begin_deferred_actor_spawn_from_class(world, u.DecalActor,
                                                                       u.Transform(loc, rot, u.Vector(1, 1, 1)))
            g = u.GameplayStatics.finish_spawning_actor(g, u.Transform(loc, rot, u.Vector(1, 1, 1)))
            g.tags = [TAG]
            g.decal.decal_size = u.Vector(*b["decal_size"])
            bmid = u.KismetMaterialLibrary.create_dynamic_material_instance(world, gm)
            for k, val in list(b["atlas"].items()) + list(b["params"].items()):
                bmid.set_scalar_parameter_value(k, val)
            bmid.set_texture_parameter_value("GreaseMask", u.EditorAssetLibrary.load_asset(TEX_DIR + "/" + b["texture"]))
            g.decal.set_decal_material(bmid)
            applied["spawned"].append(g.get_name())
        if v["lights"]:
            for L in plan["lights"]:
                loc = u.Vector(*L["location"])
                rot = u.Rotator(roll=L["rotation"]["roll"], pitch=L["rotation"]["pitch"], yaw=L["rotation"]["yaw"])
                t = u.Transform(loc, rot, u.Vector(1, 1, 1))
                g = u.GameplayStatics.finish_spawning_actor(
                    u.GameplayStatics.begin_deferred_actor_spawn_from_class(world, u.RectLight, t), t)
                g.tags = [TAG]
                c = g.rect_light_component
                c.set_mobility(u.ComponentMobility.MOVABLE)
                c.set_intensity_units(u.LightUnits.CANDELAS)
                c.set_intensity(v["lights"]["intensity_cd"])           # UFUNCTION: no Modify (memory: light benches)
                c.set_source_width(L["source_width"])
                c.set_source_height(L["source_height"])
                c.set_barn_door_angle(L["barn_door_angle"])
                c.set_barn_door_length(L["barn_door_length"])
                c.set_attenuation_radius(L["attenuation_radius"])
                c.set_diffuse_scale(v["lights"]["diffuse_scale"])      # LightComponent.h:96, setter :360
                c.set_specular_scale(1.0)
                c.set_cast_shadows(False)
                got = {"units": str(c.get_editor_property("intensity_units")),
                       "intensity": c.get_editor_property("intensity"),
                       "w": c.get_editor_property("source_width"), "h": c.get_editor_property("source_height"),
                       "diffuse_scale": c.get_editor_property("diffuse_scale")}
                require("CANDELAS" in got["units"] and abs(got["intensity"] - v["lights"]["intensity_cd"]) < 1e-3
                        and abs(got["diffuse_scale"] - v["lights"]["diffuse_scale"]) < 1e-5, "LIGHT_READBACK|%s" % got)
                applied["spawned"].append(g.get_name())
                applied.setdefault("lights", []).append({"name": g.get_name(), **got, "loc": L["location"]})
        applied["census_after"] = census()
        require(applied["census_after"]["maps"] == orig["census"]["maps"], "APPLY_DIRTIED_MAPS")
        write_verified(APPLIED, applied)
        u.log("S3MG_BENCH_APPLIED|run=%s|variant=%s|spawned=%d" % (run, variant, len(applied["spawned"])))
    except Exception:
        u.log_error("S3MG_BENCH_APPLY_ERROR|run=%s|%s" % (run, traceback.format_exc().replace("\n", " | ")))
        write_verified(APPLIED, applied)
        stage_restore(run)                       # restore in the same call on any failure
        raise


# ------------------------------------------------------------------------------------------- stage: restore (PIE)
def stage_restore(run):
    u = _u()
    orig = json.load(open(ORIGINALS))
    require(orig["run"] == run, "RUN_MISMATCH|%s" % orig["run"])
    world = pie_world()
    liner = find_by_name(world, LINER_NAME)
    smc = liner.static_mesh_component
    mi = u.EditorAssetLibrary.load_asset(orig["liner"]["slot0"].split(".")[0])
    smc.set_material(0, mi)
    problems = []
    if path(smc.get_material(0)) != orig["liner"]["slot0"]:
        problems.append("LINER|%s" % path(smc.get_material(0)))
    by_label = {a.get_actor_label(): a for a in actors(world, u.DecalActor)}
    for lab, rec in orig["decals"].items():
        a = by_label.get(lab)
        if a is None:
            problems.append("DECAL_GONE|" + lab)
            continue
        a.decal.set_decal_material(u.EditorAssetLibrary.load_asset(rec["material"].split(".")[0]))
        if path(a.decal.get_decal_material()) != rec["material"]:
            problems.append("DECAL|" + lab)
    killed = []
    for a in actors(world):
        if TAG in [str(t) for t in a.tags]:
            killed.append(a.get_name())
            a.destroy_actor()
    left = [a.get_name() for a in actors(world) if TAG in [str(t) for t in a.tags]]
    if left:
        problems.append("BENCH_ACTORS_LEFT|%s" % left)
    if census()["maps"] != orig["census"]["maps"]:
        problems.append("MAPS_DIRTY_CHANGED")
    require(not problems, "RESTORE|" + json.dumps(problems[:10]))
    u.log("S3MG_BENCH_RESTORED|run=%s|destroyed=%d" % (run, len(killed)))


def stage_census(run):
    u = _u()
    w = editor_world()
    liner = find_by_name(w, LINER_NAME)
    slot0 = path(liner.static_mesh_component.get_material(0))
    require(slot0 and slot0.split(".")[0] == LINER_MI, "EDITOR_LINER_CHANGED|%s" % slot0)
    zz = [a.get_name() for a in actors(w) if TAG in [str(t) for t in a.tags]]
    require(not zz, "EDITOR_HAS_BENCH_ACTORS|%s" % zz)
    u.log("S3MG_BENCH_CENSUS_OK|run=%s" % run)


def main():
    stage = globals().get("S3MG_STAGE", "plan")
    run = globals().get("S3MG_RUN", "S3MG-" + utc())
    if stage == "plan":
        p = make_plan()
        print(json.dumps({"plan": PLAN, "prints": p["prints"]["count"], "lights": len(p["lights"]),
                          "band": p["band"]["decal_size"]}))
        return
    fn = {"assets": stage_assets, "verify_assets": stage_verify_assets, "restore": stage_restore,
          "census": stage_census}.get(stage)
    if stage == "apply":
        return stage_apply(run, globals().get("S3MG_VARIANT"))
    require(fn is not None, "STAGE|" + str(stage))
    fn(run)


main()
