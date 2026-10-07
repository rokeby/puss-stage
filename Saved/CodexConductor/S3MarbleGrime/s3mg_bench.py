"""S3 MARBLE GRIME BENCH v3 (editor-world POOL) -- PREPARED, NOT RUN (offline, 7 Oct). Gary picked variant C (grease +
scratches + faint grime + three 3 x 1.2 m mirror-angle window strips, DiffuseScale ~0.1). GO for a PIE bench, NO SAVE;
Gary does a Don't-Save restart afterwards in any case.

WHY A POOL (v3, 7 Oct): UE 5.8 Python has NO route that spawns into a running PIE world.
GameplayStatics.begin_deferred_actor_spawn_from_class / finish_spawning_actor raise AttributeError in this editor
[measured twice: Saved/CodexFlatV3/swapkit/stills/before/FV3STB-20261003-02/st_pie_first_check_runtime.json,
Saved/CodexConductor/LookBench/20261005-044136/look_bench_result.json; GameplayStatics.h:66-67,70-71 mark them
BlueprintInternalUseOnly]. Same answer as look_bench.py:5-10: spawn a hidden POOL into the EDITOR world before PIE
(EditorActorSubsystem.spawn_actor_from_class), let PIE duplicate it, and only set properties on the PIE copies.

Driven ONLY through s3mg_run.py (one ExecuteProjectPythonFile per stage via the s3mg_run_<stage>.py wrappers and
s3mg_<stage>_request.json). Args: S3MarbleGrime/s3mg_args.json {"run": "S3MG-...", "variant": "C", "pie": 1}
("run" spans prespawn..unspawn; "pie" numbers each fresh PIE session of that run, one still each).

STAGES
  plan           offline: s3mg_bench_plan.json from geometry.json (rerun is harmless).
  assets         EDITOR, refuses while PIE runs. 6 textures (<= 2048) + create-only M_ZZ_S3MG_GreaseDecal (Deferred
                 Decal, Translucent; Opacity/Roughness/Normal, NO BaseColor) under /Game/ZZ_Bench/S3MarbleGrime.
                 IDEMPOTENT-SAFE: all 7 present + matching -> REUSED; none -> CREATED; any other mix -> FAILED.
  verify_assets  EDITOR. FAILS on compile errors since this run's START marker; PENDING while PS instructions are 0.
  prespawn       EDITOR, PIE NOT running. Refuses if the MAP is already dirty (a Don't-Save restart would discard
                 someone else's level work), if dirty content is anything but our unsaved ZZ_Bench assets, if any
                 ZZ_S3MG actor exists, or if S3 Hangar Root is not LANDED (+-1 cm, rot 0). Writes the pool labels +
                 census to s3mg_prespawn_<run>.json BEFORE the first spawn, then spawns into the EDITOR world, labelled
                 ZZ_S3MG_*, tagged ZZ_S3MG, every one HIDDEN (component invisible + hidden in game; lights 0 cd):
                   3 RectLights ZZ_S3MG_Strip_0..2 at the plan's LANDED positions, attached KEEP_WORLD to S3 Hangar Root;
                   60 grease decals ZZ_S3MG_Grease_<print> SNAP_TO_TARGET-attached to their print decal, material =
                     the grease master asset (MIDs are made in PIE), decal size copied, sort order +1;
                   1 band decal ZZ_S3MG_Band at its landed pose, attached KEEP_WORLD to the anchor print's wall.
                 Reads every spawn back (world, label, tag, parent, position). Any failure -> destroys THIS call's spawns
                 by reference -> FAILED. It dirties the map: expected, NEVER saved (saves refuse on ZZ_ actors anyway).
  apply          PIE ONLY, FRESH PIE (transport outside S3). Originals (liner + print materials + pool copy state) to
                 s3mg_originals_<run>-p<pie>.json BEFORE any change. Finds every pool copy by label + tag (refuses if
                 any is missing, duplicated or already shown) and checks it sits where the plan says for the CURRENT
                 hangar pose (landed->now rigid map through the root / the anchor print; grease = on its print).
                 Then only sets MIDs / swaps materials / shows / sets intensities on PIE copies:
                   liner StaticMeshActor_350: MID of R0 + new textures + Min/Max Roughness;
                   60 print decals: MID of their own v3 MI with OpacityGain 0.22;
                   grease decals: MID of the master with the print's atlas rect + grease params, shown;
                   variant lights: intensity + DiffuseScale set and read back, shown; band only for *_band variants.
                 Every change read back. Any exception -> restore in the same call -> FAILED.
  stills         PIE: refuses unless this pie's apply record is complete and the shown pool copies are present; arms
                 the shared scene_stills.py (Show Root transport scrub_to_master_frame) for S3 fraction 0.3 ONLY.
                 Async markers: PASSAGE_STILLS_OK|run=<stills run> / PASSAGE_STILLS_FAILED.
  restore        PIE: FIRST checks (root LANDED) that the shown pool copies are within 2 cm of the plan and that our
                 MIDs are still applied (else the still is invalid -> FAILED after restoring). Then restores the liner +
                 print materials from the originals file and HIDES the pool copies (lights 0 cd). No PIE spawn/destroy.
                 PIE already ended: nothing to restore (copies died with PIE): pie=gone.
  unspawn        EDITOR, PIE NOT running: destroys the editor-world ZZ_S3MG actors listed in the prespawn record (by
                 reference, EditorActorSubsystem.destroy_actor), verifies none left. Does NOT save; the map stays dirty
                 -> Don't-Save restart.
  census         EDITOR: liner slot 0 still MI_S3_Marble_Tiling_Daylight_R0; no ZZ_S3MG actor; report dirty packages.

COEXISTENCE with the S3 shore-ground bench (Saved/CodexConductor/S3Shore/s3_shore_ground_ue.py): its PIE bench now
BORROWS the PIE deck copy (tag ZZ_S3ShoreGroundBench; BEGIN_BENCH_PIE section ~720-1021: run_bench_pie_apply :856,
run_bench_pie_restore :953) and spawns nothing; its older editor-world run_bench is ~586-704. Our tag ZZ_S3MG and label
prefix ZZ_S3MG_ never match theirs (exact-match tags); separate files; our restore touches only our originals + our
tag; no census-equality gate in apply/restore (their dirt is not ours). We never touch S3 Hangar Deck / Beach V2 Sand.
Our prespawn must run BEFORE PIE starts and needs a CLEAN map; their PIE apply needs only a running PIE.

API names: each one is checked against UE 5.8 headers (D:/Unreal Engine/UE_5.8) and/or prior use in Saved/ scripts;
no generated stub exists. Table: Docs/Conductor/S3_MARBLE_GRIME_PREP_2026-10-07.md section 8. Markers carry run=<id>:
  S3MG_<STAGE>_START|run=  S3MG_<STAGE>_OK|run=  S3MG_FAILED|run=|stage=|reason=
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
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
LINER_NAME = "StaticMeshActor_350"                   # "S3 Marble Inner Wall Right" (s3_marble_tiling_record.json)
LINER_LABEL = "S3 Marble Inner Wall Right"
LINER_MI = "/Game/InfinityStage/Dev/Materials/MI_S3_Marble_Tiling_Daylight_R0"
ROOT_LABEL = "S3 Hangar Root"
ROOT_LANDED = {"loc": (11421.97275, 160000.0, -120.0), "rot": (0.0, 0.0, 0.0)}   # S3Shore/s3_shore_live_reads.json
#                                                    (measured live 7 Oct 18:16 by the shore stream: rot 0,0,0)
ASSET_DIR = "/Game/ZZ_Bench/S3MarbleGrime"
TEX_DIR = ASSET_DIR + "/Textures"
GREASE_MASTER = ASSET_DIR + "/M_ZZ_S3MG_GreaseDecal"
PRINT_NORMAL = "/Game/Scenes/Scene3/HandPrints/Textures/T_S03_HandPrints_Normal"
TAG = "ZZ_S3MG"
PREFIX = "ZZ_S3MG_"
POSE_TOL_CM = 2.0

TEXTURES = {   # source file -> (asset name, srgb, compression)
    "T_S3MG_Marble021_RoughGrime.png": ("T_S3MG_Marble021_RoughGrime", False, "TC_GRAYSCALE"),
    "T_S3MG_Marble021_NormalDX_Scratch.png": ("T_S3MG_Marble021_NormalDX_Scratch", False, "TC_NORMALMAP"),
    "T_S3MG_Marble021_Color_Grime_sRGB.png": ("T_S3MG_Marble021_Color_Grime", True, "TC_DEFAULT"),
    "T_S3MG_GreaseAtlas.png": ("T_S3MG_GreaseAtlas", False, "TC_MASKS"),
    "T_S3MG_GrimeBand.png": ("T_S3MG_GrimeBand", False, "TC_MASKS"),
    "T_S3MG_SeamStrip.png": ("T_S3MG_SeamStrip", False, "TC_MASKS"),
}
MARBLE_MID = {
    "textures": {"RoughnessTexture": "T_S3MG_Marble021_RoughGrime",
                 "NormalTexture": "T_S3MG_Marble021_NormalDX_Scratch",
                 "BaseColorTexture": "T_S3MG_Marble021_Color_Grime"},
    "scalars": {"Min Roughness": 0.04, "Max Roughness": 0.60, "RoughnessTextureWeight": 1.0},
}
PRINT_COLOUR_GAIN = 0.22
GREASE = {"GreaseGain": 1.0, "GreaseRoughMin": 0.30, "GreaseRoughRange": 0.25, "NormalStrength": 0.25}
BAND = {"GreaseGain": 0.85, "GreaseRoughMin": 0.20, "GreaseRoughRange": 0.50, "NormalStrength": 0.0}
VARIANTS = {   # C = Gary's pick (7 Oct)
    "C": {"marble": True, "prints": True, "band": False, "lights": {"intensity_cd": 4000.0, "diffuse_scale": 0.10}},
    "C_band": {"marble": True, "prints": True, "band": True, "lights": {"intensity_cd": 4000.0, "diffuse_scale": 0.10}},
    "C_phys": {"marble": True, "prints": True, "band": False, "lights": {"intensity_cd": 1500.0, "diffuse_scale": 1.0}},
    "A": {"marble": True, "prints": True, "band": False, "lights": None},
    "lights_only": {"marble": False, "prints": False, "band": False,
                    "lights": {"intensity_cd": 4000.0, "diffuse_scale": 0.10}},
}
STILLS = {"passage": "S3", "fractions": [0.3]}       # one still per fresh PIE (S3 scrubs refuse from inside S3)
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
MASTER_SCALARS = ATLAS_PARAMS + ("GreaseGain", "GreaseRoughMin", "GreaseRoughRange", "NormalStrength")


class BenchError(RuntimeError):
    pass


def require(cond, msg):
    if not cond:
        raise BenchError(msg)


def utc():
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def run_file(kind, run):
    return "%s/s3mg_%s_%s.json" % (HERE, kind, run)


def write_verified(path, data):
    text = json.dumps(data, indent=1, sort_keys=True, default=str)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    with open(path, encoding="utf-8") as f:
        require(f.read() == text, "READBACK|" + path)
    return path


# ------------------------------------------------------------------------------------------- plan (offline)
def _bhp():
    import importlib.util
    spec = importlib.util.spec_from_file_location("s3mg_bhp", ROOT + "/Tools/FlatV3/handprints/build_handprint_placement.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_plan():
    geo = json.load(open(GEOMETRY))
    wall_y = geo["wall"]["plane_y_cm"]
    fx = sorted([geo["frame_on_wall"]["tl"]["wall_xz"][0], geo["frame_on_wall"]["tr"]["wall_xz"][0]])
    m = _bhp()
    x, y, z = m.decal_axes([0.0, -1.0, 0.0], 0.0)          # R wall, image upright
    band_len = (fx[1] - fx[0]) + 300.0
    # anchor = the in-frame print decal nearest the band centre (same wall => same hinge)
    cx = (fx[0] + fx[1]) / 2
    anchor = min(geo["decals"], key=lambda d: abs(d["loc"][0] - cx))
    placement = {d["label"]: d for d in json.load(open(ROOT + "/DerivedAssets/FlatV3/HandPrints/placement_S03.json"))["decals"]}
    band = {"name": PREFIX + "Band", "location": [round(cx, 1), wall_y, 95.0], "x": x, "z": z,
            "decal_size": [8.0, 100.0, round(band_len / 2, 1)],
            "atlas": {"AtlasU0": 0.0, "AtlasV0": 0.0, "AtlasUSize": round(band_len / 800.0, 4), "AtlasVSize": 1.0,
                      "FlipU": 0.0, "GlobalFlipU": 0.0, "GlobalFlipV": 0.0},
            "texture": "T_S3MG_GrimeBand", "params": BAND,
            "anchor": {"label": anchor["label"], "landed_loc": anchor["loc"],
                       "landed_rot": placement[anchor["label"]]["rotation"],
                       "attach_parent_label": placement[anchor["label"]]["attach_actor_label"]}}
    lights = []
    for st in geo["mirror_light"]["strips_proposal"]:
        lights.append({"name": st["name"], "location": st["location_cm"], "x": [0.0, 1.0, 0.0], "z": [0.0, 0.0, 1.0],
                       "source_width": st["source_width_cm"], "source_height": st["source_height_cm"],
                       "barn_door_angle": 20.0, "barn_door_length": 40.0, "attenuation_radius": 3500.0,
                       "reflects_at_wall_cm": st["reflects_at_wall_cm"]})
    plan = {"tool": "s3mg_bench.py plan v2", "world": WORLD, "camera": geo["main_pose"], "root_landed": ROOT_LANDED,
            "liner": {"name": LINER_NAME, "label": LINER_LABEL, "mi": LINER_MI, "mid": MARBLE_MID},
            "prints": {"labels": sorted(d["label"] for d in geo["decals"]), "count": len(geo["decals"]),
                       "colour_gain": PRINT_COLOUR_GAIN, "grease": GREASE},
            "band": band, "lights": lights, "variants": VARIANTS, "stills": STILLS}
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


def editor_sub():
    u = _u()
    return u.get_editor_subsystem(u.UnrealEditorSubsystem)


def editor_world():
    w = editor_sub().get_editor_world()
    require(w is not None and WORLD in w.get_path_name(), "EDITOR_WORLD|%s" % (w and w.get_path_name()))
    return w


def pie_world_or_none():
    return editor_sub().get_game_world()


def pie_world():
    w = pie_world_or_none()
    require(w is not None, "NO_PIE_WORLD")
    return w


def actors(world, cls=None):
    u = _u()
    return list(u.GameplayStatics.get_all_actors_of_class(world, cls or u.Actor))


def by_label(world, cls=None):
    out = {}
    for a in actors(world, cls):
        out.setdefault(str(a.get_actor_label()), []).append(a)
    return out


def one(table, label):
    rows = table.get(label, [])
    require(len(rows) == 1, "LABEL_COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def find_by_name(world, name):
    hits = [a for a in actors(world) if a.get_name() == name]
    require(len(hits) == 1, "FIND|%s|n=%d" % (name, len(hits)))
    return hits[0]


def tagged(world):
    return [a for a in actors(world) if TAG in [str(t) for t in a.tags]]


def path(o):
    return o.get_path_name() if o is not None else None


def decal_comp(actor):
    return actor.get_editor_property("decal")       # ADecalActor::Decal is private (DecalActor.h:29-30)


def vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def rigid(u, actor):
    """Scale-free world pose of an actor (anchors may carry scale; we map rigid poses only)."""
    return u.Transform(actor.get_actor_location(), actor.get_actor_rotation(), u.Vector(1.0, 1.0, 1.0))


def landed_to_now(u, anchor_landed, anchor_now, loc, x_axis, z_axis):
    """Map a LANDED-world pose through the anchor's landed->current rigid motion (exact for rigidly attached things)."""
    ml = u.MathLibrary
    local = ml.inverse_transform_location(anchor_landed, u.Vector(*loc))
    lx = ml.inverse_transform_direction(anchor_landed, u.Vector(*x_axis))
    lz = ml.inverse_transform_direction(anchor_landed, u.Vector(*z_axis))
    p = ml.transform_location(anchor_now, local)
    r = ml.make_rot_from_xz(ml.transform_direction(anchor_now, lx), ml.transform_direction(anchor_now, lz))
    return p, r


