"""Import the baked festoon curtain Alembic as a Geometry Cache under /Game/Scenes/Curtain, place a preview actor
beside the Passage 1 opening, and read back bounds. Saves only the new asset."""
import json, os, unreal
ABC = os.path.join(unreal.Paths.project_dir(), "DerivedAssets", "CurtainCloth", "CurtainCloth_Festoon_V1.abc")
DEST = "/Game/Scenes/Curtain/Cloth"
settings = unreal.AbcImportSettings()
settings.set_editor_property("import_type", unreal.AlembicImportType.GEOMETRY_CACHE)
conv = settings.get_editor_property("conversion_settings")
conv.set_editor_property("preset", unreal.AbcConversionPreset.CUSTOM)
conv.set_editor_property("flip_u", False); conv.set_editor_property("flip_v", True)
conv.set_editor_property("scale", unreal.Vector(100.0, -100.0, 100.0))       # metres -> cm, Y-up (Alembic) handled by rotation below
conv.set_editor_property("rotation", unreal.Vector(90.0, 0.0, 0.0))
settings.set_editor_property("conversion_settings", conv)
gc = settings.get_editor_property("geometry_cache_settings")
gc.set_editor_property("flatten_tracks", True); gc.set_editor_property("apply_constant_topology_optimizations", False)
gc.set_editor_property("compressed_position_precision", 0.01); gc.set_editor_property("compressed_texture_coordinates_number_of_bits", 12)
settings.set_editor_property("geometry_cache_settings", gc)
samp = settings.get_editor_property("sampling_settings")
samp.set_editor_property("sampling_type", unreal.AlembicSamplingType.PER_FRAME); samp.set_editor_property("frame_start", 1); samp.set_editor_property("frame_end", 405)
settings.set_editor_property("sampling_settings", samp)
task = unreal.AssetImportTask()
task.set_editor_property("filename", ABC); task.set_editor_property("destination_path", DEST)
task.set_editor_property("destination_name", "GC_CurtainCloth_Festoon_V1")
task.set_editor_property("replace_existing", True); task.set_editor_property("automated", True); task.set_editor_property("save", True)
task.set_editor_property("options", settings)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
paths = [str(p) for p in task.get_editor_property("imported_object_paths")]
info = {"imported": paths}
if paths:
    asset = unreal.EditorAssetLibrary.load_asset(paths[0].split(".")[0])
    info["class"] = asset.get_class().get_name()
    # preview actor next to the Passage 1 opening, hanging from z=1000 with the track at the origin's x
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for a in sub.get_all_level_actors():
        if a.get_actor_label() == "CurtainCloth Preview": a.destroy_actor()
    actor = sub.spawn_actor_from_class(unreal.GeometryCacheActor, unreal.Vector(-1500.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
    actor.set_actor_label("CurtainCloth Preview"); actor.set_folder_path("Scenes/Curtain")
    comp = actor.get_geometry_cache_component(); comp.set_geometry_cache(asset); comp.set_editor_property("looping", True); comp.set_editor_property("running", True)
    b = actor.get_actor_bounds(False); info["preview_bounds_extent_cm"] = [round(b[1].x), round(b[1].y), round(b[1].z)]; info["preview_origin"] = [round(b[0].x), round(b[0].y), round(b[0].z)]
    try: info["duration_s"] = float(asset.calculate_duration())
    except Exception: pass
unreal.log("CURTAIN_ABC_IMPORT|" + json.dumps(info))
