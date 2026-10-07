"""S3 shore ground -- editor-side DRY / IMPORT / BUILD_MAT / BENCH / APPLY / REVERT / VERIFY.

DRAFT, written 7 Oct 2026 OFFLINE.  DRY/IMPORT/BUILD_MAT/BENCH_PIE were run 7 Oct; APPLY/REVERT written offline, NOT RUN.
Plan + live reads: Docs/Conductor/S3_SHORE_GROUND_PREP_2026-10-07.md (sections 4-5).

Args Saved/CodexConductor/S3Shore/s3_shore_ground_args.json:
  {"mode": "DRY"|"IMPORT"|"BUILD_MAT"|"BENCH"|"APPLY"|"REVERT"|"VERIFY",
   "confirm": "<MODE> S3SHORE", "run": "<id>",
   "mesh_name": "SM_S3_ShoreGround_B" (IMPORT, APPLY), "mi": "<MI path>" (APPLY), "reveal": "mirror_deck"|"none"}

Modes (write modes need the confirm string and refuse on a dirty editor):
  DRY        read-only.  Writes s3_shore_live_reads.json: root transform (asserts LANDED == footprint +-1 cm),
             deck / walls / backdrop / door / wave rows / figures / pedestal / props / every CineCameraActor whose
             label starts "S3 " or "Scene 3" (+ attach parents, mobility, world AABBs), and the FBX/manifest
             hashes.  Offline, footprint_from_live_reads() turns it into s3_shore_footprint.json; rebuild the mesh.
  IMPORT     one FBX -> /Game/InfinityStage/Dev/Generated/S3Shore/SM_S3_ShoreGround (Interchange override:
             static mesh only, NO materials/textures, Nanite ON, vertex colours REPLACE, no LODs).  Gates before
             save: 1 LOD, nanite enabled, bounds == manifest (Y mirror gate), no stray assets (folder diff),
             calibration vertex colours read (records the byte encoding), only this package dirty.
  BUILD_MAT  create-only M_S3_ShoreGround (opaque, Nanite) + MI_S3_ShoreGround.  Graph in graph_spec().  Never edits
             an existing asset (memory ue58-python-material-authoring: never delete nodes on pre-existing assets).
  BENCH      reversible look test, NO SAVE PATH.  Writes originals to s3_shore_bench_originals_<run>.json and prints
             the path BEFORE changing anything; spawns ZZ_S3ShoreGroundBench attached to S3 Hangar Root at relative
             identity; hides the deck + v2 sand by set_visibility (UFUNCTION; whether it dirties is MEASURED here);
             captures the S3 shot stills (s3_beach_marble_stills.py pattern); destroys the spawn BY REFERENCE and
             restores visibility in `finally`; verifies against the file; reports the census.
  BENCH_PIE_APPLY    (added 7 Oct, offline, NOT RUN) PIE ONLY: the combined PIE still with the s3mg marble bench.
             Borrows the PIE copy of the deck (mesh/MI/relative identity/tag ZZ_S3ShoreGroundBench), hides the PIE
             copy of the v2 sand; originals file first; never saves, never starts/ends PIE, never spawns/destroys.
             Why borrow: see the BENCH_PIE section (deferred spawn is not exposed to UE 5.8 Python, measured).
  BENCH_PIE_RESTORE  PIE: puts both PIE copies back from the originals file of args["bench_run"]; idempotent
             (NOOP marker when PIE is gone / a new PIE / already restored).
  IMPORT takes "mesh_name" (default SM_S3_ShoreGround = v1); set B goes in as SM_S3_ShoreGround_B (create-only).
  APPLY      (7 Oct evening, offline, NOT RUN; section BEGIN_APPLY) record FIRST (s3_shore_ground_record.json, refuses
             if present) -> Backups/PreS3ShoreGround-<run> (umap + LS_S3_HangarRise + record, sha-checked) -> spawn
             "S3 Shore Ground" (mesh = mesh_name, slot 0 = mi, default MI_S3_ShoreGround_v2, tag
             RigAtmos.S3ShoreGround, MOVABLE, NO_COLLISION) attached KEEP_RELATIVE to S3 Hangar Root at relative
             identity -> mirror the deck's rise reveal if it has one -> hide deck and v2 sand (actor hidden in game +
             every primitive component visibility off + hidden in game; exact originals in the record) -> save
             census-exact (map [+ LS_S3_HangarRise only if a reveal was copied]) -> fresh read-back + landed-box guard.
  REVERT     destroy the recorded actor (by path, by reference), remove our reveal binding, restore deck / v2 sand
             flags exactly from the record, save, read back; record -> .reverted-<run>.  Assets stay.
  VERIFY     (still refused by the runner) read-only end state; then queue InfinityStage.Editor.SavedMasterMatchesShow and
             InfinityStage.Editor.SceneCutBindingsResolve after a run-id marker (memory tk-saved-master-stage-is-fake).

Markers: S3SHORE_START|run= / S3SHORE_<MODE>_OK|run= / S3SHORE_FAILED|run=|<reason>
Crash rules (memory puss-mcp-python-crashes-the-editor): no UE object at module level; no reloading the open
level; no open-range GetBoundObjects; destroy spawns by reference in the same call.
"""
import datetime
import hashlib
import json
import os
import shutil

try:
    import unreal
except ModuleNotFoundError:  # offline
    unreal = None

PROJECT = "E:/PussStage/"
HERE = PROJECT + "Saved/CodexConductor/S3Shore/"
ARGS = HERE + "s3_shore_ground_args.json"
LIVE_READS = HERE + "s3_shore_live_reads.json"
RECORD = HERE + "s3_shore_ground_record.json"
MANIFEST = PROJECT + "DerivedAssets/S3Shore/SM_S3_ShoreGround_manifest.json"
FBX = PROJECT + "DerivedAssets/S3Shore/SM_S3_ShoreGround.fbx"
WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
UMAP = PROJECT + "Content/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.umap"
BACKUP_ROOT = PROJECT + "Backups/PreS3ShoreGround-"
ASSET_DIR = "/Game/InfinityStage/Dev/Generated/S3Shore"
MESH = ASSET_DIR + "/SM_S3_ShoreGround"
MASTER = ASSET_DIR + "/M_S3_ShoreGround"
MI = ASSET_DIR + "/MI_S3_ShoreGround"
ROOT_LABEL = "S3 Hangar Root"
DECK_LABEL = "S3 Hangar Deck"
V2_SAND_LABEL = "S3 Beach V2 Sand Floor"
ACTOR_LABEL = "S3 Shore Ground"
BENCH_LABEL = "ZZ_S3ShoreGroundBench"
TAG = "RigAtmos.S3ShoreGround"
ROOT_LANDED_WORLD = (11421.97275, 160000.0, -120.0)
LANDED_LOCAL_BOX = {"min": (-1.0, -1013.0, 94.0), "max": (6013.0, 1009.0, 400.0)}   # guard (memory landed-frame trap)
REQUIRED_TESTS = ("InfinityStage.Editor.SavedMasterMatchesShow", "InfinityStage.Editor.SceneCutBindingsResolve")

# Textures (all present on disk, measured 7 Oct by ls; the Megascans_4K sand/mud folders are EMPTY)
TEX = {
    "SandAlbedo": "/Game/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/pjuuz_2K_Albedo",
    "SandNormal": "/Game/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/pjuuz_2K_Normal",
    "SandRough": "/Game/EnvironmentPacks/Megascans_2K/Surface/01_Soil_Sand_pjuuz0/pjuuz_2K_Roughness",
    "MudAlbedo": "/Game/EnvironmentPacks/Megascans_2K/Surface/09_Soil_Mud_pkbc30/pkbc3_2K_Albedo",
    "MudNormal": "/Game/EnvironmentPacks/Megascans_2K/Surface/09_Soil_Mud_pkbc30/pkbc3_2K_Normal",
    "MudRough": "/Game/EnvironmentPacks/Megascans_2K/Surface/09_Soil_Mud_pkbc30/pkbc3_2K_Roughness",
    "MossAlbedo": "/Game/EnvironmentPacks/MWMeadowWetlands/Textures/Grounds/TEX_MWL_GroundMoss_col",
    "MossNormal": "/Game/EnvironmentPacks/MWMeadowWetlands/Textures/Grounds/TEX_MWL_GroundMoss_nrm",
}

# Scalar parameters (look values are Gary's; these are first-pass defaults)
SCALARS = {
    "SandTileM": (1.5, "10 Tiling"), "MudTileM": (2.0, "10 Tiling"), "MossTileM": (1.2, "10 Tiling"),
    "MudBlendContrast": (4.0, "20 Blend"), "MossStrength": (1.0, "20 Blend"),
    "WetDarken": (0.55, "30 Wet"), "WetRoughness": (0.12, "30 Wet"), "PuddleRoughness": (0.04, "30 Wet"),
    "PuddleFromG": (0.85, "30 Wet"), "NormalStrength": (1.0, "40 Normal"), "Specular": (0.5, "40 Normal"),
}
# MossNormal is NOT used: the MW _nrm textures may be RG-packed (the pack ships MF_MW_RG2Nrm) [bin+inf]; moss
# areas take the mud normal.  MW _col alpha is ignored.
TEX_PARAMS = {"SandAlbedo": "SandAlbedo", "SandNormalT": "SandNormal", "SandRoughT": "SandRough",
              "MudAlbedo": "MudAlbedo", "MudNormalT": "MudNormal", "MudRoughT": "MudRough", "MossAlbedo": "MossAlbedo"}
CODE_TILE = "return UV / max(TileM, 0.01);"
CODE_MUDW = "return saturate((VC.r - 0.5) * C + 0.5);"
CODE_BASE = ("float3 c = lerp(SandC, MudC, M);\n"
             "c = lerp(c, MossC, saturate(VC.b * MossS));\n"
             "return c * lerp(1.0, WetD, saturate(VC.g));")
CODE_ROUGH = ("float r = lerp(SandR, MudR, M);\n"
              "r = lerp(r, 0.85, saturate(VC.b));\n"
              "r = lerp(r, WetR, saturate(VC.g));\n"
              "float p = saturate((VC.g - PF) / max(1.0 - PF, 0.001));\n"
              "return lerp(r, PudR, p);")
CODE_NORMAL = ("float3 n = lerp(SandN, MudN, M);\n"
               "n.xy *= Str;\n"
               "float p = saturate((VC.g - PF) / max(1.0 - PF, 0.001));\n"
               "return normalize(lerp(n, float3(0, 0, 1), p));")
CUSTOM = {   # key: (code, inputs, output type)
    "TileSand": (CODE_TILE, ["UV", "TileM"], "F2"),
    "TileMud": (CODE_TILE, ["UV", "TileM"], "F2"),
    "TileMoss": (CODE_TILE, ["UV", "TileM"], "F2"),
    "MudW": (CODE_MUDW, ["VC", "C"], "F1"),
    "SH_Base": (CODE_BASE, ["SandC", "MudC", "MossC", "M", "VC", "MossS", "WetD"], "F3"),
    "SH_Rough": (CODE_ROUGH, ["SandR", "MudR", "M", "VC", "WetR", "PF", "PudR"], "F1"),
    "SH_Normal": (CODE_NORMAL, ["SandN", "MudN", "M", "Str", "VC", "PF"], "F3"),
}
FIXED_NODES = {"UV0": ("MaterialExpressionTextureCoordinate", {"coordinate_index": 0}),
               "VC": ("MaterialExpressionVertexColor", {})}