def attach(u, child, parent, rule):
    r = getattr(u.AttachmentRule, rule)
    child.attach_to_actor(parent, u.Name("None"), r, r, r, False)
    require(child.get_attach_parent_actor() == parent, "ATTACH|%s" % child.get_name())


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


def texture_state(asset):
    u = _u()
    tex = u.EditorAssetLibrary.load_asset(TEX_DIR + "/" + asset)
    if tex is None:
        return None
    return {"class": tex.get_class().get_name(), "srgb": bool(tex.get_editor_property("srgb")),
            "compression": str(tex.get_editor_property("compression_settings")),
            "size": [int(tex.blueprint_get_size_x()), int(tex.blueprint_get_size_y())]}


def texture_ok(st, srgb, comp):
    # a texture still compiling reports the 32x32 placeholder (s3_marble_tiling_material.py:129)
    return (st is not None and st["class"] == "Texture2D" and st["srgb"] == srgb and comp in st["compression"]
            and (max(st["size"]) <= 2048))


def master_state():
    u = _u()
    m = u.EditorAssetLibrary.load_asset(GREASE_MASTER)
    if m is None:
        return None
    return {"domain": str(m.get_editor_property("material_domain")), "blend": str(m.get_editor_property("blend_mode")),
            "scalars": sorted(str(n) for n in u.MaterialEditingLibrary.get_scalar_parameter_names(m)),
            "textures": sorted(str(n) for n in u.MaterialEditingLibrary.get_texture_parameter_names(m))}


