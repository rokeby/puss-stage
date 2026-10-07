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
    "SandTileM": 1.5, "MudTileM": 2.0, "MossTileM": 1.2,   # metres per texture repeat (UV0 is in metres)
    "WetDarken": 0.55, "WetRoughness": 0.12, "PuddleRoughness": 0.04, "PuddleFromG": 0.85,
    "MossStrength": 1.0, "NormalStrength": 1.0, "MudBlendContrast": 4.0,
}


def graph_spec():
    """Node list and wiring for M_S3_ShoreGround (pure data; offline-testable).

    VertexColor: R = mud weight, G = wetness, B = moss, A = reserved (1).
    BaseColor = lerp(lerp(Sand, Mud, Rc), Moss, B*MossStrength) * lerp(1, WetDarken, G)
      where Rc = height-aware contrast of R (MudBlendContrast) so hand-painted R edges stay crisp.
    Roughness = lerp(lerp(lerp(SandR, MudR, Rc), 0.8, B), WetRoughness, G), then PuddleRoughness above PuddleFromG.
    Normal    = lerp(lerp(SandN, MudN, Rc), MossN, B), flattened toward (0,0,1) by G (standing water).
    UVs: UV0 / <X>TileM (mesh UV0 is metres in hangar-local space, so tiling rides with the rising box).
    """
    return {
        "flags": {"blend_mode": "BLEND_OPAQUE", "shading_model": "MSM_DEFAULT_LIT", "used_with_nanite": True,
                  "two_sided": False},
        "textures": dict(TEX),
        "scalars": dict(SCALARS),
        "vertex_channels": {"R": "mud", "G": "wetness", "B": "moss", "A": "reserved"},
    }


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


def _pipeline():
    """Interchange override for one static mesh. Property names are from s3_beach_v2.py:666-699 (run 4 Oct);
    the Nanite / vertex-colour property names below are UNVERIFIED -> DRY must probe them read-only first."""
    p = unreal.InterchangeGenericAssetsPipeline()
    common = p.get_editor_property("common_meshes_properties")
    mesh = p.get_editor_property("mesh_pipeline")
    mat = p.get_editor_property("material_pipeline")
    wanted = [(mat, "import_materials", False), (mesh, "import_static_meshes", True),
              (mesh, "import_skeletal_meshes", False), (mesh, "build_nanite", True),          # UNVERIFIED name
              (common, "import_lods", False), (common, "vertex_color_import_option",          # UNVERIFIED name
                                                  unreal.InterchangeVertexColorImportOption.IVCIO_REPLACE)]
    for obj, prop, val in wanted:
        obj.set_editor_property(prop, val)
    for obj, prop, val in wanted:
        _require(obj.get_editor_property(prop) == val, "PIPELINE_READBACK|" + prop)
    tex = mat.get_editor_property("texture_pipeline")
    if tex:
        tex.set_editor_property("import_textures", False)
    ov = unreal.InterchangePipelineStackOverride()
    ov.add_pipeline(p)
    return ov


def run_import(run):
    eal = unreal.EditorAssetLibrary
    _require(_census() == {"content": [], "maps": []}, "DIRTY_EDITOR")
    _require(not eal.does_asset_exist(MESH), "MESH_EXISTS")
    man = json.load(open(MANIFEST, encoding="utf-8"))
    _require(sha256_file(FBX) == man["fbx_sha256"], "FBX_HASH")
    before = set(eal.list_assets(ASSET_DIR, recursive=True)) if eal.does_directory_exist(ASSET_DIR) else set()
    task = unreal.AssetImportTask()
    for k, v in (("filename", FBX), ("destination_path", ASSET_DIR), ("destination_name", "SM_S3_ShoreGround"),
                 ("automated", True), ("replace_existing", False), ("save", False)):
        task.set_editor_property(k, v)
    task.set_editor_property("options", _pipeline())
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(MESH)
    _require(isinstance(mesh, unreal.StaticMesh), "IMPORT_FAILED|%s" % list(task.imported_object_paths))
    new = sorted(set(eal.list_assets(ASSET_DIR, recursive=True)) - before)
    _require([n.split(".")[0] for n in new] == [MESH], "STRAY_ASSETS|%s" % new)
    _require(mesh.get_num_lods() == 1, "LODS|%d" % mesh.get_num_lods())
    nanite = mesh.get_editor_property("nanite_settings").get_editor_property("enabled")
    _require(nanite, "NANITE_OFF")
    bb = mesh.get_bounding_box()
    exp = man["expected_ue_local_bounds_cm"]
    got = {"min": [bb.min.x, bb.min.y, bb.min.z], "max": [bb.max.x, bb.max.y, bb.max.z]}
    for k in ("min", "max"):
        for i in range(3):
            _require(abs(got[k][i] - exp[k][i]) <= 0.5, "BOUNDS|%s|got=%s|exp=%s (Y swapped => mirrored)" % (k, got, exp))
    # calibration colours: read the 4 skirt-bottom corner vertex instances (API probed read-only in DRY first)
    # TODO before first run: probe the vertex-instance colour getter on StaticMeshDescription read-only; until
    # then IMPORT records the calibration as UNREAD and the BENCH stills are the colour check.
    calib = [{"want": c, "got": None, "status": "UNREAD_API_UNVERIFIED"} for c in man["calibration_vertices"]]
    _require(_census() == {"content": [MESH], "maps": []}, "DIRTY_SCOPE|%s" % _census())
    _require(eal.save_asset(MESH, only_if_is_dirty=False), "SAVE_MESH")
    _require(_census() == {"content": [], "maps": []}, "POST_SAVE_DIRTY|%s" % _census())
    rec = {"run": run, "mesh": MESH, "bounds": got, "nanite": True, "calibration": calib}
    _write(RECORD + ".import", rec)
    return rec