# (source, source output, target, target pin).  VertexColor output "" = its first (RGB) output [inf: the
# expression's .cpp, where Outputs are named, is not in the UE 5.8 install; recompile errors would expose it].
EDGES = [
    ("UV0", "", "TileSand", "UV"), ("SandTileM", "", "TileSand", "TileM"),
    ("UV0", "", "TileMud", "UV"), ("MudTileM", "", "TileMud", "TileM"),
    ("UV0", "", "TileMoss", "UV"), ("MossTileM", "", "TileMoss", "TileM"),
    ("TileSand", "", "SandAlbedo", "UVs"), ("TileSand", "", "SandNormalT", "UVs"), ("TileSand", "", "SandRoughT", "UVs"),
    ("TileMud", "", "MudAlbedo", "UVs"), ("TileMud", "", "MudNormalT", "UVs"), ("TileMud", "", "MudRoughT", "UVs"),
    ("TileMoss", "", "MossAlbedo", "UVs"),
    ("VC", "", "MudW", "VC"), ("MudBlendContrast", "", "MudW", "C"),
    ("SandAlbedo", "RGB", "SH_Base", "SandC"), ("MudAlbedo", "RGB", "SH_Base", "MudC"),
    ("MossAlbedo", "RGB", "SH_Base", "MossC"), ("MudW", "", "SH_Base", "M"), ("VC", "", "SH_Base", "VC"),
    ("MossStrength", "", "SH_Base", "MossS"), ("WetDarken", "", "SH_Base", "WetD"),
    ("SandRoughT", "R", "SH_Rough", "SandR"), ("MudRoughT", "R", "SH_Rough", "MudR"), ("MudW", "", "SH_Rough", "M"),
    ("VC", "", "SH_Rough", "VC"), ("WetRoughness", "", "SH_Rough", "WetR"), ("PuddleFromG", "", "SH_Rough", "PF"),
    ("PuddleRoughness", "", "SH_Rough", "PudR"),
    ("SandNormalT", "RGB", "SH_Normal", "SandN"), ("MudNormalT", "RGB", "SH_Normal", "MudN"),
    ("MudW", "", "SH_Normal", "M"), ("NormalStrength", "", "SH_Normal", "Str"), ("VC", "", "SH_Normal", "VC"),
    ("PuddleFromG", "", "SH_Normal", "PF"),
]
PROPS = [("SH_Base", "", "MP_BASE_COLOR"), ("SH_Rough", "", "MP_ROUGHNESS"), ("SH_Normal", "", "MP_NORMAL"),
         ("Specular", "", "MP_SPECULAR")]
MASTER_FLAGS = {"blend_mode": "BLEND_OPAQUE", "shading_model": "MSM_DEFAULT_LIT", "two_sided": False,
                "used_with_nanite": True}


def graph_spec():
    """Logical graph of M_S3_ShoreGround (pure data; the harness checks it with graph_problems()).

    Vertex colour: R = mud, G = wetness (+ puddle above PuddleFromG), B = moss, A = reserved.
    UV0 is metres in hangar-local space, so tiling rides with the rising box.
    """
    nodes = {k: ("scalar", v) for k, v in SCALARS.items()}
    nodes.update({k: ("texture", t) for k, t in TEX_PARAMS.items()})
    nodes.update({k: ("fixed", v) for k, v in FIXED_NODES.items()})
    nodes.update({k: ("custom", v) for k, v in CUSTOM.items()})
    return nodes, list(EDGES), list(PROPS)


def graph_problems():
    nodes, edges, props = graph_spec()
    probs = []
    for s, _o, d, _pin in edges:
        if s not in nodes or d not in nodes:
            probs.append("EDGE_NODE|%s->%s" % (s, d))
    seen = {}
    for s, _o, d, pin in edges:
        seen.setdefault((d, pin), []).append(s)
    for (d, pin), srcs in seen.items():
        if len(srcs) != 1:
            probs.append("PIN_FED_TWICE|%s.%s|%s" % (d, pin, srcs))
    for k, (kind, v) in nodes.items():
        if kind == "custom":
            code, ins, _t = v
            for pin in ins:
                if (k, pin) not in seen:
                    probs.append("CUSTOM_PIN_UNFED|%s.%s" % (k, pin))
                if pin not in code:
                    probs.append("CUSTOM_PIN_UNUSED_IN_CODE|%s.%s" % (k, pin))
        if kind == "texture" and (k, "UVs") not in seen:
            probs.append("TEXTURE_UV_UNFED|%s" % k)
    used = {e[0] for e in edges} | {p[0] for p in props}
    for k in nodes:
        if k not in used:
            probs.append("UNUSED_NODE|%s" % k)
    if {p[2] for p in props} != {"MP_BASE_COLOR", "MP_ROUGHNESS", "MP_NORMAL", "MP_SPECULAR"}:
        probs.append("PROPS")
    return probs


# ----------------------------------------------------------------------------- offline helpers
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def footprint_from_live_reads(live, footprint_path=HERE + "s3_shore_footprint.json"):
    """Offline: update s3_shore_footprint.json from a DRY live read (every changed field logged)."""
    with open(footprint_path, encoding="utf-8") as f:
        fp = json.load(f)
    root = live["root"]["world_location"]
    changes = []
    for i, v in enumerate(ROOT_LANDED_WORLD):
        if abs(root[i] - v) > 1.0:
            changes.append("ROOT_MOVED axis=%d live=%s" % (i, root[i]))
    for row in fp["figures"]["rows"]:
        lv = live["figures"].get(row["label"])
        if lv:
            dock = [lv["local"][0] + 500.0, lv["local"][1]]
            if abs(dock[0] - row["dock_xy"][0]) > 1 or abs(dock[1] - row["dock_xy"][1]) > 1:
                changes.append("FIGURE_MOVED %s %s -> %s" % (row["label"], row["dock_xy"], dock))
                row["dock_xy"] = dock
            foot = lv["foot_local_z"] - 115.0 - 5.0   # back to dock-z convention (+5 = floor top)
            if abs(foot - row["foot_dock_z"]) > 0.5:
                changes.append("FIGURE_FOOT %s %.2f -> %.2f" % (row["label"], row["foot_dock_z"], foot))
                row["foot_dock_z"] = foot
    if live.get("cameras"):
        fp["cameras"]["rows"] = [{"label": k, "local": v["local"], "rpy": v["rpy"], "lens_mm": v.get("lens_mm", 35.0)}
                                 for k, v in sorted(live["cameras"].items())]
        fp["cameras"]["tier"] = "measured"
        fp["cameras"]["src"] = "s3_shore_live_reads.json run %s" % live.get("run")
    return fp, changes


# ----------------------------------------------------------------------------- editor helpers
def _require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def _write(path, value):
    with open(path, "w", encoding="utf-8") as h:
        json.dump(value, h, indent=1, default=str)
        h.flush()
        os.fsync(h.fileno())


def _census():
    lib = unreal.EditorLoadingAndSavingUtils
    return {"content": sorted(str(p.get_name()) for p in lib.get_dirty_content_packages()),
            "maps": sorted(str(p.get_name()) for p in lib.get_dirty_map_packages())}


def _actors_by_label(world):
    acts = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)   # sees transient actors too
    out = {}
    for a in acts:
        out.setdefault(str(a.get_actor_label()), []).append(a)
    return out


def _one(by_label, label):
    rows = by_label.get(label, [])
    _require(len(rows) == 1, "LABEL_COUNT|%s|%d" % (label, len(rows)))
    return rows[0]


def _local(root, world_vec):
    return root.get_actor_transform().inverse_transform_location(world_vec)