def master_ok(st):
    return (st is not None and "DEFERRED_DECAL" in st["domain"] and "TRANSLUCENT" in st["blend"]
            and sorted(MASTER_SCALARS) == st["scalars"] and st["textures"] == ["GreaseMask", "PrintNormal"])


def import_textures():
    u = _u()
    eal = u.EditorAssetLibrary
    tasks = []
    for fname, (asset, _s, _c) in TEXTURES.items():
        require(os.path.isfile(SRC + "/" + fname), "SOURCE_MISSING|" + fname)
        t = u.AssetImportTask()
        for k, v in (("filename", SRC + "/" + fname), ("destination_path", TEX_DIR), ("destination_name", asset),
                     ("automated", True), ("replace_existing", False), ("save", False)):
            t.set_editor_property(k, v)
        tasks.append(t)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    out = {}
    for fname, (asset, srgb, comp) in TEXTURES.items():
        tex = eal.load_asset(TEX_DIR + "/" + asset)
        require(isinstance(tex, u.Texture2D), "IMPORT_FAILED|" + asset)
        tex.modify()
        tex.set_editor_property("compression_settings", getattr(u.TextureCompressionSettings, comp))
        tex.set_editor_property("srgb", srgb)
        if comp == "TC_NORMALMAP":
            tex.set_editor_property("flip_green_channel", False)
        st = texture_state(asset)
        require(texture_ok(st, srgb, comp), "TEX_SETTINGS|%s|%s" % (asset, st))
        out[asset] = st
    return out


