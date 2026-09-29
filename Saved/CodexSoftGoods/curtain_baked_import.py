"""Import the approved Opening drop bake (final2_stage_v2) into Unreal (29 Sep; Gary: "place the opening curtain where
it's supposed to be (at the front and also in between transitions)"). CONTENT ONLY: no level, Show or sequence edits.

Creates, all under /Game/Scenes/Curtain/Baked and nothing else (replaced in place on a re-run):
  SM_CurtainDrape_Hanging   the first exported frame (the settled hang) as a static mesh: the axis check, and the
                            stand-in drape for the camera-following transition rigs
  SM_CurtainDrape_Pile      the last frame (the settled pile) as a static mesh: the axis check (asymmetric extents)
  GC_CurtainDrop_Opening    the whole show window (Blender 120-450 at 30 fps, release 1.0 s in) as a GeometryCache
  MI_CurtainVelvet_DeepRed_Drop   velvet for the drop mesh (PatternWidthM 35.529, DropM 10, SeamWidthM 1.37)
and sets "Used with Geometry Cache" on M_CurtainVelvet (Soft goods' own master; copied to Backups/ first).

AXIS CHECK (before the slow cache import): Blender x = UE Y/100, y = UE X/100, z = UE Z/100, curtain line at the origin.
The bake's own extents (final2_stage_v2.json) give, in UE cm, hanging frame X -103.7..+69.0, Y +-888.5; pile frame
X -468.6..+508.4, Y -1084.6..+1167.6. The pile is asymmetric on both axes, so a flip or swap cannot pass.

Crash rules (puss-mcp-python-crashes-the-editor): everything inside main(), no UE objects at module level.
Guards: expected world, no PIE, nothing dirty at start. Ends on PUSS_SOFTGOODS_BAKED_IMPORT_SUCCESS or _STOPPED.
"""
import datetime
import json
import os
import shutil

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
DEST = "/Game/Scenes/Curtain/Baked"
VELVET_MASTER = "/Game/Scenes/Curtain/Chaos/Materials/M_CurtainVelvet"
VELVET_PARENT = "/Game/Scenes/Curtain/Chaos/Materials/MI_CurtainVelvet_DeepRed"
# Conversion: scale m -> cm with the Maya-style Y mirror, roll 90 (Y-up Alembic -> Z-up), then yaw 90 so that
# Blender y (upstage) lands on UE X and Blender x (across) on UE Y. Verified by the extents check, not assumed.
CONV_SCALE = (100.0, -100.0, 100.0)
CONV_ROT = (90.0, 0.0, 90.0)
EXPECT = {
    "SM_CurtainDrape_Hanging": {"x": (-103.7, 69.0), "y": (-888.5, 888.5)},
    "SM_CurtainDrape_Pile": {"x": (-468.6, 508.4), "y": (-1084.6, 1167.6)},
}
TOL_CM = 4.0


def project():
    return unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())


def dirty():
    return sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()) + \
        sorted(p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())


def settings(kind, frame_start, frame_end):
    s = unreal.AbcImportSettings()
    s.set_editor_property("import_type", kind)
    conv = unreal.AbcConversionSettings()
    conv.set_editor_property("preset", unreal.AbcConversionPreset.CUSTOM)
    conv.set_editor_property("scale", unreal.Vector(*CONV_SCALE))
    conv.set_editor_property("rotation", unreal.Vector(*CONV_ROT))
    conv.set_editor_property("flip_u", False)
    conv.set_editor_property("flip_v", True)
    s.set_editor_property("conversion_settings", conv)
    samp = unreal.AbcSamplingSettings()
    samp.set_editor_property("sampling_type", unreal.AlembicSamplingType.PER_FRAME)
    samp.set_editor_property("frame_start", frame_start)
    samp.set_editor_property("frame_end", frame_end)
    samp.set_editor_property("skip_empty", False)
    s.set_editor_property("sampling_settings", samp)
    mat = unreal.AbcMaterialSettings()
    mat.set_editor_property("create_materials", False)
    mat.set_editor_property("find_materials", False)
    s.set_editor_property("material_settings", mat)
    if kind == unreal.AlembicImportType.GEOMETRY_CACHE:
        gc = unreal.AbcGeometryCacheSettings()
        gc.set_editor_property("flatten_tracks", True)
        gc.set_editor_property("apply_constant_topology_optimizations", True)
        gc.set_editor_property("motion_vectors", unreal.AbcGeometryCacheMotionVectorsImport.CALCULATE_MOTION_VECTORS_DURING_IMPORT)
        s.set_editor_property("geometry_cache_settings", gc)
    return s