def _bounds_local(root, actor):
    origin, extent = actor.get_actor_bounds(False)
    pts = [unreal.Vector(origin.x + sx * extent.x, origin.y + sy * extent.y, origin.z + sz * extent.z)
           for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    loc = [_local(root, p) for p in pts]
    return {"min": [min(p.x for p in loc), min(p.y for p in loc), min(p.z for p in loc)],
            "max": [max(p.x for p in loc), max(p.y for p in loc), max(p.z for p in loc)]}


def run_dry(run):
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    _require(str(world.get_path_name()).startswith(WORLD), "WRONG_WORLD")
    by = _actors_by_label(world)
    root = _one(by, ROOT_LABEL)
    rl = root.get_actor_location()
    out = {"run": run, "utc": datetime.datetime.utcnow().isoformat() + "Z",
           "root": {"world_location": [rl.x, rl.y, rl.z], "rotation": str(root.get_actor_rotation())},
           "landed_matches_footprint": all(abs(a - b) <= 1.0 for a, b in zip((rl.x, rl.y, rl.z), ROOT_LANDED_WORLD)),
           "actors": {}, "figures": {}, "cameras": {}, "census": _census()}
    for label in (DECK_LABEL, V2_SAND_LABEL, "S3 Backdrop", "S3 Hangar Left Wall", "S3 Hangar Right Wall",
                  "S3 Marble Inner Wall Left", "S3 Marble Inner Wall Right", "Clam_Pedastal",
                  "S3 Hangar Far Wall Left of Exit", "S3 Hangar Far Wall Right of Exit"):
        for a in by.get(label, []):
            parent = a.get_attach_parent_actor()
            comp = a.root_component
            out["actors"][label] = {"parent": str(parent.get_actor_label()) if parent else None,
                                    "mobility": str(comp.get_editor_property("mobility")) if comp else None,
                                    "local_aabb": _bounds_local(root, a),
                                    "hidden_in_game": bool(a.get_editor_property("hidden")) if hasattr(a, "get_editor_property") else None}
    for label, rows in by.items():
        if label.startswith("Shore0") and label.endswith("Clam"):
            a = rows[0]
            b = _bounds_local(root, a)
            parent = a.get_attach_parent_actor()
            out["figures"][label] = {"local": list(map(float, (_local(root, a.get_actor_location()).x,
                                                                _local(root, a.get_actor_location()).y))),
                                     "foot_local_z": b["min"][2], "local_aabb": b,
                                     "parent": str(parent.get_actor_label()) if parent else None}
        if label.startswith(("S3 Wave", "S3 Beach V2")):
            out["actors"][label] = {"local_aabb": _bounds_local(root, rows[0])}
        for a in rows:
            if isinstance(a, unreal.CineCameraActor) and (label.startswith("S3 ") or label.startswith("Scene 3")):
                cam = a.get_cine_camera_component()
                p = _local(root, a.get_actor_location())
                r = a.get_actor_rotation()
                out["cameras"][label] = {"local": [p.x, p.y, p.z], "rpy": [r.roll, r.pitch, r.yaw],
                                         "lens_mm": float(cam.get_editor_property("current_focal_length"))}
    out["fbx_sha256"] = sha256_file(FBX)
    out["manifest_sha256"] = json.load(open(MANIFEST, encoding="utf-8"))["fbx_sha256"]
    _require(out["fbx_sha256"] == out["manifest_sha256"], "FBX_HASH_MISMATCH")
    out["assets_exist"] = {p: unreal.EditorAssetLibrary.does_asset_exist(p) for p in (MESH, MASTER, MI)}
    _write(LIVE_READS, out)
    return out
    # NOTE Sequencer-spawned shot cameras (LS_DevScene_03 shot sub-sequences) are NOT level actors; their
    # template poses need the read pattern in memory ue58-fbx-import-traps (root component relative transform).


def _enum_name(v):
    s = str(v)
    return s.split(".")[-1].split(":")[0].strip("<> ").upper()


def _pipeline(asset_name="SM_S3_ShoreGround"):
    """Interchange override for one static mesh.  Names checked 7 Oct against the UE 5.8 headers
    (declaration-proven, see the API table in Docs/Conductor/S3_SHORE_GROUND_PREP_2026-10-07.md):
      InterchangeGenericMeshPipeline.h:73 bImportStaticMeshes, :204 bImportSkeletalMeshes, :101 bCollision,
      :134 bBuildNanite; InterchangeGenericAssetsPipelineSharedSettings.h:95 bImportLods, :127 bRecomputeNormals,
      :111 VertexColorImportOption (default IVCIO_Replace -> NOT set, only read back);
      InterchangeGenericMaterialPipeline.h:85 bImportMaterials; InterchangeGenericTexturePipeline.h:32 bImportTextures.
    Run-proven precedent for the object path: s3_beach_v2.py:666-699 (4 Oct), s3_sack_install.py:1012-1041 (6 Oct)."""
    p = unreal.InterchangeGenericAssetsPipeline()
    common = p.get_editor_property("common_meshes_properties")
    mesh = p.get_editor_property("mesh_pipeline")
    mat = p.get_editor_property("material_pipeline")
    tex = mat.get_editor_property("texture_pipeline") if mat else None
    _require(all(x is not None for x in (common, mesh, mat, tex)), "PIPELINE_SUBOBJECTS")
    p.set_editor_property("asset_name", asset_name)
    wanted = [(mat, "import_materials", False), (tex, "import_textures", False),
              (mesh, "import_static_meshes", True), (mesh, "import_skeletal_meshes", False),
              (mesh, "build_nanite", True), (mesh, "collision", False),
              (common, "import_lods", False), (common, "recompute_normals", False)]
    for obj, prop, val in wanted:
        obj.set_editor_property(prop, val)
    got = {}
    for obj, prop, val in wanted:
        got[prop] = obj.get_editor_property(prop)
        _require(got[prop] == val, "PIPELINE_READBACK|%s=%s" % (prop, got[prop]))
    vc = _enum_name(common.get_editor_property("vertex_color_import_option"))
    _require(vc.endswith("REPLACE"), "VERTEX_COLOR_OPTION|%s" % vc)
    got["vertex_color_import_option"] = vc
    for k in ("import_offset_translation", "import_offset_rotation", "import_offset_uniform_scale"):
        got[k] = str(p.get_editor_property(k))
    ov = unreal.InterchangePipelineStackOverride()
    ov.add_pipeline(p)
    return ov, got


DEFAULT_MESH_NAME = "SM_S3_ShoreGround"          # v1 asset; set B goes in as "SM_S3_ShoreGround_B" (7 Oct)


def mesh_name_of(args):
    name = str((args or {}).get("mesh_name") or DEFAULT_MESH_NAME)
    _require(name.startswith("SM_S3_ShoreGround") and all(c.isalnum() or c == "_" for c in name), "MESH_NAME|%r" % name)
    return name


def mesh_path_of(args):
    return ASSET_DIR + "/" + mesh_name_of(args)


def import_record_path(name):
    return RECORD + ".import" if name == DEFAULT_MESH_NAME else RECORD + ".import-" + name


def run_import(run, args=None):
    """Create-only.  args["mesh_name"] (default SM_S3_ShoreGround) names the NEW asset; never reimports in place."""
    eal = unreal.EditorAssetLibrary
    name = mesh_name_of(args)
    MESH = ASSET_DIR + "/" + name                                   # noqa: N806 (shadows the v1 constant on purpose)
    _require(_census() == {"content": [], "maps": []}, "DIRTY_EDITOR|%s" % _census())
    _require(not eal.does_asset_exist(MESH), "MESH_EXISTS|%s" % MESH)
    _require(not os.path.isfile(import_record_path(name)), "IMPORT_RECORD_EXISTS|%s" % import_record_path(name))
    man = json.load(open(MANIFEST, encoding="utf-8"))
    _require(sha256_file(FBX) == man["fbx_sha256"], "FBX_HASH")
    before = set(eal.list_assets(ASSET_DIR, recursive=True)) if eal.does_directory_exist(ASSET_DIR) else set()
    task = unreal.AssetImportTask()
    for k, v in (("filename", FBX), ("destination_path", ASSET_DIR), ("destination_name", name),
                 ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    ov, settings = _pipeline(name)
    task.set_editor_property("options", ov)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(MESH)
    _require(isinstance(mesh, unreal.StaticMesh), "IMPORT_FAILED|%s" % list(task.imported_object_paths))
    new = sorted(str(n).split(".")[0] for n in set(eal.list_assets(ASSET_DIR, recursive=True)) - before)
    _require(new == [MESH], "STRAY_ASSETS|%s" % new)        # strays are never-saved: discard by restart, not delete
    _require(mesh.get_num_lods() == 1, "LODS|%d" % mesh.get_num_lods())          # StaticMesh.h:2176 ScriptName GetNumLods
    nanite = bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled"))  # StaticMesh.h:746; EngineTypes.h:3285
    _require(nanite, "NANITE_OFF")
    bb = mesh.get_bounding_box()                                                    # StaticMesh.h:2204
    exp = man["expected_ue_local_bounds_cm"]
    got = {"min": [bb.min.x, bb.min.y, bb.min.z], "max": [bb.max.x, bb.max.y, bb.max.z]}
    for k in ("min", "max"):
        for i in range(3):
            _require(abs(got[k][i] - exp[k][i]) <= 0.5, "BOUNDS|%s|got=%s|exp=%s (Y swapped => mirrored)" % (k, got, exp))
    sme = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    has_vc = bool(sme.has_vertex_colors(mesh))                                      # StaticMeshEditorSubsystem.h:468-470
    _require(has_vc, "NO_VERTEX_COLOURS")
    slots = [str(m.get_editor_property("material_slot_name")) for m in mesh.get_editor_property("static_materials")]
    # Calibration byte values: StaticMeshDescription has NO vertex-instance colour UFUNCTION (only the C++
    # GetVertexInstanceColors(), StaticMeshDescription.h:77-78) -> UNREAD here; BENCH stills are the colour check.
    calib = [{"want": c, "got": None, "status": "UNREADABLE_FROM_PYTHON"} for c in man["calibration_vertices"]]
    _require(_census() == {"content": [MESH], "maps": []}, "DIRTY_SCOPE|%s" % _census())
    _require(eal.save_asset(MESH, only_if_is_dirty=False), "SAVE_MESH")
    _require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    rec = {"run": run, "mesh": MESH, "bounds": got, "nanite": nanite, "has_vertex_colors": has_vc, "slots": slots,
           "pipeline": settings, "calibration": calib, "fbx_sha256": man["fbx_sha256"], "saved": True}
    _write(import_record_path(name), rec)
    return rec


def _sampler_for(tex):
    comp = _enum_name(tex.get_editor_property("compression_settings"))
    srgb = bool(tex.get_editor_property("srgb"))
    if comp == "TC_NORMALMAP":
        return "SAMPLERTYPE_NORMAL"
    if comp == "TC_MASKS":
        return "SAMPLERTYPE_MASKS"
    if comp in ("TC_GRAYSCALE", "TC_ALPHA", "TC_DISPLACEMENTMAP"):
        return "SAMPLERTYPE_GRAYSCALE" if srgb else "SAMPLERTYPE_LINEAR_GRAYSCALE"
    if comp in ("TC_DEFAULT", "TC_BC7"):
        return "SAMPLERTYPE_COLOR" if srgb else "SAMPLERTYPE_LINEAR_COLOR"
    raise RuntimeError("SAMPLER_UNMAPPED|%s|srgb=%s" % (comp, srgb))


def run_build_mat(run):
    """Create-only master + MI (pattern s3_sack_install.py:1175-1256 and 1330-1345, BUILD_MAT run 6 Oct, saved).
    Never touches an existing asset.  Textures are existing assets, only referenced."""
    eal, mel = unreal.EditorAssetLibrary, unreal.MaterialEditingLibrary
    _require(_census() == {"content": [], "maps": []}, "DIRTY_EDITOR|%s" % _census())
    _require(not graph_problems(), "GRAPH_SPEC|%s" % graph_problems())
    for p in (MASTER, MI):
        _require(not eal.does_asset_exist(p), "EXISTS|" + p)
    textures = {}
    for key, path in TEX.items():
        if key == "MossNormal":
            continue
        t = unreal.load_asset(path)
        _require(isinstance(t, unreal.Texture2D), "TEXTURE_MISSING|" + path)
        textures[key] = t
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(MASTER.rsplit("/", 1)[1], ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())
    _require(mat is not None, "MASTER_CREATE")
    mat.modify()
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("used_with_nanite", True)                              # Material.h:863 bUsedWithNanite
    nodes, edges, props = graph_spec()
    made = {}
    otypes = {"F1": unreal.CustomMaterialOutputType.CMOT_FLOAT1, "F2": unreal.CustomMaterialOutputType.CMOT_FLOAT2,
              "F3": unreal.CustomMaterialOutputType.CMOT_FLOAT3}
    for i, (key, (kind, v)) in enumerate(nodes.items()):
        if kind == "scalar":
            n = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -2400, -900 + 70 * i)
            _require(n is not None, "CREATE_NODE|" + key)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("default_value", float(v[0]))
            n.set_editor_property("group", v[1])
        elif kind == "texture":
            tex = textures[v]
            n = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSampleParameter2D, -1500, -900 + 260 * i)
            _require(n is not None, "CREATE_NODE|" + key)
            n.set_editor_property("parameter_name", key)
            n.set_editor_property("texture", tex)
            n.set_editor_property("sampler_type", getattr(unreal.MaterialSamplerType, _sampler_for(tex)))
            n.set_editor_property("group", "00 Textures")
        elif kind == "fixed":
            cls_name, pp = v
            n = mel.create_material_expression(mat, getattr(unreal, cls_name), -2000, 200 + 120 * i)
            _require(n is not None, "CREATE_NODE|" + key)
            for k2, v2 in pp.items():
                n.set_editor_property(k2, v2)
        else:
            code, ins, otype = v
            n = mel.create_material_expression(mat, unreal.MaterialExpressionCustom, -900, -600 + 200 * i)
            _require(n is not None, "CREATE_NODE|" + key)
            n.set_editor_property("description", key)
            n.set_editor_property("code", code)
            n.set_editor_property("output_type", otypes[otype])
            cis = []
            for name in ins:
                ci = unreal.CustomInput()
                ci.set_editor_property("input_name", name)
                cis.append(ci)
            n.set_editor_property("inputs", cis)
            got = [str(c.get_editor_property("input_name")) for c in n.get_editor_property("inputs")]
            _require(got == list(ins), "CUSTOM_INPUTS|%s|%s" % (key, got))
        made[key] = n
    for s, o, d, pin in edges:
        ok = mel.connect_material_expressions(made[s], o, made[d], pin)
        _require(ok, "LINK|%s.%s->%s.%s|inputs=%s" % (s, o, d, pin,
                                                     [str(x) for x in mel.get_material_expression_input_names(made[d])]))
    for s, o, prop in props:
        _require(mel.connect_material_property(made[s], o, getattr(unreal.MaterialProperty, prop)), "PROP|" + prop)
    errors = [str(e) for e in (mel.recompile_material(mat) or [])]
    _require(not errors, "RECOMPILE|%s" % errors)
    _require(bool(mat.get_editor_property("used_with_nanite")), "NANITE_USAGE_READBACK")
    mi = tools.create_asset(MI.rsplit("/", 1)[1], ASSET_DIR, unreal.MaterialInstanceConstant,
                            unreal.MaterialInstanceConstantFactoryNew())
    _require(mi is not None, "MI_CREATE")
    mi.modify()
    mel.set_material_instance_parent(mi, mat)
    mel.update_material_instance(mi)
    _require(mi.get_editor_property("parent") == mat, "MI_PARENT")
    scal = {k: float(mel.get_material_instance_scalar_parameter_value(mi, k)) for k in SCALARS}
    bad = {k: v for k, v in scal.items() if abs(v - SCALARS[k][0]) > 1e-4}
    _require(not bad, "MI_DEFAULTS|%s" % bad)
    planned = sorted([MASTER, MI])
    _require(_census() == {"content": planned, "maps": []}, "DIRTY_SCOPE|%s" % _census())
    for p in planned:
        _require(eal.save_asset(p, only_if_is_dirty=False), "SAVE|" + p)
    _require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    unreal.SystemLibrary.collect_garbage()                       # memory ue58-bulk-import-oom-crash
    rec = {"run": run, "master": MASTER, "mi": MI, "nodes": len(made), "edges": len(edges), "scalars": scal,
           "samplers": {k: _sampler_for(t) for k, t in textures.items()}, "saved": True}
    _write(RECORD + ".build_mat", rec)
    return rec