def build_grease_master():
    u = _u()
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
    defaults = dict(zip(ATLAS_PARAMS, (0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 0.0)), **GREASE)
    p = {n: g.scalar(n, defaults[n], -1800, 120 + 90 * i) for i, n in enumerate(MASTER_SCALARS)}
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
    g.prop(nn, "", MP.MP_NORMAL)              # deliberately NO MP_BASE_COLOR
    u.MaterialEditingLibrary.layout_material_expressions(mat)
    errs = [str(e) for e in (u.MaterialEditingLibrary.recompile_material(mat) or [])]
    require(not errs, "MASTER_COMPILE|" + json.dumps(errs[:6]))
    st = master_state()
    require(master_ok(st), "MASTER_READBACK|%s" % st)
    return st


def stage_assets(run, args):
    u = _u()
    require(pie_world_or_none() is None, "PIE_RUNNING|assets stage runs in the editor only")
    editor_world()
    marker = "S3MG_ASSETS_START|run=%s" % run
    u.log(marker)
    rec = {"run": run, "start_marker": marker, "census_before": census()}
    tex_states = {a: texture_state(a) for a, _s, _c in TEXTURES.values()}
    mst = master_state()
    present = [a for a, s in tex_states.items() if s is not None] + (["MASTER"] if mst is not None else [])
    if len(present) == len(TEXTURES) + 1:
        bad = [a for f, (a, s, c) in TEXTURES.items() if not texture_ok(tex_states[a], s, c)]
        require(not bad and master_ok(mst), "REUSE_MISMATCH|tex=%s|master_ok=%s" % (bad, master_ok(mst)))
        rec.update(mode="REUSED", textures=tex_states, master=mst)
    elif not present:
        write_verified(run_file("assets", run), dict(rec, mode="CREATING"))
        rec["textures"] = import_textures()
        u.SystemLibrary.collect_garbage()
        rec["master"] = build_grease_master()
        u.SystemLibrary.collect_garbage()
        rec["mode"] = "CREATED"
    else:
        raise BenchError("PARTIAL_ASSETS|%s|fix: Don't-Save restart, then rerun" % present)
    rec["saved"] = False
    rec["census_after"] = census()
    write_verified(run_file("assets", run), rec)
    return "mode=%s|unsaved=1" % rec["mode"]


def stage_verify_assets(run, args):
    u = _u()
    rec = json.load(open(run_file("assets", run)))
    require(rec["run"] == run and rec.get("mode") in ("CREATED", "REUSED"), "ASSETS_NOT_DONE|%s" % rec.get("mode"))
    with open(ROOT + "/Saved/Logs/PussStage.log", encoding="utf-8", errors="replace") as f:
        log = f.read()
    i = log.rfind(rec["start_marker"])
    require(i >= 0, "START_MARKER_NOT_IN_LOG")
    bad = [ln for ln in log[i:].splitlines() if "M_ZZ_S3MG_GreaseDecal" in ln and
           ("Failed to compile" in ln or "Default Material will be used" in ln)]
    require(not bad, "MASTER_COMPILE_LOG|" + json.dumps(bad[:4]))
    m = u.EditorAssetLibrary.load_asset(GREASE_MASTER)
    ps = int(u.MaterialEditingLibrary.get_statistics(m).get_editor_property("num_pixel_shader_instructions"))
    require(ps > 0, "PENDING_COMPILE|rerun verify_assets in ~30 s")
    for f, (a, s, c) in TEXTURES.items():
        st = texture_state(a)
        require(texture_ok(st, s, c) and st["size"] != [32, 32], "TEX_RECHECK|%s|%s" % (a, st))
    rec["verified"] = {"ps": ps}
    write_verified(run_file("assets", run), rec)
    write_verified(HERE + "/s3mg_assets_last.json", rec)
    return "ps=%d" % ps


# ------------------------------------------------------------------------------------------- pool plan (shared)
def pool_specs(plan):
    """Every editor-world pool actor any variant can need (band always spawned, shown only by *_band variants)."""
    specs = []
    for i, L in enumerate(plan["lights"]):
        specs.append({"label": "%sStrip_%d" % (PREFIX, i), "kind": "light", "plan": L})
    for lab in plan["prints"]["labels"]:
        specs.append({"label": PREFIX + "Grease_" + lab.replace(" ", "_"), "kind": "grease", "print": lab})
    specs.append({"label": PREFIX + "Band", "kind": "band", "plan": plan["band"]})
    return specs


def pool_map(world):
    out = {}
    for a in tagged(world):
        lab = str(a.get_actor_label())
        require(lab not in out, "POOL_DUPLICATE|" + lab)
        out[lab] = a
    return out