def run_bench(run, args):
    """Reversible.  Originals FIRST to a file.  No save anywhere in this function."""
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    by = _actors_by_label(world)
    root = _one(by, ROOT_LABEL)
    deck = _one(by, DECK_LABEL)
    v2 = by.get(V2_SAND_LABEL, [None])[0]
    census0 = _census()
    originals = {"run": run, "census_before": census0,
                 "deck_visible": bool(deck.static_mesh_component.is_visible()),
                 "v2_visible": bool(v2.static_mesh_component.is_visible()) if v2 else None}
    path = HERE + "s3_shore_bench_originals_%s.json" % run
    _write(path, originals)
    unreal.log("S3SHORE_BENCH_ORIGINALS|run=%s|%s" % (run, path))
    spawned = None
    try:
        spawned = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(
            unreal.StaticMeshActor, root.get_actor_location(), root.get_actor_rotation(), transient=True)
        spawned.set_actor_label(BENCH_LABEL)
        smc = spawned.static_mesh_component
        smc.set_mobility(unreal.ComponentMobility.MOVABLE)
        smc.set_static_mesh(unreal.load_asset(MESH))
        smc.set_material(0, unreal.load_asset(MI))
        spawned.attach_to_actor(root, "", unreal.AttachmentRule.KEEP_RELATIVE, unreal.AttachmentRule.KEEP_RELATIVE,
                                unreal.AttachmentRule.KEEP_RELATIVE, False)
        spawned.root_component.set_relative_transform(unreal.Transform(), False, False)
        deck.static_mesh_component.set_visibility(False)
        if v2:
            v2.static_mesh_component.set_visibility(False)
        originals["census_after_set"] = _census()                    # MEASURE: does set_visibility dirty?
        # stills: reuse Saved/CodexConductor/s3_beach_marble_stills.py capture helper per S3 shot camera (TODO wire)
    finally:
        if spawned is not None:
            spawned.destroy_actor()
        deck.static_mesh_component.set_visibility(originals["deck_visible"])
        if v2:
            v2.static_mesh_component.set_visibility(originals["v2_visible"])
    _require(bool(deck.static_mesh_component.is_visible()) == originals["deck_visible"], "RESTORE_DECK")
    originals["census_end"] = _census()
    _write(path, originals)
    return originals


# APPLY / REVERT / VERIFY follow s3_sack_install.py:_save/_backup_umap and s3_beach_v2.py APPLY verbatim in shape:
#   census clean -> backup umap (sha-checked) -> spawn + attach (KEEP_RELATIVE, identity) -> deck/v2 hide with modify()
#   -> _save(planned={"content": [MESH, MASTER, MI] if newly created else [], "maps": [WORLD]})
#   -> read back from the saved state: parent == S3 Hangar Root, relative transform identity (+-0.01 cm / deg),
#      mesh/MI paths, deck+v2 hidden, world AABB inside LANDED_LOCAL_BOX composed with the LIVE root transform
#   -> S3SHORE_APPLY_OK|run=.. only after every assert.  Left unwritten on purpose until the DRY live reads exist.