# ----------------------------------------------------------------------------- BENCH (tick-driven stills)
BENCH_SHOTS = ("S3 Shot B02", "S3 Shot B04", "S3 Shot B09")
SEQUENCE_PATH = "/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"
STILLS_DIR = PROJECT + "Saved/CodexConductor/S3Shore/BenchStills/"


def _bench_jobs(run, by):
    """Shot poses from the LS_DevScene_03 spawnable templates (pattern s3_beach_marble_stills.py:84-131, run 3 Oct:
    unattached template roots => relative_* is world) + the level Entry Handoff camera.  Missing shots are recorded."""
    import math
    jobs, missing = [], []
    seq = unreal.load_asset(SEQUENCE_PATH)
    _require(isinstance(seq, unreal.LevelSequence), "SEQUENCE_LOAD")
    spawn = {str(b.get_display_name()): b for b in seq.get_spawnables()}
    for label in BENCH_SHOTS:
        b = spawn.get(label)
        tmpl = b.get_object_template() if b else None
        root = tmpl.get_editor_property("root_component") if tmpl else None
        comp = tmpl.get_cine_camera_component() if tmpl else None
        if root is None or comp is None or root.get_attach_parent() is not None:
            missing.append(label)
            continue
        jobs.append({"label": label, "location": root.get_editor_property("relative_location"),
                     "rotation": root.get_editor_property("relative_rotation"), "comp": comp})
    for label, rows in by.items():
        if label.startswith("Scene 3") and label.endswith("Entry Handoff Camera"):
            a = rows[0]
            jobs.append({"label": "EntryHandoff", "location": a.get_actor_location(),
                         "rotation": a.get_actor_rotation(), "comp": a.get_cine_camera_component()})
    for j in jobs:
        fb = j["comp"].get_editor_property("filmback")
        sw = float(fb.get_editor_property("sensor_width"))
        fl = float(j["comp"].get_editor_property("current_focal_length"))
        j["hfov_deg"] = math.degrees(2.0 * math.atan(sw / (2.0 * fl)))
        j["path"] = STILLS_DIR + "S3Shore_%s_%s.png" % (j["label"].rsplit(" ", 1)[-1], run)
        j["pose_record"] = {"label": j["label"], "path": j["path"],
                            "location": [j["location"].x, j["location"].y, j["location"].z],
                            "rotation_rpy": [j["rotation"].roll, j["rotation"].pitch, j["rotation"].yaw],
                            "focal_mm": fl, "sensor_width_mm": sw}
        del j["comp"]
    return jobs, missing


def _restore_from_originals(orig, spawned=None):
    """Idempotent: destroy the bench actor (by reference, plus any by label via GameplayStatics), set deck / v2
    visibility back to the values in the originals FILE, then verify."""
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    if spawned is not None:
        spawned.destroy_actor()
    by = _actors_by_label(world)
    for a in by.get(BENCH_LABEL, []):
        a.destroy_actor()
    deck = _one(by, DECK_LABEL)
    deck.static_mesh_component.set_visibility(bool(orig["deck_visible"]), False)
    v2 = by.get(V2_SAND_LABEL, [None])[0]
    if v2 is not None and orig.get("v2_visible") is not None:
        v2.static_mesh_component.set_visibility(bool(orig["v2_visible"]), False)
    by2 = _actors_by_label(world)
    _require(not by2.get(BENCH_LABEL), "BENCH_ACTOR_SURVIVED")
    _require(bool(_one(by2, DECK_LABEL).static_mesh_component.is_visible()) == bool(orig["deck_visible"]), "RESTORE_DECK")


def run_bench(run, args):
    """Reversible look test.  NO SAVE PATH.  Originals go to a FILE before any change.  The spawned (transient)
    actor lives across slate ticks inside this one script run (held by reference, destroyed in finish/fail);
    BENCH_RESTORE is the out-of-band restore if anything interrupts it."""
    import builtins
    import time
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    _require(str(world.get_outermost().get_name()) == WORLD, "WRONG_WORLD")
    _require(ed.get_game_world() is None, "PIE_ACTIVE")
    _require(not hasattr(builtins, "PUSS_S3SHORE_BENCH"), "BENCH_ALREADY_RUNNING")
    _require(_census() == {"content": [], "maps": []}, "DIRTY_BEFORE|%s" % _census())
    for p in (MESH, MI):
        _require(unreal.EditorAssetLibrary.does_asset_exist(p), "ASSET_MISSING|" + p)
    by = _actors_by_label(world)
    _require(not by.get(BENCH_LABEL), "STALE_BENCH_ACTOR")
    root = _one(by, ROOT_LABEL)
    rl = root.get_actor_location()
    _require(all(abs(a - b) <= 0.5 for a, b in zip((rl.x, rl.y, rl.z), ROOT_LANDED_WORLD)), "NOT_LANDED")
    deck = _one(by, DECK_LABEL)
    v2 = by.get(V2_SAND_LABEL, [None])[0]
    jobs, missing = _bench_jobs(run, by)
    os.makedirs(STILLS_DIR, exist_ok=True)
    viewport0 = unreal.EditorLevelLibrary.get_level_viewport_camera_info()
    orig = {"run": run, "census_before": _census(), "deck_visible": bool(deck.static_mesh_component.is_visible()),
            "v2_visible": bool(v2.static_mesh_component.is_visible()) if v2 else None,
            "viewport": [str(x) for x in (viewport0 or [])],
            "shots": [j["pose_record"] for j in jobs], "missing_shots": missing}
    opath = HERE + "s3_shore_bench_originals_%s.json" % run
    _write(opath, orig)
    unreal.log("S3SHORE_BENCH_ORIGINALS|run=%s|%s" % (run, opath))
    spawned = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
        unreal.StaticMeshActor, root.get_actor_location(), root.get_actor_rotation(), True)   # EditorActorSubsystem.h:228
    try:
        spawned.set_actor_label(BENCH_LABEL)
        smc = spawned.static_mesh_component
        smc.set_mobility(unreal.ComponentMobility.MOVABLE)
        _require(smc.set_static_mesh(unreal.load_asset(MESH)), "SET_MESH")         # StaticMeshComponent.h:449-450
        smc.set_material(0, unreal.load_asset(MI))
        spawned.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE,
                                unreal.AttachmentRule.KEEP_RELATIVE, False)
        spawned.root_component.set_relative_transform(unreal.Transform(), False, False)
        rel = spawned.root_component.get_relative_transform()
        _require(rel.translation.length() < 0.01, "BENCH_NOT_IDENTITY")
        deck.static_mesh_component.set_visibility(False, False)                     # SceneComponent.h:916
        if v2:
            v2.static_mesh_component.set_visibility(False, False)
        orig["census_after_set"] = _census()                                        # MEASURE: what dirtied?
        _write(opath, orig)
    except Exception:
        _restore_from_originals(orig, spawned)
        raise
    state = {"i": 0, "phase": "setup", "ticks": 0, "t": 0.0, "last": -1, "stable": 0, "msgs": False}

    def stop():
        h = getattr(builtins, "PUSS_S3SHORE_BENCH", None)
        if h is not None:
            unreal.unregister_slate_post_tick_callback(h)
            delattr(builtins, "PUSS_S3SHORE_BENCH")

    def restore_all():
        try:
            unreal.SystemLibrary.execute_console_command(world, "FOV 90")
            if state["msgs"]:
                unreal.SystemLibrary.execute_console_command(world, "EnableAllScreenMessages")
            if viewport0:
                unreal.EditorLevelLibrary.set_level_viewport_camera_info(viewport0[0], viewport0[1])
        finally:
            _restore_from_originals(orig, spawned)

    def tick(_dt):
        try:
            if state["i"] >= len(jobs):
                stop()
                restore_all()
                orig["census_end"] = _census()
                orig["stills"] = [{"label": j["label"], "path": j["path"],
                                   "bytes": os.path.getsize(j["path"]) if os.path.isfile(j["path"]) else None}
                                  for j in jobs]
                _write(opath, orig)
                unreal.log("S3SHORE_BENCH_OK|run=%s|stills=%d|missing=%s|census_end=%s|originals=%s" % (
                    run, len(jobs), missing, json.dumps(orig["census_end"]), opath))
                return
            j = jobs[state["i"]]
            if state["phase"] == "setup":
                if not state["msgs"]:
                    unreal.SystemLibrary.execute_console_command(world, "DisableAllScreenMessages")
                    state["msgs"] = True
                unreal.SystemLibrary.execute_console_command(world, "FOV %.9f" % j["hfov_deg"])
                unreal.EditorLevelLibrary.set_level_viewport_camera_info(j["location"], j["rotation"])
                state.update(phase="settle", ticks=0)
                return
            if state["phase"] == "settle":
                state["ticks"] += 1
                if state["ticks"] < 30:          # Nanite build + new shader: allow streaming / compile
                    return
                unreal.SystemLibrary.execute_console_command(world, "HighResShot 1600x900 filename=" + j["path"])
                state.update(phase="wait", t=time.time(), last=-1, stable=0)
                return
            size = os.path.getsize(j["path"]) if os.path.isfile(j["path"]) else -1
            if size > 1000 and size == state["last"]:
                state["stable"] += 1
            else:
                state.update(stable=0, last=size)
            if state["stable"] >= 4:
                state.update(i=state["i"] + 1, phase="setup")
            elif time.time() - state["t"] > 60.0:
                raise RuntimeError("CAPTURE_TIMEOUT|" + j["path"])
        except Exception as exc:  # noqa: BLE001
            stop()
            try:
                restore_all()
            finally:
                unreal.log_error("S3SHORE_FAILED|run=%s|BENCH_TICK|%r|originals=%s" % (run, exc, opath))

    builtins.PUSS_S3SHORE_BENCH = unreal.register_slate_post_tick_callback(tick)
    return {"originals": opath, "jobs": [j["label"] for j in jobs], "missing": missing,
            "census_after_set": orig["census_after_set"], "status": "STARTED (wait for S3SHORE_BENCH_OK in the log)"}