def comp_of(actor):
    u = _u()
    if isinstance(actor, u.RectLight):
        return actor.get_editor_property("rect_light_component")
    return decal_comp(actor)


def is_shown(actor):
    """USceneComponent::IsVisible (UFUNCTION) on the pool actor's main component; AActor::IsHidden is not a UFUNCTION."""
    return bool(comp_of(actor).is_visible())


def show(actor, comp, on):
    comp.set_visibility(bool(on), True)
    actor.set_actor_hidden_in_game(not on)


def own_content_dirt(c):
    return [p for p in c["content"] if not p.startswith(ASSET_DIR)]


# ------------------------------------------------------------------------------------------- stage: prespawn (EDITOR)
def stage_prespawn(run, args):
    u = _u()
    require(pie_world_or_none() is None, "PIE_RUNNING|prespawn runs in the editor world before PIE")
    world = editor_world()
    c0 = census()
    require(not c0["maps"], "MAP_ALREADY_DIRTY|%s|a Don't-Save restart would discard it; save/settle first" % c0["maps"])
    require(not own_content_dirt(c0), "FOREIGN_DIRTY_CONTENT|%s" % own_content_dirt(c0)[:6])
    require(not tagged(world), "POOL_EXISTS|%s|run unspawn (or Don't-Save restart) first"
            % [str(a.get_actor_label()) for a in tagged(world)][:6])
    require(not os.path.isfile(run_file("prespawn", run)), "RUN_ALREADY_PRESPAWNED|use a new run id")
    last = HERE + "/s3mg_assets_last.json"
    arec = json.load(open(last)) if os.path.isfile(last) else {}
    require(arec.get("verified"), "ASSETS_NOT_VERIFIED|run assets + verify_assets in this editor session")
    require(master_ok(master_state()), "ASSETS_GONE|master")
    plan = json.load(open(PLAN))
    labels_tbl = by_label(world)
    root = one(labels_tbl, ROOT_LABEL)
    rl, rr = vec(root.get_actor_location()), root.get_actor_rotation()
    require(max(abs(a - b) for a, b in zip(rl, ROOT_LANDED["loc"])) <= 1.0
            and max(abs(rr.roll), abs(rr.pitch), abs(rr.yaw)) <= 0.01,
            "ROOT_NOT_LANDED|%s|%s" % (rl, (rr.roll, rr.pitch, rr.yaw)))
    dtbl = by_label(world, u.DecalActor)
    specs = pool_specs(plan)
    rec = {"run": run, "world": world.get_path_name(), "census_before": c0, "labels": [s["label"] for s in specs],
           "spawned": [], "complete": False}
    write_verified(run_file("prespawn", run), rec)                 # labels on disk BEFORE the first spawn
    u.log("S3MG_PRESPAWN_RECORD|run=%s|path=%s|n=%d" % (run, run_file("prespawn", run), len(specs)))
    actor_sub = u.get_editor_subsystem(u.EditorActorSubsystem)
    gm = u.EditorAssetLibrary.load_asset(GREASE_MASTER)
    spawned = []

    def spawn(cls, label, loc, rot):
        a = actor_sub.spawn_actor_from_class(cls, loc, rot)
        require(a is not None, "SPAWN_FAILED|" + label)
        spawned.append(a)
        rec["spawned"].append({"label": label, "path": a.get_path_name()})
        require(a.get_world() == world, "SPAWN_NOT_IN_EDITOR_WORLD|" + label)
        a.set_actor_label(label, False)
        a.set_editor_property("tags", [u.Name(TAG)])
        a.set_actor_enable_collision(False)
        a.get_editor_property("root_component").set_mobility(u.ComponentMobility.MOVABLE)
        return a

    try:
        for s in specs:
            if s["kind"] == "light":
                L = s["plan"]
                a = spawn(u.RectLight, s["label"], u.Vector(*L["location"]),
                          u.MathLibrary.make_rot_from_xz(u.Vector(*L["x"]), u.Vector(*L["z"])))
                c = a.get_editor_property("rect_light_component")
                c.set_mobility(u.ComponentMobility.MOVABLE)
                c.set_intensity_units(u.LightUnits.CANDELAS)
                c.set_intensity(0.0)
                c.set_source_width(L["source_width"])
                c.set_source_height(L["source_height"])
                c.set_barn_door_angle(L["barn_door_angle"])
                c.set_barn_door_length(L["barn_door_length"])
                c.set_attenuation_radius(L["attenuation_radius"])
                c.set_specular_scale(1.0)
                c.set_cast_shadows(False)
                attach(u, a, root, "KEEP_WORLD")
                show(a, c, False)
                want = L["location"]
            elif s["kind"] == "grease":
                p = one(dtbl, s["print"])
                pdc = decal_comp(p)
                a = spawn(u.DecalActor, s["label"], p.get_actor_location(), p.get_actor_rotation())
                attach(u, a, p, "SNAP_TO_TARGET")
                c = decal_comp(a)
                c.set_editor_property("decal_size", pdc.get_editor_property("decal_size"))
                c.set_sort_order(int(pdc.get_editor_property("sort_order")) + 1)
                c.set_decal_material(gm)
                require(c.get_decal_material() == gm, "GREASE_MATERIAL|" + s["label"])
                show(a, c, False)
                want = vec(p.get_actor_location())
            else:
                b = s["plan"]
                anc = one(dtbl, b["anchor"]["label"])
                wall = anc.get_attach_parent_actor()
                require(wall is not None and str(wall.get_actor_label()) == b["anchor"]["attach_parent_label"],
                        "BAND_WALL|%s" % (wall and wall.get_actor_label()))
                a = spawn(u.DecalActor, s["label"], u.Vector(*b["location"]),
                          u.MathLibrary.make_rot_from_xz(u.Vector(*b["x"]), u.Vector(*b["z"])))
                attach(u, a, wall, "KEEP_WORLD")
                c = decal_comp(a)
                c.set_editor_property("decal_size", u.Vector(*b["decal_size"]))
                c.set_decal_material(gm)
                show(a, c, False)
                want = b["location"]
            got = vec(a.get_actor_location())
            require(max(abs(x - y) for x, y in zip(got, want)) <= 1.0, "SPAWN_POSE|%s|%s|%s" % (s["label"], got, want))
        require(len(pool_map(world)) == len(specs), "POOL_COUNT|%d/%d" % (len(pool_map(world)), len(specs)))
        rec["complete"] = True
        rec["census_after"] = census()
        write_verified(run_file("prespawn", run), rec)
        return "pool=%d|hidden|map_dirty_expected|NEEDS_DONT_SAVE_RESTART" % len(specs)
    except Exception:
        rec["error"] = traceback.format_exc()
        for a in reversed(spawned):                                 # this call's spawns, by reference
            try:
                actor_sub.destroy_actor(a)
            except Exception:
                pass
        rec["destroyed_after_error"] = len(spawned)
        write_verified(run_file("prespawn", run), rec)
        raise