def import_one(abc, name, kind, frame_start, frame_end):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", abc)
    task.set_editor_property("destination_path", DEST)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", settings(kind, frame_start, frame_end))
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.get_editor_property("imported_object_paths") or [])
    del task
    return paths


def bounds_cm(sm_path):
    sm = unreal.load_asset(sm_path)
    b = sm.get_bounds()
    o, e = b.origin, b.box_extent
    out = {"x": (round(o.x - e.x, 1), round(o.x + e.x, 1)), "y": (round(o.y - e.y, 1), round(o.y + e.y, 1)),
           "z": (round(o.z - e.z, 1), round(o.z + e.z, 1))}
    del sm
    return out


def main():
    report = {"ok": False}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods",
                       "curtain_baked_import.json")

    def finish(msg):
        report["message"] = msg
        with open(out, "w", encoding="utf-8") as h:
            json.dump(report, h, indent=1, default=str)
        unreal.log(("PUSS_SOFTGOODS_BAKED_IMPORT_SUCCESS|" if report["ok"] else "PUSS_SOFTGOODS_BAKED_IMPORT_STOPPED|") + msg)

    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world_name = editor.get_editor_world().get_outermost().get_name()
    if world_name != EXPECTED_WORLD or editor.get_game_world() is not None:
        return finish(f"unsafe editor state: world={world_name}")
    # A re-run may find only this script's own unsaved imports under DEST dirty (a stopped earlier run); nothing else.
    foreign = [p for p in dirty() if not p.startswith(DEST + "/")]
    if foreign:
        return finish(f"refusing: dirty packages {foreign}")
    report["own_dirty_at_start"] = dirty()
    abc = os.path.join(project(), "DerivedAssets", "CurtainCloth", "Baked", "CurtainDrop_Opening_final2.abc").replace("\\", "/")
    if not os.path.isfile(abc):
        return finish(f"missing {abc}")
    # Fail BEFORE any import if an enum/property name is wrong (a mid-script failure would leave dirty imports).
    try:
        settings(unreal.AlembicImportType.STATIC_MESH, 0, 0)
        settings(unreal.AlembicImportType.GEOMETRY_CACHE, 120, 450)
        probe = unreal.load_asset(VELVET_MASTER)
        probe.get_editor_property("used_with_geometry_cache")
        del probe
        if not unreal.load_asset(VELVET_PARENT):
            return finish(f"missing {VELVET_PARENT}")
    except Exception as exc:  # noqa: BLE001
        return finish(f"preflight failed before any import: {exc}")

    # 1) the two one-frame static meshes, and the axis check
    # UE numbers Alembic frames ABSOLUTELY (the file holds Blender frames 120-450; index 330 sampled Blender frame 330,
    # matching its extents row to 0.1 cm on 29 Sep). 121 is the first row of the bake's extents table.
    frames = {"SM_CurtainDrape_Hanging": (121, 121), "SM_CurtainDrape_Pile": (450, 450)}
    report["static_meshes"] = {}
    for name, (f0, f1) in frames.items():
        paths = import_one(abc, name, unreal.AlembicImportType.STATIC_MESH, f0, f1)
        path = f"{DEST}/{name}"
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            report["static_meshes"][name] = {"imported": paths}
            return finish(f"static mesh import produced nothing for {name}: {paths}")
        report["static_meshes"][name] = {"imported": paths, "bounds_cm": bounds_cm(path)}
    fails = []
    for name, exp in EXPECT.items():
        got = report["static_meshes"][name]["bounds_cm"]
        for ax in ("x", "y"):
            if abs(got[ax][0] - exp[ax][0]) > TOL_CM or abs(got[ax][1] - exp[ax][1]) > TOL_CM:
                fails.append(f"{name}.{ax} got {got[ax]} expected {exp[ax]}")
    report["axis_check_failures"] = fails
    if fails:
        return finish("AXIS CHECK FAILED, cache not imported, nothing saved: " + "; ".join(fails))

    # 2) velvet: Geometry Cache usage on the master (backed up first), and the drop MI
    backup = os.path.join(project(), "Backups", "PreCurtainBakedImport-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, exist_ok=True)
    shutil.copy2(os.path.join(project(), "Content", "Scenes", "Curtain", "Chaos", "Materials", "M_CurtainVelvet.uasset"), backup)
    report["backup"] = backup
    master = unreal.load_asset(VELVET_MASTER)
    report["velvet_used_with_gc_before"] = bool(master.get_editor_property("used_with_geometry_cache"))
    if not report["velvet_used_with_gc_before"]:
        master.set_editor_property("used_with_geometry_cache", True)
        unreal.MaterialEditingLibrary.recompile_material(master)
    del master
    mi_path = f"{DEST}/MI_CurtainVelvet_DeepRed_Drop"
    mi = unreal.load_asset(mi_path) if unreal.EditorAssetLibrary.does_asset_exist(mi_path) else \
        unreal.AssetToolsHelpers.get_asset_tools().create_asset("MI_CurtainVelvet_DeepRed_Drop", DEST,
                                                               unreal.MaterialInstanceConstant,
                                                               unreal.MaterialInstanceConstantFactoryNew())
    mel = unreal.MaterialEditingLibrary
    mel.set_material_instance_parent(mi, unreal.load_asset(VELVET_PARENT))
    for pname, value in (("PatternWidthM", 35.529), ("DropM", 10.0), ("SeamWidthM", 1.37)):
        mel.set_material_instance_scalar_parameter_value(mi, pname, value)
    report["mi_params"] = {p: mel.get_material_instance_scalar_parameter_value(mi, p) for p in ("PatternWidthM", "DropM", "SeamWidthM")}
    for name in frames:
        sm = unreal.load_asset(f"{DEST}/{name}")
        mats = list(sm.get_editor_property("static_materials"))
        report["static_meshes"][name]["slots"] = len(mats)
        for i in range(len(mats)):
            sm.set_material(i, mi)
        del sm, mats

    # 3) the GeometryCache (slow)
    paths = import_one(abc, "GC_CurtainDrop_Opening", unreal.AlembicImportType.GEOMETRY_CACHE, 120, 450)
    gc_path = f"{DEST}/GC_CurtainDrop_Opening"
    if not unreal.EditorAssetLibrary.does_asset_exist(gc_path):
        del mi
        return finish(f"geometry cache import produced nothing: {paths}; static meshes left UNSAVED")
    gc = unreal.load_asset(gc_path)
    report["gc"] = {"imported": paths, "start_frame": gc.get_editor_property("start_frame"),
                    "end_frame": gc.get_editor_property("end_frame"),
                    "material_slots": len(list(gc.get_editor_property("materials")))}
    gc.set_editor_property("materials", [mi] * max(1, report["gc"]["material_slots"]))
    del gc, mi

    # 4) save exactly what this script made or changed
    expected = {f"{DEST}/{n}" for n in list(frames) + ["GC_CurtainDrop_Opening", "MI_CurtainVelvet_DeepRed_Drop"]}
    expected.add(VELVET_MASTER)
    now = dirty()
    report["dirty_before_save"] = now
    unexpected = [p for p in now if p not in expected]
    if unexpected:
        return finish(f"unexpected dirty packages {unexpected}; NOTHING saved")
    saved = {p: unreal.EditorAssetLibrary.save_asset(p, only_if_is_dirty=True) for p in sorted(expected)}
    report["saved"] = saved
    report["dirty_final"] = dirty()
    report["ok"] = all(saved.values()) and not report["dirty_final"]
    finish(f"saved={saved}|gc_frames={report['gc']['start_frame']}..{report['gc']['end_frame']}"
           f"|hanging={report['static_meshes']['SM_CurtainDrape_Hanging']['bounds_cm']}"
           f"|pile={report['static_meshes']['SM_CurtainDrape_Pile']['bounds_cm']}|dirty_final={report['dirty_final']}")


main()