def run_bench_restore(run, args):
    """Out-of-band restore from the originals file of args['bench_run'] (no save)."""
    import builtins
    h = getattr(builtins, "PUSS_S3SHORE_BENCH", None)
    if h is not None:
        unreal.unregister_slate_post_tick_callback(h)
        delattr(builtins, "PUSS_S3SHORE_BENCH")
    opath = HERE + "s3_shore_bench_originals_%s.json" % args["bench_run"]
    orig = json.load(open(opath, encoding="utf-8"))
    _restore_from_originals(orig)
    return {"restored_from": opath, "census": _census()}


# ----------------------------------------------------------------------------- BENCH_PIE (combined PIE still)
# BEGIN_BENCH_PIE  (the harness scans this section for save / PIE-control / destroy / editor-spawn calls)
#
# Gary 7 Oct: ONE combined PIE bench of this ground + marble variant C (s3mg_bench.py), no level save, Don't-Save
# restart afterwards.  The editor-world BENCH above cannot be in a PIE still (PIE is a copy taken at PIE start).
#
# WHY BORROW, NOT SPAWN.  The brief asked for GameplayStatics begin/finish deferred spawn into the PIE world (as in
# s3mg_bench.py:285-292).  That route does NOT exist in UE 5.8 Python [measured twice: AttributeError "type object
# 'GameplayStatics' has no attribute 'begin_deferred_actor_spawn_from_class'" in
# Saved/CodexFlatV3/swapkit/stills/before/FV3STB-20261003-02/st_pie_first_check_runtime.json (3 Oct) and
# Saved/CodexConductor/LookBench/20261005-044136/look_bench_result.json (5 Oct)].  The header marks both functions
# BlueprintInternalUseOnly (GameplayStatics.h:66,70) [decl]; AddComponentByClass is ScriptNoExport (Actor.h:1974)
# [decl].  So, like gloss4_glint_pie_spawn.py and hp_test_pie_still.py (borrow an existing PIE copy), this bench
# BORROWS THE PIE COPY OF THE DECK ITSELF: deck = StaticMeshActor, MOVABLE, attached to S3 Hangar Root [meas:
# hp_probe_walls_result.json, s3_shore_live_reads.json run S3SHORE-20261007-181646].  On that PIE copy only:
# mesh -> SM_S3_ShoreGround, every slot -> MI_S3_ShoreGround, relative transform -> identity (it rides the root
# exactly like a spawned child at relative identity), tag ZZ_S3ShoreGroundBench added.  The v2 sand PIE copy is
# hidden (set_actor_hidden_in_game + component set_visibility).  Nothing is spawned or destroyed.  The deck is
# NOT hidden: its PIE copy IS the bench ground.  PIE end discards all of it; RESTORE puts every value back from
# the originals file while PIE runs (so the s3mg stills/restore sequence ends with the PIE world as it started).
PIE_TAG = BENCH_LABEL                     # "ZZ_S3ShoreGroundBench" (s3mg uses "ZZ_S3MG": exact-match tags, no overlap)


def pie_file(kind, run):
    return HERE + "s3_shore_pie_bench_%s_%s.json" % (kind, run)


def write_verified(path, data):
    text = json.dumps(data, indent=1, sort_keys=True, default=str)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    with open(path, encoding="utf-8") as f:
        _require(f.read() == text, "READBACK|" + path)
    return path


def _path(o):
    return str(o.get_path_name()) if o is not None else None


def _tags(actor):
    return [str(t) for t in actor.get_editor_property("tags")]


def _rot_close(a, b, tol=0.01):
    return all(abs(((x - y) + 180.0) % 360.0 - 180.0) <= tol for x, y in zip(a, b))


def _rel(comp):
    t = comp.get_relative_transform()                                        # SceneComponent.h:464-465
    r = t.rotation.rotator()
    return {"loc": [float(t.translation.x), float(t.translation.y), float(t.translation.z)],
            "rpy": [float(r.roll), float(r.pitch), float(r.yaw)],
            "scale": [float(t.scale3d.x), float(t.scale3d.y), float(t.scale3d.z)]}


def _rel_matches(got, want, tol_cm=0.01):
    return (all(abs(a - b) <= tol_cm for a, b in zip(got["loc"], want["loc"])) and _rot_close(got["rpy"], want["rpy"])
            and all(abs(a - b) <= 1e-4 for a, b in zip(got["scale"], want["scale"])))


IDENTITY_REL = {"loc": [0.0, 0.0, 0.0], "rpy": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]}


def _deck_state(deck):
    smc = deck.static_mesh_component                                          # StaticMeshActor.h:25-26
    n = int(smc.get_num_materials())                                          # PrimitiveComponent.h:2325-2326
    return {"name": str(deck.get_name()), "class": str(deck.get_class().get_name()),
            "actor_hidden": bool(deck.get_editor_property("hidden")),         # Actor.h:364-365 bHidden [run: DRY]
            "tags": _tags(deck),
            "mesh": _path(smc.get_editor_property("static_mesh")),            # StaticMeshComponent.h:132-133
            "materials": [_path(smc.get_material(i)) for i in range(n)],      # PrimitiveComponent.h:1565-1566
            "rel": _rel(smc),
            "visible": bool(smc.is_visible()),                                # SceneComponent.h:852-853
            "hidden_in_game": bool(smc.get_editor_property("hidden_in_game")),  # SceneComponent.h:225-226
            "mobility": _enum_name(smc.get_editor_property("mobility"))}       # SceneComponent.h:302-303


def _v2_state(v2):
    comps = list(v2.get_components_by_class(unreal.PrimitiveComponent))       # Actor.h:3805-3807
    return {"name": str(v2.get_name()), "actor_hidden": bool(v2.get_editor_property("hidden")),
            "components": {str(c.get_name()): bool(c.is_visible()) for c in comps}}


def _pie_worlds():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    return ed.get_game_world(), ed.get_editor_world()                         # UnrealEditorSubsystem.h:49-52


def _by_name(world):
    out = {}
    for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):   # GameplayStatics.h:98
        out.setdefault(str(a.get_name()), []).append(a)
    return out


def _tagged(world):
    return [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if PIE_TAG in _tags(a)]


def _new_dirt(before, after):
    return {k: sorted(set(after[k]) - set(before[k])) for k in ("content", "maps")}


def _set_v2(v2, actor_hidden, comp_visible):
    """comp_visible: bool for all, or {name: bool} from the originals file."""
    v2.set_actor_hidden_in_game(bool(actor_hidden))                          # Actor.h:1921-1922
    for c in v2.get_components_by_class(unreal.PrimitiveComponent):
        want = comp_visible if isinstance(comp_visible, bool) else comp_visible.get(str(c.get_name()))
        if want is not None:
            c.set_visibility(bool(want), False)                               # SceneComponent.h:916-917


def _set_mesh(smc, mesh):
    """SetStaticMesh returns False when the mesh is unchanged [inf: engine .cpp not in the install], so only call it
    on a change; the read-back is the check either way."""
    if _path(smc.get_editor_property("static_mesh")) != _path(mesh):
        _require(smc.set_static_mesh(mesh), "SET_STATIC_MESH_RETURNED_FALSE|%s" % _path(mesh))  # StaticMeshComponent.h:449-450
    _require(_path(smc.get_editor_property("static_mesh")) == _path(mesh), "READBACK_MESH|%s" % _path(mesh))


def _set_deck(deck, mesh, materials, rel, tags, actor_hidden, visible):
    smc = deck.static_mesh_component
    _set_mesh(smc, mesh)
    for i, m in enumerate(materials):
        smc.set_material(i, m)                                                # PrimitiveComponent.h:1599-1600
    smc.set_relative_transform(unreal.Transform(location=unreal.Vector(*rel["loc"]),
                                                rotation=unreal.Rotator(roll=rel["rpy"][0], pitch=rel["rpy"][1],
                                                                        yaw=rel["rpy"][2]),
                                                scale=unreal.Vector(*rel["scale"])), False, False)  # SceneComponent.h:459-460
    deck.set_editor_property("tags", [unreal.Name(t) for t in tags])
    deck.set_actor_hidden_in_game(bool(actor_hidden))
    smc.set_visibility(bool(visible), False)