# ---- PIE BEGIN (apply / stills / restore: no spawn, no destroy, no editor-actor API in this region) ----
def stage_apply(run, args):
    u = _u()
    variant = args.get("variant", "C")
    require(variant in VARIANTS, "VARIANT|%s" % variant)
    v = VARIANTS[variant]
    pid = "%s-p%d" % (run, int(args.get("pie", 1)))
    pre = json.load(open(run_file("prespawn", run))) if os.path.isfile(run_file("prespawn", run)) else {}
    require(pre.get("complete"), "NOT_PRESPAWNED|run prespawn (editor, before PIE) for this run")
    require(not os.path.isfile(run_file("originals", pid)), "PIE_ALREADY_APPLIED|bump args.pie for a fresh PIE")
    plan = json.load(open(PLAN))
    world = pie_world()
    require(world.get_path_name() != pre["world"], "GAME_WORLD_IS_EDITOR_WORLD")
    mel = u.MaterialEditingLibrary
    pool = pool_map(world)
    missing = [l for l in pre["labels"] if l not in pool]
    require(not missing, "POOL_COPY_MISSING|%s|was PIE started after prespawn?" % missing[:5])
    liner = find_by_name(world, LINER_NAME)
    require(str(liner.get_actor_label()) == LINER_LABEL, "LINER_LABEL|%s" % liner.get_actor_label())
    smc = liner.static_mesh_component
    dtbl = by_label(world, u.DecalActor)
    decals = {lab: one(dtbl, lab) for lab in plan["prints"]["labels"]}
    root = one(by_label(world), ROOT_LABEL)
    specs = pool_specs(plan)
    # ---- ORIGINALS FIRST
    orig = {"run": run, "pie": pid, "variant": variant, "world": world.get_path_name(), "utc": utc(), "census": census(),
            "liner": {"name": liner.get_name(), "slot0": path(smc.get_material(0))},
            "decals": {lab: {"name": a.get_name(), "material": path(decal_comp(a).get_decal_material())}
                       for lab, a in sorted(decals.items())},
            "pool": {}}
    for s in specs:
        a = pool[s["label"]]
        orig["pool"][s["label"]] = {"shown": is_shown(a)}
    require(orig["liner"]["slot0"] and orig["liner"]["slot0"].split(".")[0] == LINER_MI,
            "LINER_NOT_R0|%s" % orig["liner"]["slot0"])
    shown = [l for l, r in orig["pool"].items() if r["shown"]]
    require(not shown, "POOL_ALREADY_SHOWN|%s" % shown[:5])
    write_verified(run_file("originals", pid), orig)
    u.log("S3MG_BENCH_ORIGINALS|run=%s|pie=%s|path=%s" % (run, pid, run_file("originals", pid)))
    applied = {"run": run, "pie": pid, "variant": variant, "shown": [], "mids": [], "positions": {}, "complete": False}
    try:
        # positions of the PIE copies for the CURRENT hangar pose (PIE may start un-landed)
        root_landed = u.Transform(u.Vector(*ROOT_LANDED["loc"]), u.Rotator(roll=0.0, pitch=0.0, yaw=0.0),
                                  u.Vector(1, 1, 1))
        for s in specs:
            a = pool[s["label"]]
            if s["kind"] == "light":
                want, _r = landed_to_now(u, root_landed, rigid(u, root), s["plan"]["location"], s["plan"]["x"],
                                         s["plan"]["z"])
                want = vec(want)
            elif s["kind"] == "grease":
                p = decals[s["print"]]
                require(a.get_attach_parent_actor() == p, "GREASE_PARENT|" + s["label"])
                want = vec(p.get_actor_location())
            else:
                b = s["plan"]
                anc = one(dtbl, b["anchor"]["label"])
                r = b["anchor"]["landed_rot"]
                al = u.Transform(u.Vector(*b["anchor"]["landed_loc"]),
                                 u.Rotator(roll=r["roll"], pitch=r["pitch"], yaw=r["yaw"]), u.Vector(1, 1, 1))
                want, _r = landed_to_now(u, al, rigid(u, anc), b["location"], b["x"], b["z"])
                want = vec(want)
            got = vec(a.get_actor_location())
            err = max(abs(x - y) for x, y in zip(got, want))
            applied["positions"][s["label"]] = round(err, 3)
            require(err <= POSE_TOL_CM, "POOL_COPY_POSE|%s|err=%.2f cm" % (s["label"], err))
        if v["marble"]:
            mid = smc.create_dynamic_material_instance(0, smc.get_material(0))
            for pname, asset in MARBLE_MID["textures"].items():
                tex = u.EditorAssetLibrary.load_asset(TEX_DIR + "/" + asset)
                require(tex is not None, "BENCH_TEXTURE_MISSING|" + asset)
                mid.set_texture_parameter_value(pname, tex)
                require(path(mid.get_texture_parameter_value(pname)) == path(tex), "MID_TEX|" + pname)
            for k, val in MARBLE_MID["scalars"].items():
                mid.set_scalar_parameter_value(k, val)
                require(abs(mid.get_scalar_parameter_value(k) - val) < 1e-5, "MID_SCALAR|" + k)
            require(smc.get_material(0) == mid, "LINER_MID_NOT_APPLIED")
            applied["mids"].append(LINER_NAME)
        for s in specs:
            a = pool[s["label"]]
            if s["kind"] == "grease" and v["prints"]:
                p = decals[s["print"]]
                pdc = decal_comp(p)
                src_mi = pdc.get_decal_material()
                atlas = {k: float(mel.get_material_instance_scalar_parameter_value(src_mi, k)) for k in ATLAS_PARAMS}
                cmid = pdc.create_dynamic_material_instance()
                cmid.set_scalar_parameter_value("OpacityGain", PRINT_COLOUR_GAIN)
                require(abs(cmid.get_scalar_parameter_value("OpacityGain") - PRINT_COLOUR_GAIN) < 1e-5,
                        "GAIN|" + s["print"])
                applied["mids"].append(s["print"])
                gdc = decal_comp(a)
                gmid = gdc.create_dynamic_material_instance()       # parent = the grease master set at prespawn
                for k, val in list(atlas.items()) + list(GREASE.items()):
                    gmid.set_scalar_parameter_value(k, val)
                    require(abs(gmid.get_scalar_parameter_value(k) - val) < 1e-5, "GREASE_PARAM|%s|%s" % (s["label"], k))
                require(gdc.get_decal_material() == gmid, "GREASE_MID|" + s["label"])
                show(a, gdc, True)
                applied["shown"].append(s["label"])
            elif s["kind"] == "band" and v["band"]:
                b = s["plan"]
                gdc = decal_comp(a)
                bmid = gdc.create_dynamic_material_instance()
                for k, val in list(b["atlas"].items()) + list(b["params"].items()):
                    bmid.set_scalar_parameter_value(k, val)
                band_tex = u.EditorAssetLibrary.load_asset(TEX_DIR + "/" + b["texture"])
                bmid.set_texture_parameter_value("GreaseMask", band_tex)
                require(path(bmid.get_texture_parameter_value("GreaseMask")) == path(band_tex), "BAND_TEX")
                show(a, gdc, True)
                applied["shown"].append(s["label"])
            elif s["kind"] == "light" and v["lights"]:
                c = a.get_editor_property("rect_light_component")
                c.set_intensity(v["lights"]["intensity_cd"])
                c.set_diffuse_scale(v["lights"]["diffuse_scale"])
                show(a, c, True)
                L = s["plan"]
                got = {"units": str(c.get_editor_property("intensity_units")),
                       "intensity": float(c.get_editor_property("intensity")),
                       "w": float(c.get_editor_property("source_width")), "h": float(c.get_editor_property("source_height")),
                       "diffuse_scale": float(c.get_editor_property("diffuse_scale"))}
                require("CANDELAS" in got["units"] and abs(got["intensity"] - v["lights"]["intensity_cd"]) < 1e-3
                        and abs(got["w"] - L["source_width"]) < 1e-3 and abs(got["h"] - L["source_height"]) < 1e-3
                        and abs(got["diffuse_scale"] - v["lights"]["diffuse_scale"]) < 1e-5, "LIGHT_READBACK|%s" % got)
                applied["shown"].append(s["label"])
                applied.setdefault("lights", []).append(dict(got, label=s["label"]))
        applied["census_after"] = census()
        applied["complete"] = True
        write_verified(run_file("applied", pid), applied)
        return "pie=%s|variant=%s|shown=%d|mids=%d|max_pose_err_cm=%.2f" % (
            pid, variant, len(applied["shown"]), len(applied["mids"]), max(applied["positions"].values()))
    except Exception:
        applied["error"] = traceback.format_exc()
        write_verified(run_file("applied", pid), applied)
        try:
            stage_restore(run, args, check_pose=False)
        except Exception:
            u.log_error("S3MG_FAILED|run=%s|stage=apply|reason=restore_after_error|%s" % (
                run, traceback.format_exc().replace("\n", " | ")))
        raise


