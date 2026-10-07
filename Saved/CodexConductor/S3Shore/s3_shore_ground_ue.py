"""S3 shore ground -- editor-side DRY / IMPORT / BUILD_MAT / BENCH / APPLY / REVERT / VERIFY.

DRAFT, written 7 Oct 2026 OFFLINE.  NEVER RUN.  Unreal was closed/building; MCP not called.
Plan + live reads: Docs/Conductor/S3_SHORE_GROUND_PREP_2026-10-07.md (sections 4-5).

Args Saved/CodexConductor/S3Shore/s3_shore_ground_args.json:
  {"mode": "DRY"|"IMPORT"|"BUILD_MAT"|"BENCH"|"APPLY"|"REVERT"|"VERIFY",
   "confirm": "<MODE> S3SHORE", "run": "<id>",
   "hide_deck": true, "hide_v2_sand": true}

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
  APPLY      backup umap -> Backups/PreS3ShoreGround-<run>; spawn "S3 Shore Ground" (tag RigAtmos.S3ShoreGround),
             attach KEEP_RELATIVE to S3 Hangar Root, relative identity, mobility = the deck's measured mobility;
             hide deck and v2 sand (visible False + hidden_in_game True, modify() first); save census-exact
             (map + the 3 new assets only); read back from the saved state; landed-box guard.
  REVERT     destroy the recorded actor (by path), restore deck / v2 sand flags from the record, save the map.
             Assets stay.
  VERIFY     read-only end state; then queue InfinityStage.Editor.SavedMasterMatchesShow and
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


def _pipeline():
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
    p.set_editor_property("asset_name", "SM_S3_ShoreGround")
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


def run_import(run):
    eal = unreal.EditorAssetLibrary
    _require(_census() == {"content": [], "maps": []}, "DIRTY_EDITOR|%s" % _census())
    _require(not eal.does_asset_exist(MESH), "MESH_EXISTS")
    man = json.load(open(MANIFEST, encoding="utf-8"))
    _require(sha256_file(FBX) == man["fbx_sha256"], "FBX_HASH")
    before = set(eal.list_assets(ASSET_DIR, recursive=True)) if eal.does_directory_exist(ASSET_DIR) else set()
    task = unreal.AssetImportTask()
    for k, v in (("filename", FBX), ("destination_path", ASSET_DIR), ("destination_name", "SM_S3_ShoreGround"),
                 ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    ov, settings = _pipeline()
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
    _write(RECORD + ".import", rec)
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


# APPLY / REVERT / VERIFY: REFUSED by the runner.  Shape (unchanged): census clean -> backup umap (sha-checked) ->
#   spawn "S3 Shore Ground" + attach KEEP_RELATIVE identity, mobility MOVABLE (deck measured MOVABLE, DRY 181646)
#   -> deck + v2 sand hidden (modify(); visible False; hidden_in_game True) -> save census-exact
#   {"content": [], "maps": [WORLD]} -> read back from the saved state -> landed-box guard against the LIVE root
#   -> S3SHORE_APPLY_OK only after every assert.  Figures / pedestal / rocks are NOT moved (Gary re-arranges).