def run_bench_pie_apply(run, args):
    """PIE ONLY.  Never saves, never starts/ends PIE, never spawns or destroys.  Returns the applied record."""
    world, editor_world = _pie_worlds()
    _require(world is not None, "NO_PIE_WORLD|start a fresh PIE first (this script never starts PIE)")
    # Conductor 7 Oct [meas probe_worlds]: during PIE get_editor_world() returns None; identify PIE by its path.
    _require("/UEDPIE_" in str(_path(world)) and (editor_world is None or _path(world) != _path(editor_world)),
             "GAME_WORLD_IS_EDITOR_WORLD|%s" % _path(world))
    _require(WORLD.rsplit("/", 1)[1] in _path(world), "WRONG_PIE_MAP|%s" % _path(world))
    # Conductor 7 Oct [meas probe_worlds]: EditorAssetLibrary returns None during PIE; unreal.load_asset works.
    mesh, mi, master = unreal.load_asset(MESH), unreal.load_asset(MI), unreal.load_asset(MASTER)
    for p, o in ((MESH, mesh), (MI, mi), (MASTER, master)):
        _require(o is not None, "ASSET_MISSING|%s|run IMPORT and BUILD_MAT first" % p)
    _require(isinstance(mesh, unreal.StaticMesh), "MESH_CLASS|%s" % _path(mesh))
    _require(isinstance(mi, unreal.MaterialInterface), "MI_CLASS|%s" % _path(mi))
    try:  # an editor library: may be refused in PIE; BUILD_MAT already compiled + saved it in the editor
        ps = int(unreal.MaterialEditingLibrary.get_statistics(master).get_editor_property("num_pixel_shader_instructions"))
    except Exception:  # noqa: BLE001
        ps = -1
    _require(ps != 0, "PENDING_COMPILE|M_S3_ShoreGround has 0 pixel-shader instructions; rerun in ~30 s")  # MaterialEditingLibrary.h:609-610
    opath = pie_file("originals", run)
    _require(not os.path.isfile(opath), "RUN_ALREADY_APPLIED|use a new run id")
    stale = [str(a.get_name()) for a in _tagged(world)]
    _require(not stale, "STALE_BENCH_TAG_IN_PIE|%s" % stale)
    by = _actors_by_label(world)
    root, deck, v2 = _one(by, ROOT_LABEL), _one(by, DECK_LABEL), _one(by, V2_SAND_LABEL)
    _require(isinstance(deck, unreal.StaticMeshActor), "DECK_NOT_STATIC_MESH_ACTOR|%s" % deck.get_class().get_name())
    parent = deck.get_attach_parent_actor()                                    # Actor.h:3547-3548
    _require(parent is not None and _path(parent) == _path(root), "DECK_NOT_ON_ROOT|%s" % _path(parent))
    for w in (deck, v2, root):
        _require(_path(w.get_world()) == _path(world), "NOT_A_PIE_COPY|%s" % _path(w))
    children = [str(a.get_name()) for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                if a.get_attach_parent_actor() is not None and _path(a.get_attach_parent_actor()) == _path(deck)]
    _require(not children, "DECK_HAS_CHILDREN|%s|they would move with the identity transform" % children)
    dstate = _deck_state(deck)
    _require(dstate["mobility"].endswith("MOVABLE"), "DECK_NOT_MOVABLE|%s|SetStaticMesh refuses on Static" % dstate["mobility"])
    rl = root.get_actor_location()
    orig = {"run": run, "utc": datetime.datetime.utcnow().isoformat() + "Z", "pie_world": _path(world),
            "pie_real_time_s": float(unreal.GameplayStatics.get_real_time_seconds(world)),   # GameplayStatics.h:1246-1247
            "deferred_spawn_exposed": hasattr(unreal.GameplayStatics, "begin_deferred_actor_spawn_from_class"),
            "census_before": _census(), "root": {"name": str(root.get_name()), "world": [rl.x, rl.y, rl.z]},
            "deck": dstate, "v2": _v2_state(v2), "mesh": MESH, "mi": MI, "master_ps": ps}
    write_verified(opath, orig)                                    # ORIGINALS FIRST: nothing has been changed yet
    unreal.log("S3SHORE_BENCH_PIE_ORIGINALS|run=%s|path=%s" % (run, opath))
    applied = {"run": run, "complete": False, "borrowed": dstate["name"], "hidden": orig["v2"]["name"]}
    try:
        smc = deck.static_mesh_component
        _set_mesh(smc, mesh)
        n = int(smc.get_num_materials())                            # slot count of the NEW mesh
        _require(n >= 1, "NEW_MESH_HAS_NO_SLOTS")
        _set_deck(deck, mesh, [mi] * n, IDENTITY_REL, dstate["tags"] + [PIE_TAG], False, True)
        _set_v2(v2, True, False)
        got = _deck_state(deck)
        _require(got["mesh"] == _path(mesh), "READBACK_MESH|%s" % got["mesh"])
        _require(got["materials"] and all(m == _path(mi) for m in got["materials"]), "READBACK_MI|%s" % got["materials"])
        _require(_rel_matches(got["rel"], IDENTITY_REL), "READBACK_NOT_IDENTITY|%s" % got["rel"])
        _require(PIE_TAG in got["tags"] and not got["actor_hidden"] and got["visible"], "READBACK_DECK_FLAGS|%s" % got)
        dl = deck.get_actor_location()
        _require(max(abs(dl.x - rl.x), abs(dl.y - rl.y), abs(dl.z - rl.z)) <= 0.5,
                 "READBACK_NOT_AT_ROOT|deck=%s|root=%s" % ([dl.x, dl.y, dl.z], [rl.x, rl.y, rl.z]))
        vs = _v2_state(v2)
        _require(vs["actor_hidden"] and vs["components"] and not any(vs["components"].values()), "READBACK_V2|%s" % vs)
        applied.update(deck_after=got, v2_after=vs, census_after=_census())
        dirt = _new_dirt(orig["census_before"], applied["census_after"])
        _require(not dirt["content"] and not dirt["maps"], "EDITOR_PACKAGES_DIRTIED|%s" % dirt)
        applied["complete"] = True
        write_verified(pie_file("applied", run), applied)
        return applied
    except Exception:
        import traceback
        applied["error"] = traceback.format_exc()
        write_verified(pie_file("applied", run), applied)
        try:
            run_bench_pie_restore(run + "-AUTO", {"bench_run": run}, check_still=False)
        except Exception:  # noqa: BLE001
            unreal.log_error("S3SHORE_FAILED|run=%s|mode=BENCH_PIE_APPLY|reason=restore_after_error|%s" % (
                run, traceback.format_exc().replace("\n", " | ")))
        raise


def _still_check(world, orig, deck, v2, root):
    """BEFORE restoring: did our state hold until now (i.e. through the s3mg still)?  Does not change anything."""
    got = _deck_state(deck)
    vs = _v2_state(v2)
    dl, rl = deck.get_actor_location(), root.get_actor_location()
    reasons = []
    if got["mesh"] != orig["mesh_path"]:
        reasons.append("mesh=%s" % got["mesh"])
    if not got["materials"] or any(m != orig["mi_path"] for m in got["materials"]):
        reasons.append("materials")
    if not _rel_matches(got["rel"], IDENTITY_REL):
        reasons.append("rel=%s" % got["rel"])
    if max(abs(dl.x - rl.x), abs(dl.y - rl.y), abs(dl.z - rl.z)) > 0.5:
        reasons.append("deck_off_root")
    if got["actor_hidden"] or not got["visible"]:
        reasons.append("ground_hidden")
    if not vs["actor_hidden"] or any(vs["components"].values()):
        reasons.append("v2_visible")
    landed = all(abs(a - b) <= 1.0 for a, b in zip((rl.x, rl.y, rl.z), ROOT_LANDED_WORLD))
    return {"verdict": "STILL_STATE_HELD" if not reasons else "STILL_INVALID|" + ",".join(reasons),
            "root_now": [rl.x, rl.y, rl.z], "root_landed": landed, "deck_now": [dl.x, dl.y, dl.z]}


def run_bench_pie_restore(run, args, check_still=True):
    """PIE: put the borrowed deck copy and the v2 sand copy back from the originals FILE; idempotent.
    Returns {"noop": reason} when nothing needed doing (PIE gone / new PIE / already restored)."""
    bench_run = args.get("bench_run")
    _require(bench_run, "BENCH_RUN_MISSING")
    opath = pie_file("originals", bench_run)
    _require(os.path.isfile(opath), "NO_ORIGINALS|%s" % opath)
    orig = json.load(open(opath, encoding="utf-8"))
    _require(orig["run"] == bench_run, "RUN_MISMATCH|%s" % orig["run"])
    rpath = pie_file("restored", bench_run)
    world, _editor_world = _pie_worlds()
    if world is None:
        write_verified(rpath, {"run": run, "bench_run": bench_run, "pie": "gone", "census": _census()})
        return {"noop": "pie=gone (PIE copies died with PIE; editor world was never touched)", "record": rpath}
    if (_path(world) != orig["pie_world"]
            or float(unreal.GameplayStatics.get_real_time_seconds(world)) < orig["pie_real_time_s"]):
        write_verified(rpath, {"run": run, "bench_run": bench_run, "pie": "new_session", "census": _census()})
        return {"noop": "pie=new_session (the applied PIE ended; this PIE never had the bench)", "record": rpath}
    names = _by_name(world)
    rows = names.get(orig["deck"]["name"], [])
    _require(len(rows) == 1, "DECK_BY_NAME|%s|%d" % (orig["deck"]["name"], len(rows)))
    deck = rows[0]
    v2rows = names.get(orig["v2"]["name"], [])
    _require(len(v2rows) == 1, "V2_BY_NAME|%s|%d" % (orig["v2"]["name"], len(v2rows)))
    v2 = v2rows[0]
    root_rows = names.get(orig["root"]["name"], [])
    _require(len(root_rows) == 1, "ROOT_BY_NAME|%s" % orig["root"]["name"])
    rec = {"run": run, "bench_run": bench_run, "pie": "live"}
    before_deck, before_v2 = _deck_state(deck), _v2_state(v2)
    already = (before_deck["mesh"] == orig["deck"]["mesh"] and before_deck["materials"] == orig["deck"]["materials"]
               and _rel_matches(before_deck["rel"], orig["deck"]["rel"]) and before_deck["tags"] == orig["deck"]["tags"]
               and before_deck["actor_hidden"] == orig["deck"]["actor_hidden"]
               and before_deck["visible"] == orig["deck"]["visible"] and before_v2 == orig["v2"])
    if check_still and not already:
        rec["still"] = _still_check(world, dict(orig, mesh_path=_path(unreal.load_asset(MESH)),
                                                mi_path=_path(unreal.load_asset(MI))),
                                    deck, v2, root_rows[0])
        write_verified(rpath, rec)                                  # still evidence on disk before restoring
    if not already:
        eal = unreal.EditorAssetLibrary
        mesh = unreal.load_asset(orig["deck"]["mesh"].split(".")[0])
        mats = [unreal.load_asset(m.split(".")[0]) if m else None for m in orig["deck"]["materials"]]
        _require(mesh is not None and all(m is not None for m, p in zip(mats, orig["deck"]["materials"]) if p),
                 "ORIGINAL_ASSET_LOAD")
        _set_deck(deck, mesh, mats, orig["deck"]["rel"], orig["deck"]["tags"], orig["deck"]["actor_hidden"],
                  orig["deck"]["visible"])
        _set_v2(v2, orig["v2"]["actor_hidden"], orig["v2"]["components"])
    after_deck, after_v2 = _deck_state(deck), _v2_state(v2)
    problems = []
    for k in ("mesh", "materials", "tags", "actor_hidden", "visible", "hidden_in_game"):
        if after_deck[k] != orig["deck"][k]:
            problems.append("DECK_%s|%s" % (k.upper(), after_deck[k]))
    if not _rel_matches(after_deck["rel"], orig["deck"]["rel"]):
        problems.append("DECK_REL|%s" % after_deck["rel"])
    if after_v2 != orig["v2"]:
        problems.append("V2|%s" % after_v2)
    left = [str(a.get_name()) for a in _tagged(world)]
    if left:
        problems.append("OUR_TAG_LEFT|%s" % left)
    rec.update(deck_after=after_deck, v2_after=after_v2, problems=problems, census=_census(), already=already)
    write_verified(rpath, rec)
    _require(not problems, "RESTORE|" + json.dumps(problems[:10]))
    verdict = rec.get("still", {}).get("verdict", "unchecked")
    _require(not verdict.startswith("STILL_INVALID"), "RESTORED_BUT_STILL_INVALID|" + verdict)
    if already:
        return {"noop": "already_restored (state equals the originals file)", "record": rpath}
    return {"restored": True, "still": verdict, "root_landed": rec["still"]["root_landed"] if "still" in rec else None,
            "record": rpath}
# END_BENCH_PIE