def stage_stills(run, args):
    pid = "%s-p%d" % (run, int(args.get("pie", 1)))
    applied = json.load(open(run_file("applied", pid)))
    require(applied.get("complete"), "APPLY_NOT_COMPLETE|" + pid)
    world = pie_world()
    pool = pool_map(world)
    missing = [l for l in applied["shown"] if l not in pool or not is_shown(pool[l])]
    require(not missing, "SHOWN_POOL_MISSING_OR_HIDDEN|%s" % missing[:5])
    import runpy
    label = "s3mg_%s" % pid.split("-", 1)[-1]
    runpy.run_path(ROOT + "/Saved/CodexConductor/scene_stills.py", init_globals={
        "STILLS_PASSAGE": STILLS["passage"], "STILLS_FRACTIONS": list(STILLS["fractions"]),
        "STILLS_LABEL": label, "STILLS_PARAMS": {}})
    return "armed|pie=%s|label=%s|watch=PASSAGE_STILLS_OK" % (pid, label)


def pose_check(u, world, pid):
    """Before restoring: did the still show what we set? Pose verdict only if the hangar root is LANDED now."""
    plan = json.load(open(PLAN))
    applied = json.load(open(run_file("applied", pid)))
    root = one(by_label(world), ROOT_LABEL)
    rl = vec(root.get_actor_location())
    landed = max(abs(a - b) for a, b in zip(rl, ROOT_LANDED["loc"])) <= 1.0
    out = {"root_now": rl, "root_landed": landed, "poses": {}}
    held = []
    if LINER_NAME in applied.get("mids", []):
        m = find_by_name(world, LINER_NAME).static_mesh_component.get_material(0)
        held.append(("liner", isinstance(m, u.MaterialInstanceDynamic)))
    dtbl = by_label(world, u.DecalActor)
    for lab in [x for x in applied.get("mids", []) if x != LINER_NAME]:
        rows = dtbl.get(lab, [])
        held.append((lab, len(rows) == 1 and isinstance(decal_comp(rows[0]).get_decal_material(),
                                                        u.MaterialInstanceDynamic)))
    pool = pool_map(world)
    for lab in applied.get("shown", []):
        held.append((lab, lab in pool and is_shown(pool[lab])))
    lost = [k for k, ok in held if not ok]
    out["held"] = {"checked": len(held), "lost": lost[:10]}
    if lost:
        out["verdict"] = "POSE_MISMATCH|lost=%d" % len(lost)
        return out
    if not landed:
        out["verdict"] = "ROOT_NOT_LANDED"
        return out
    want = {s["label"]: s["plan"]["location"] for s in pool_specs(plan) if s["kind"] in ("light", "band")}
    errs = []
    for lab in applied.get("shown", []):
        if lab in want:
            d = max(abs(x - y) for x, y in zip(vec(pool[lab].get_actor_location()), want[lab]))
            out["poses"][lab] = round(d, 2)
            if d > POSE_TOL_CM:
                errs.append(lab)
    out["verdict"] = "POSE_OK" if not errs else "POSE_MISMATCH|%s" % errs
    return out