# ----------------------------------------------------------------------------- APPLY / REVERT (7 Oct evening)
# BEGIN_APPLY   written OFFLINE 7 Oct evening, NOT RUN.  Patterns (run-proven 7 Oct): S3Millstone/s3_props_ue.py
# run_apply/_revert_record (record first, backup umap + rise, _set_flags pedestal hide, _add_reveal track copy,
# census-exact _save, fresh read-back after save).  Everything here uses unreal.load_asset (EditorAssetLibrary
# .load_asset returned None in PIE, measured 7 Oct) and refuses in PIE anyway.
#
# APPLY  args: mesh_name (default SM_S3_ShoreGround; Gary 7 Oct: SM_S3_ShoreGround_B), mi (default
#        MI_S3_ShoreGround_v2), reveal ("mirror_deck" default | "none").
#   gates: no PIE, editor world == WORLD, census CLEAN, no record file, no "S3 Shore Ground" label / TAG yet,
#          mesh + MI load, exactly one root / deck / v2 sand, sequences read.
#   reveal: the deck's and the v2 sand's bindings in LS_S3_HangarRise and LS_DevScene_03 are read and REPORTED.
#          mirror_deck: deck has ONE RISE binding with ONE visibility section -> that section is copied to the new
#          actor (actor hidden in game, like the millstone) and LS_S3_HangarRise is saved too; the S3 float hold
#          (s4_hangar_hold.py FLOAT, s3_hangar_float_hold_record.json) then needs re-applying -> REPORTED, not done.
#          deck has no visibility track anywhere -> no reveal (the ground rides the root like the deck did).
#          deck visibility only in LS_DevScene_03, several bindings/sections, or a sequence UNREAD -> REFUSED.
#   hides deck + v2 sand: actor hidden in game + EVERY primitive component visibility off + hidden in game (exact
#          originals in the record); component-level, so a rise visibility track on them cannot re-show them.
RISE = "/Game/InfinityStage/RigAtmos/LS_S3_HangarRise"
RISE_UASSET = PROJECT + "Content/InfinityStage/RigAtmos/LS_S3_HangarRise.uasset"
APPLY_DEFAULT_MI = ASSET_DIR + "/MI_S3_ShoreGround_v2"          # built live 7 Oct (4K sand)
HIDE_LABELS = (DECK_LABEL, V2_SAND_LABEL)
GUARD_TOL_CM = 2.0
FLOAT_HOLD_NOTE = ("the new actor got a COPY of the deck's LS_S3_HangarRise visibility track: re-apply the S3 float "
                   "hold (s4_hangar_hold.py FLOAT, record s3_hangar_float_hold_record.json) to include it - NOT done here")


def _guid(g):
    return str(unreal.GuidLibrary.conv_guid_to_string(g))


def _fps(seq):
    r = seq.get_display_rate()
    return r.numerator / float(r.denominator)


def _vis_sections(binding, fps):
    out = []
    for t in binding.get_tracks():
        if str(t.get_class().get_name()) != "MovieSceneVisibilityTrack":
            continue
        for s in t.get_sections():
            chans = list(s.get_all_channels())
            try:
                mode = _enum_name(s.get_completion_mode())
            except Exception:  # noqa: BLE001
                mode = _enum_name(s.get_editor_property("eval_options").get_editor_property("completion_mode"))
            out.append({"range_s": [float(s.get_start_frame_seconds()), float(s.get_end_frame_seconds())],
                        "completion_mode": mode, "channels": len(chans),
                        "keys": [[int(k.get_time().frame_number.value), bool(k.get_value())] for k in chans[0].get_keys()]
                        if len(chans) == 1 else None, "fps": fps})
    return out


def _bindings_for(seq, world, actor):
    """Bindings that resolve to `actor` (locate_bound_objects, run-proven) OR whose display name is its label / object
    name (sub-sequence possessables may not resolve outside their parent).  "UNREAD" when the sequence is missing."""
    if seq is None:
        return "UNREAD"
    want, names = _path(actor), (str(actor.get_actor_label()), str(actor.get_name()))
    fps = _fps(seq)
    rows = []
    for b in seq.get_bindings():
        try:
            hit = any(_path(o) == want for o in seq.locate_bound_objects(b, world))
        except Exception:  # noqa: BLE001
            hit = False
        if hit or str(b.get_display_name()) in names:
            rows.append({"guid": _guid(b.get_id()), "resolved": hit,
                         "tracks": [str(t.get_class().get_name()) for t in b.get_tracks()],
                         "visibility_sections": _vis_sections(b, fps)})
    return rows


def plan_reveal(reads, mode="mirror_deck"):
    """Pure (harness-tested).  reads = {"rise": {label: rows|"UNREAD"}, "scene": {label: rows|"UNREAD"}}.
    Returns {"mode", "copy": section|None, "copy_from_guid", "report": {...}, "float_hold_reapply_needed"}."""
    report = {}
    for label in HIDE_LABELS:
        r = {}
        for k in ("rise", "scene"):
            rows = reads.get(k, {}).get(label, "UNREAD")
            r[k] = rows if rows == "UNREAD" else [{"guid": x["guid"], "tracks": x["tracks"],
                                                   "visibility_sections": len(x["visibility_sections"])} for x in rows]
        report[label] = r
    out = {"mode": mode, "copy": None, "copy_from_guid": None, "report": report, "float_hold_reapply_needed": False}
    if mode == "none":
        return out
    _require(mode == "mirror_deck", "REVEAL_MODE|%r" % mode)
    rise, scene = reads.get("rise", {}).get(DECK_LABEL, "UNREAD"), reads.get("scene", {}).get(DECK_LABEL, "UNREAD")
    _require(rise != "UNREAD" and scene != "UNREAD", "SEQUENCE_UNREAD|rise=%s|scene=%s|use reveal=none to override" % (
        rise == "UNREAD", scene == "UNREAD"))
    rv = [x for x in rise if x["visibility_sections"]]
    sv = [x for x in scene if x["visibility_sections"]]
    _require(not sv, "DECK_REVEAL_IN_SCENE_SEQUENCE_UNSUPPORTED|%s" % [x["guid"] for x in sv])
    if not rv:
        return out
    _require(len(rv) == 1 and len(rv[0]["visibility_sections"]) == 1, "DECK_REVEAL_SHAPE|%s" % rv)
    sec = rv[0]["visibility_sections"][0]
    _require(sec["channels"] == 1 and sec["keys"], "DECK_REVEAL_KEYS|%s" % sec)
    out.update(copy=sec, copy_from_guid=rv[0]["guid"], float_hold_reapply_needed=True)
    return out


def _prims(actor):
    return sorted(actor.get_components_by_class(unreal.PrimitiveComponent), key=lambda c: str(c.get_name()))


def _hide_state(actor):
    return {"path": _path(actor), "label": str(actor.get_actor_label()),
            "actor_hidden": bool(actor.get_editor_property("hidden")),                       # Actor.h bHidden
            "components": {str(c.get_name()): {"visible": bool(c.is_visible()),              # SceneComponent.h:852
                                               "hidden_in_game": bool(c.get_editor_property("hidden_in_game"))}
                           for c in _prims(actor)}}


def hidden_target(state):
    return dict(state, actor_hidden=True,
                components={k: {"visible": False, "hidden_in_game": True} for k in state["components"]})


def _set_hide_state(actor, want):
    actor.modify()
    actor.set_actor_hidden_in_game(bool(want["actor_hidden"]))                              # Actor.h:1921
    for c in _prims(actor):
        w = want["components"].get(str(c.get_name()))
        _require(w is not None, "COMPONENT_NOT_IN_RECORD|%s|%s" % (want["label"], c.get_name()))
        c.modify()
        c.set_visibility(bool(w["visible"]), False)                                          # SceneComponent.h:916
        c.set_hidden_in_game(bool(w["hidden_in_game"]), False)                               # SceneComponent.h:932-933
    got = _hide_state(actor)
    _require(got == want, "HIDE_READBACK|%s|%s" % (want["label"], json.dumps(got)))


def _by_path_in(world, path):
    rows = [a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor) if _path(a) == path]
    _require(len(rows) <= 1, "PATH_COUNT|%s|%d" % (path, len(rows)))
    return rows[0] if rows else None


def _ground_state(actor):
    smc = actor.static_mesh_component
    parent = actor.get_attach_parent_actor()
    return {"path": _path(actor), "label": str(actor.get_actor_label()), "parent": _path(parent), "tags": _tags(actor),
            "mesh": (_path(smc.get_editor_property("static_mesh")) or "").split(".")[0],
            "mi0": (_path(smc.get_material(0)) or "").split(".")[0], "rel": _rel(smc),
            "mobility": _enum_name(smc.get_editor_property("mobility")),
            "collision": _enum_name(smc.get_collision_enabled()),                            # PrimitiveComponent.h:2618-2619
            "actor_hidden": bool(actor.get_editor_property("hidden")), "visible": bool(smc.is_visible())}


def _apply_world():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    _require(ed.get_game_world() is None, "PIE_ACTIVE|APPLY/REVERT are editor-world only")
    world = ed.get_editor_world()
    _require(world is not None and str(world.get_path_name()).startswith(WORLD), "WRONG_WORLD|%s" % _path(world))
    return world


def _backup_files(run, record_path):
    d = BACKUP_ROOT + run
    os.makedirs(d)                                                    # refuses an existing folder
    out = {}
    for src in (UMAP, RISE_UASSET, record_path):
        dst = os.path.join(d, os.path.basename(src))
        shutil.copy2(src, dst)
        _require(sha256_file(dst) == sha256_file(src), "BACKUP_HASH|%s" % dst)
        out[os.path.basename(src)] = sha256_file(dst)
    return {"dir": d, "sha256": out}


def _seq_save(world, want_content):
    c = _census()
    _require(c == {"content": sorted(want_content), "maps": [WORLD]}, "DIRTY_SCOPE|%s" % json.dumps(c))
    _require(not [k for k in _actors_by_label(world) if k.startswith("ZZ_")], "ZZ_ACTORS_PRESENT")
    for p in want_content:
        _require(unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=False), "SAVE|" + p)
    _require(unreal.EditorLoadingAndSavingUtils.save_map(world, WORLD), "SAVE_MAP")
    after = _census()
    _require(after == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % json.dumps(after))


def _add_reveal_copy(world, actor, section):
    rise = unreal.load_asset(RISE)
    _require(abs(_fps(rise) - section["fps"]) < 1e-6, "RISE_FPS_CHANGED")
    b = rise.add_possessable(actor)
    _require(b is not None and b.is_valid(), "ADD_POSSESSABLE")
    t = b.add_track(unreal.MovieSceneVisibilityTrack)
    _require(t is not None, "ADD_VISIBILITY_TRACK")
    s = t.add_section()
    s.set_range_seconds(section["range_s"][0], section["range_s"][1])
    s.set_completion_mode(getattr(unreal.MovieSceneCompletionMode, section["completion_mode"]))
    ch = list(s.get_all_channels())
    _require(len(ch) == 1, "NEW_SECTION_CHANNELS|%d" % len(ch))
    for frame, value in section["keys"]:
        ch[0].add_key(unreal.FrameNumber(int(frame)), bool(value), time_unit=unreal.MovieSceneTimeUnit.DISPLAY_RATE)
    return _guid(b.get_id())


def _verify_reveal_copy(world, guid, actor, section):
    rise = unreal.load_asset(RISE)
    rows = [b for b in rise.get_bindings() if _guid(b.get_id()) == guid]
    _require(len(rows) == 1, "REVEAL_BINDING_COUNT|%d" % len(rows))
    _require([_path(o) for o in rise.locate_bound_objects(rows[0], world)] == [_path(actor)], "REVEAL_RESOLVES")
    got = _vis_sections(rows[0], _fps(rise))
    _require(len(got) == 1 and got[0]["keys"] == [[int(f), bool(v)] for f, v in section["keys"]]
             and got[0]["completion_mode"] == section["completion_mode"]
             and all(abs(a - b) <= 1.0 / got[0]["fps"] + 1e-6 for a, b in zip(got[0]["range_s"], section["range_s"])),
             "REVEAL_READBACK|%s" % got)


def _remove_reveal_copy(world, guid, actor_path):
    rise = unreal.load_asset(RISE)
    rows = [b for b in rise.get_bindings() if _guid(b.get_id()) == guid]
    if not rows:
        return False
    _require([_path(o) for o in rise.locate_bound_objects(rows[0], world)] == [actor_path], "REVERT_BINDING_TARGET")
    rows[0].remove()                                                  # returns None even on success: re-list
    _require(not [b for b in rise.get_bindings() if _guid(b.get_id()) == guid], "REVERT_BINDING_SURVIVED")
    return True


def _expected_ground(record):
    p = record["plan"]
    return {"label": ACTOR_LABEL, "parent": p["root_path"], "tags": [TAG], "mesh": p["mesh"], "mi0": p["mi"],
            "mobility": "MOVABLE", "collision": "NO_COLLISION", "actor_hidden": bool(p["reveal"]["copy"]),
            "visible": True}


def _verify_applied(world, record):
    a = _by_path_in(world, record["actor_path"])
    _require(a is not None, "ACTOR_MISSING|%s" % record["actor_path"])
    got = _ground_state(a)
    for k, v in _expected_ground(record).items():
        _require(got[k] == v, "READBACK_%s|got=%r|want=%r" % (k.upper(), got[k], v))
    _require(_rel_matches(got["rel"], IDENTITY_REL), "READBACK_NOT_IDENTITY|%s" % got["rel"])
    for label in HIDE_LABELS:
        h = _by_path_in(world, record["before"][label]["path"])
        _require(h is not None, "HIDDEN_ACTOR_MISSING|%s" % label)
        _require(_hide_state(h) == record["after"][label], "READBACK_HIDDEN|%s|%s" % (label, json.dumps(_hide_state(h))))
    if record.get("reveal_binding_guid"):
        _verify_reveal_copy(world, record["reveal_binding_guid"], a, record["plan"]["reveal"]["copy"])
    root = _by_path_in(world, record["plan"]["root_path"])
    box = _bounds_local(root, a)
    lo, hi = LANDED_LOCAL_BOX["min"], LANDED_LOCAL_BOX["max"]
    _require(all(lo[i] - GUARD_TOL_CM <= box["min"][i] and box["max"][i] <= hi[i] + GUARD_TOL_CM for i in range(3)),
             "OUTSIDE_LANDED_BOX|%s" % box)                           # memory puss-level-saved-landed-frame-trap
    return dict(got, local_box=box)


def _undo(world, record):
    """In-memory undo of whatever the record says was done (reveal binding, actor, flags).  No save.  Idempotent."""
    done = []
    a = _by_path_in(world, record["actor_path"]) if record.get("actor_path") else None
    if record.get("reveal_binding_guid") and a is not None:
        if _remove_reveal_copy(world, record["reveal_binding_guid"], record["actor_path"]):
            done.append("reveal_removed")
    if a is not None:
        _require(str(a.get_actor_label()) == ACTOR_LABEL and TAG in _tags(a), "DESTROY_TARGET|%s" % _path(a))
        _require(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(a), "DESTROY")
        _require(_by_path_in(world, record["actor_path"]) is None, "DESTROY_SURVIVED")
        done.append("actor_destroyed")
    for label in HIDE_LABELS:
        before = record.get("before", {}).get(label)
        h = _by_path_in(world, before["path"]) if before else None
        if h is not None and _hide_state(h) != before:
            _set_hide_state(h, before)
            done.append("restored|" + label)
    return done


def run_apply(run, args):
    world = _apply_world()
    _require(_census() == {"content": [], "maps": []}, "DIRTY_EDITOR|%s" % json.dumps(_census()))
    _require(not os.path.isfile(RECORD), "RECORD_EXISTS|%s|REVERT first or move it" % RECORD)
    mesh_p, mi_p = mesh_path_of(args), str(args.get("mi") or APPLY_DEFAULT_MI)
    mesh, mi = unreal.load_asset(mesh_p), unreal.load_asset(mi_p)
    _require(isinstance(mesh, unreal.StaticMesh), "MESH_MISSING|%s|run IMPORT first" % mesh_p)
    _require(isinstance(mi, unreal.MaterialInterface), "MI_MISSING|%s" % mi_p)
    by = _actors_by_label(world)
    _require(not by.get(ACTOR_LABEL), "ACTOR_EXISTS|%s" % ACTOR_LABEL)
    tagged = [str(a.get_name()) for rows in by.values() for a in rows if TAG in _tags(a)]
    _require(not tagged, "TAG_EXISTS|%s" % tagged)
    root, deck, v2 = _one(by, ROOT_LABEL), _one(by, DECK_LABEL), _one(by, V2_SAND_LABEL)
    seqs = {"rise": unreal.load_asset(RISE), "scene": unreal.load_asset(SEQUENCE_PATH)}
    reads = {k: {DECK_LABEL: _bindings_for(s, world, deck), V2_SAND_LABEL: _bindings_for(s, world, v2)}
             for k, s in seqs.items()}
    reveal = plan_reveal(reads, str(args.get("reveal") or "mirror_deck"))
    dp = deck.get_attach_parent_actor()
    try:
        folder = str(deck.get_folder_path())                          # Actor.h:2757-2758
    except Exception:  # noqa: BLE001
        folder = None
    folder = None if folder in ("", "None") else folder
    rl = root.get_actor_location()
    before = {DECK_LABEL: _hide_state(deck), V2_SAND_LABEL: _hide_state(v2)}
    record = {"run": run, "utc": datetime.datetime.utcnow().isoformat() + "Z", "world": WORLD, "rise": RISE,
              "census_before": _census(), "saved": False, "applied": False, "actor_path": None,
              "reveal_binding_guid": None,
              "plan": {"mesh": mesh_p, "mi": mi_p, "root_path": _path(root), "root_world": [rl.x, rl.y, rl.z],
                       "deck_parent": _path(dp), "folder": folder, "reveal": reveal},
              "before": before, "after": {k: hidden_target(v) for k, v in before.items()}, "sequence_reads": reads}
    with open(RECORD, "x", encoding="utf-8") as h:                     # RECORD FIRST (exclusive create)
        json.dump(record, h, indent=1, default=str)
    unreal.log("S3SHORE_RECORD|run=%s|path=%s" % (run, RECORD))
    record["backup"] = _backup_files(run, RECORD)
    _write(RECORD, record)
    try:
        eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        a = eas.spawn_actor_from_class(unreal.StaticMeshActor, root.get_actor_location(), root.get_actor_rotation(),
                                       False)                         # EditorActorSubsystem.h:228
        _require(a is not None, "SPAWN_FAILED")
        record["actor_path"] = _path(a)
        _write(RECORD, record)
        a.set_actor_label(ACTOR_LABEL)
        smc = a.static_mesh_component
        smc.set_mobility(unreal.ComponentMobility.MOVABLE)
        _set_mesh(smc, mesh)
        smc.set_material(0, mi)
        smc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)          # PrimitiveComponent.h:2025-2026
        a.set_editor_property("tags", [unreal.Name(TAG)])
        if folder:
            a.set_folder_path(folder)
        a.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE,
                          unreal.AttachmentRule.KEEP_RELATIVE, False)
        smc.set_relative_transform(unreal.Transform(), False, False)
        a.set_actor_hidden_in_game(bool(reveal["copy"]))
        if reveal["copy"]:
            record["reveal_binding_guid"] = _add_reveal_copy(world, a, reveal["copy"])
            _write(RECORD, record)
        for label, h in ((DECK_LABEL, deck), (V2_SAND_LABEL, v2)):
            _set_hide_state(h, record["after"][label])
        _verify_applied(world, record)
        _seq_save(world, [RISE] if record["reveal_binding_guid"] else [])
        record["saved"] = True
        _write(RECORD, record)
    except Exception as exc:
        record["error"] = repr(exc)
        try:
            record["auto_undo"] = _undo(world, record)
            record["census_after_undo"] = _census()
        except Exception as exc2:  # noqa: BLE001
            record["auto_undo_error"] = repr(exc2)
        _write(RECORD, record)
        os.replace(RECORD, RECORD + ".failed-" + run)                 # a failed APPLY leaves no live record
        raise
    record["readback"] = _verify_applied(world, record)               # fresh lookups, after the save
    record["census_after"] = _census()
    _require(record["census_after"] == {"content": [], "maps": []}, "DIRTY_AFTER_READBACK|%s" % record["census_after"])
    record["applied"] = True
    _write(RECORD, record)
    return {"actor": record["actor_path"], "mesh": mesh_p, "mi": mi_p, "reveal_guid": record["reveal_binding_guid"],
            "float_hold_reapply_needed": reveal["float_hold_reapply_needed"], "reveal_report": reveal["report"],
            "backup": record["backup"]["dir"], "local_box": record["readback"]["local_box"]}


def run_revert(run, args):
    world = _apply_world()
    _require(_census() == {"content": [], "maps": []}, "DIRTY_EDITOR|%s" % json.dumps(_census()))
    _require(os.path.isfile(RECORD), "NO_RECORD|%s" % RECORD)
    record = json.load(open(RECORD, encoding="utf-8"))
    _require(record.get("saved") and record.get("actor_path"), "RECORD_NOT_SAVED")
    _verify_applied(world, record)                                    # drift since APPLY -> refuse before mutating
    backup = _backup_files(run + "-REVERT", RECORD)
    done = _undo(world, record)
    _seq_save(world, [RISE] if record.get("reveal_binding_guid") else [])
    by = _actors_by_label(world)
    _require(_by_path_in(world, record["actor_path"]) is None and not by.get(ACTOR_LABEL), "REVERT_ACTOR_PRESENT")
    for label in HIDE_LABELS:
        got = _hide_state(_by_path_in(world, record["before"][label]["path"]))
        _require(got == record["before"][label], "REVERT_FLAGS|%s|%s" % (label, json.dumps(got)))
    if record.get("reveal_binding_guid"):
        rise = unreal.load_asset(RISE)
        _require(not [b for b in rise.get_bindings() if _guid(b.get_id()) == record["reveal_binding_guid"]],
                 "REVERT_BINDING_PRESENT")
    _require(_census() == {"content": [], "maps": []}, "DIRTY_AFTER_REVERT|%s" % _census())
    os.replace(RECORD, RECORD + ".reverted-" + run)
    return {"done": done, "backup": backup["dir"], "record": RECORD + ".reverted-" + run}
# END_APPLY
# VERIFY: still REFUSED by the runner (queue SavedMasterMatchesShow + SceneCutBindingsResolve after a run-id marker
# by hand: memory tk-saved-master-stage-is-fake).