def stage_restore(run, args, check_pose=True):
    u = _u()
    pid = "%s-p%d" % (run, int(args.get("pie", 1)))
    orig = json.load(open(run_file("originals", pid)))
    require(orig["pie"] == pid, "RUN_MISMATCH|%s" % orig["pie"])
    world = pie_world_or_none()
    if world is None or world.get_path_name() != orig["world"]:
        write_verified(run_file("restored", pid), {"pie": pid, "state": "pie=gone", "census": census()})
        return "pie=gone|nothing to restore (PIE copies died with PIE)"
    rec = {"pie": pid, "state": "pie=live"}
    if check_pose:
        rec["pose"] = pose_check(u, world, pid)
        write_verified(run_file("restored", pid), rec)            # evidence on disk before restoring
    liner = find_by_name(world, LINER_NAME)
    smc = liner.static_mesh_component
    smc.set_material(0, u.EditorAssetLibrary.load_asset(orig["liner"]["slot0"].split(".")[0]))
    problems = []
    if path(smc.get_material(0)) != orig["liner"]["slot0"]:
        problems.append("LINER|%s" % path(smc.get_material(0)))
    dtbl = by_label(world, u.DecalActor)
    for lab, row in orig["decals"].items():
        rows = dtbl.get(lab, [])
        if len(rows) != 1:
            problems.append("DECAL_COUNT|%s|%d" % (lab, len(rows)))
            continue
        dc = decal_comp(rows[0])
        dc.set_decal_material(u.EditorAssetLibrary.load_asset(row["material"].split(".")[0]))
        if path(dc.get_decal_material()) != row["material"]:
            problems.append("DECAL|" + lab)
    pool = pool_map(world)
    for lab in orig["pool"]:
        a = pool.get(lab)
        if a is None:
            problems.append("POOL_GONE|" + lab)
            continue
        if isinstance(a, u.RectLight):
            c = a.get_editor_property("rect_light_component")
            c.set_intensity(0.0)
        else:
            c = decal_comp(a)
        show(a, c, False)
        if is_shown(a):
            problems.append("POOL_STILL_SHOWN|" + lab)
    rec.update(problems=problems, census=census())
    write_verified(run_file("restored", pid), rec)
    require(not problems, "RESTORE|" + json.dumps(problems[:10]))
    verdict = rec.get("pose", {}).get("verdict", "unchecked")
    require(not verdict.startswith("POSE_MISMATCH"), "RESTORED_BUT_STILL_INVALID|" + verdict)
    return "pie=%s|hidden=%d|pose=%s" % (pid, len(orig["pool"]), verdict)
# ---- PIE END ----


# ------------------------------------------------------------------------------------------- stage: unspawn (EDITOR)
def stage_unspawn(run, args):
    u = _u()
    require(pie_world_or_none() is None, "PIE_RUNNING|unspawn after PIE has ended")
    world = editor_world()
    pre = json.load(open(run_file("prespawn", run)))
    actor_sub = u.get_editor_subsystem(u.EditorActorSubsystem)
    pool = pool_map(world)
    listed = {r["label"] for r in pre.get("spawned", [])}
    stray = sorted(set(pool) - listed)
    require(not stray, "UNLISTED_ZZ_S3MG_ACTORS|%s|not ours to delete" % stray[:5])
    destroyed = []
    for lab in sorted(listed):
        a = pool.get(lab)
        if a is None:
            continue
        require(actor_sub.destroy_actor(a), "DESTROY_FAILED|" + lab)
        destroyed.append(lab)
    left = [str(a.get_actor_label()) for a in tagged(world)]
    require(not left, "POOL_LEFT|%s" % left[:5])
    pre["unspawned"] = {"destroyed": len(destroyed), "census": census()}
    write_verified(run_file("prespawn", run), pre)
    return "destroyed=%d|not_saved|NEEDS_DONT_SAVE_RESTART" % len(destroyed)


def stage_census(run, args):
    w = editor_world()
    liner = find_by_name(w, LINER_NAME)
    slot0 = path(liner.static_mesh_component.get_material(0))
    require(slot0 and slot0.split(".")[0] == LINER_MI, "EDITOR_LINER_CHANGED|%s" % slot0)
    zz = [str(a.get_actor_label()) for a in tagged(w)]
    require(not zz, "EDITOR_HAS_BENCH_ACTORS|%s" % zz[:5])
    return "editor_clean_of_bench|dirty=%s" % json.dumps(census())


STAGES = {"assets": stage_assets, "verify_assets": stage_verify_assets, "prespawn": stage_prespawn,
          "apply": stage_apply, "stills": stage_stills, "restore": stage_restore, "unspawn": stage_unspawn,
          "census": stage_census}


def run_stage(stage, run, args):
    """Called by s3mg_run.py inside Unreal. Returns the OK detail or raises."""
    require(stage in STAGES, "STAGE|%s" % stage)
    return STAGES[stage](run, args)


if __name__ == "__main__":         # offline: python s3mg_bench.py  -> plan only
    p = make_plan()
    print(json.dumps({"plan": PLAN, "prints": p["prints"]["count"], "lights": len(p["lights"]),
                      "band_anchor": p["band"]["anchor"]["label"], "pool": len(pool_specs(p))}))
